// Tests del wrapper: contrato v1.13.0 del userscript con el buzón.
// Se ejecuta el dist real en jsdom con una implementación de GM_* que
// registra las peticiones y devuelve respuestas controladas.

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const RAIZ = path.join(__dirname, "..");
const DIST = fs.readFileSync(path.join(RAIZ, "dist", "vistobueno-dspace-fill.user.js"), "utf8");
const ITEM_HTML = fs.readFileSync(path.join(__dirname, "fixtures", "item.html"), "utf8");

const TITULO_FICHA = "Taller de dramatización de títeres";
const HANDLE = "https://hdl.handle.net/20.500.14414/27871";

// Monta la página del ítem con un userscript y un buzón simulados.
// `respuestas` mapea "RUTA|METODO" a {status, body}. `peticiones` guarda
// cada llamada saliente.
function montarItem({ envio, respuestas, tituloItem }) {
	const html = tituloItem
		? ITEM_HTML.replace(
				'content="Taller de dramatización de títeres"',
				'content="' + tituloItem + '"'
			)
		: ITEM_HTML;
	const dom = new JSDOM(html, { url: "https://repositorio.unitru.edu.pe/items/1", runScripts: "dangerously" });
	const ventana = dom.window;
	const peticiones = [];

	ventana.GM_setValue = function (clave, valor) {
		ventana.localStorage.setItem("vb:" + clave, JSON.stringify(valor));
	};
	ventana.GM_getValue = function (clave, porDefecto) {
		const bruto = ventana.localStorage.getItem("vb:" + clave);
		return bruto === null ? porDefecto : JSON.parse(bruto);
	};
	ventana.GM_xmlhttpRequest = function (opciones) {
		const ruta = opciones.url.replace("/api-proxy", "").replace("http://localhost:8000", "");
		const metodo = opciones.method || "GET";
		peticiones.push({ ruta, metodo, cuerpo: opciones.data ? JSON.parse(opciones.data) : null });
		const clave = metodo + " " + ruta;
		let configuracion = respuestas[clave] || { status: 404, body: "{}" };
		// Una lista de respuestas simula la API caída y luego recuperada:
		// cada llamada consume el siguiente elemento de la lista.
		if (Array.isArray(configuracion)) {
			configuracion = configuracion.length > 1 ? configuracion.shift() : configuracion[0];
		}
		if (opciones.onload) {
			opciones.onload({
				status: configuracion.status,
				responseText: typeof configuracion.body === "string" ? configuracion.body : JSON.stringify(configuracion.body),
			});
		}
	};

	if (envio) ventana.localStorage.setItem("vb:vb_envio", JSON.stringify(envio));
	ventana.eval(DIST);
	return { dom, ventana, peticiones };
}

function dormir(ms) {
	return new Promise((resolver) => setTimeout(resolver, ms));
}

test("el depósito viaja con tramite_id y titulo_observado", async () => {
	const { ventana, peticiones } = montarItem({
		envio: { tramite_id: "tramite-1", titulo: TITULO_FICHA, timestamp: "2026-11-12T10:00:00" },
		respuestas: { "POST /deposito": { status: 204, body: "" } },
	});
	await dormir(50);

	const reporte = peticiones.find((p) => p.metodo === "POST" && p.ruta === "/deposito");
	assert.ok(reporte, "el userscript no reportó el depósito");
	assert.strictEqual(reporte.cuerpo.tramite_id, "tramite-1");
	assert.strictEqual(reporte.cuerpo.handle, HANDLE);
	assert.strictEqual(reporte.cuerpo.titulo_observado, TITULO_FICHA);
	assert.strictEqual(reporte.cuerpo.timestamp, "2026-11-12T10:00:00");
	assert.ok(!("titulo" in reporte.cuerpo), "el payload todavía usa el campo viejo `titulo`");
});

test("un ítem con otro título no se reporta", async () => {
	const { peticiones } = montarItem({
		envio: { tramite_id: "tramite-1", titulo: TITULO_FICHA, timestamp: "2026-11-12T10:00:00" },
		respuestas: { "POST /deposito": { status: 204, body: "" } },
		tituloItem: "Otra tesis completamente distinta",
	});
	await dormir(50);

	assert.ok(
		!peticiones.some((p) => p.metodo === "POST" && p.ruta === "/deposito"),
		"el userscript reportó un ítem con título distinto"
	);
});

test("sin clic en Depositar no se inventa una hora", async () => {
	const { peticiones } = montarItem({
		envio: { tramite_id: "tramite-1", titulo: TITULO_FICHA, timestamp: null },
		respuestas: { "POST /deposito": { status: 204, body: "" } },
	});
	await dormir(50);

	assert.ok(
		!peticiones.some((p) => p.metodo === "POST" && p.ruta === "/deposito"),
		"el userscript reportó un depósito sin timestamp"
	);
});

test("un envío sin tramite_id no se reporta", async () => {
	const { peticiones } = montarItem({
		envio: { titulo: TITULO_FICHA, timestamp: "2026-11-12T10:00:00" },
		respuestas: { "POST /deposito": { status: 204, body: "" } },
	});
	await dormir(50);

	assert.ok(
		!peticiones.some((p) => p.metodo === "POST" && p.ruta === "/deposito"),
		"el userscript reportó un envío sin trámite"
	);
});

test("un 409 descarta el envío viejo y avisa", async () => {
	const { ventana, peticiones } = montarItem({
		envio: { tramite_id: "tramite-1", titulo: TITULO_FICHA, timestamp: "2026-11-12T10:00:00" },
		respuestas: { "POST /deposito": { status: 409, body: '{"detail":"trámite anterior"}' } },
	});
	await dormir(50);

	assert.ok(peticiones.some((p) => p.metodo === "POST" && p.ruta === "/deposito"));
	assert.strictEqual(ventana.localStorage.getItem("vb:vb_envio"), "null");
	const toast = ventana.document.getElementById("vb-toast");
	assert.ok(toast && /vigente/.test(toast.textContent), "no avisó que el trámite ya no está vigente");
});

test("si la API falla, el reporte se reintenta y no se pierde el handle", async () => {
	// La API responde 500 y luego 204: el reintento acotado del wrapper
	// debe recoverar el mismo handle sin que el operador repita nada.
	const { ventana, peticiones } = montarItem({
		envio: { tramite_id: "tramite-1", titulo: TITULO_FICHA, timestamp: "2026-11-12T10:00:00" },
		respuestas: {
			"POST /deposito": [
				{ status: 500, body: '{"detail":"error interno"}' },
				{ status: 204, body: "" },
			],
		},
	});
	await dormir(1400);

	const reportes = peticiones.filter((p) => p.metodo === "POST" && p.ruta === "/deposito");
	assert.ok(reportes.length >= 2, "el wrapper no reintentó el reporte");
	assert.strictEqual(reportes[0].cuerpo.handle, reportes[1].cuerpo.handle);
	assert.strictEqual(reportes[0].cuerpo.tramite_id, "tramite-1");
	// Tras el éxito, el envío se limpia: el handle quedó reportado.
	assert.strictEqual(ventana.localStorage.getItem("vb:vb_envio"), "null");
});

test("el reintento es acotado: tras tres fallos no sigue insistiendo", async () => {
	const { ventana, peticiones } = montarItem({
		envio: { tramite_id: "tramite-1", titulo: TITULO_FICHA, timestamp: "2026-11-12T10:00:00" },
		respuestas: { "POST /deposito": { status: 500, body: '{"detail":"error interno"}' } },
	});
	await dormir(4000);

	const reportes = peticiones.filter((p) => p.metodo === "POST" && p.ruta === "/deposito");
	assert.strictEqual(reportes.length, 3, "el reintento no se detuvo tras tres intentos");
	// El envío sigue en el almacenamiento: una recarga puede reintentarlo.
	assert.notStrictEqual(ventana.localStorage.getItem("vb:vb_envio"), "null");
});
