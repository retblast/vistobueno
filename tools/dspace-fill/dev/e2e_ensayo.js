// Driver del ensayo general de un comando (hallazgo 10, revisión PR #55).
//
// Corre el userscript REAL (dist + shim) dentro de jsdom contra el mock
// de DSpace ya levantado por scripts/e2e_ficha_deposito.sh, con el buzón
// de la API real detrás del proxy del mock:
//
//   1. Carga /mock/submit → el userscript auto-rellena el formulario.
//   2. Verifica los campos clave (título, autor, DNI, "Acceso abierto").
//   3. Pulsa Depositar → el userscript registra el timestamp.
//   4. Carga /mock/item con el localStorage de la sesión → el userscript
//      reporta el handle al buzón.
//   5. Verifica GET /deposito en la API real (handle + timestamp).
//
// Sin Playwright: jsdom + fetch real del driver bastan porque el shim
// delega el buzón al proxy same-origin del mock.

const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const MOCK = process.env.MOCK_URL || "http://127.0.0.1:8080";
const API = process.env.API_URL || "http://127.0.0.1:8000";
const RAIZ = path.join(__dirname, "..");

const SHIM = fs.readFileSync(path.join(RAIZ, "dev", "shim-gm.js"), "utf8");
const USERSCRIPT = fs.readFileSync(
	path.join(RAIZ, "dist", "vistobueno-dspace-fill.user.js"),
	"utf8"
);

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

async function esperar(condicion, msTotal, mensaje) {
	const inicio = Date.now();
	while (Date.now() - inicio < msTotal) {
		// await: la condición puede ser síncrona o async (sin el await,
		// una promesa se evaluaría como truthy antes de resolverse).
		if (await condicion()) return;
		await dormir(150);
	}
	throw new Error("❌ " + mensaje);
}

// jsdom no implementa la navegación entre páginas (location.href). El mock
// navega al ítem al pulsar Depositar, así que ese error es esperado y no
// dice nada del userscript: se filtra para no ensuciar la salida verde del
// ensayo. Los demás errores de jsdom sí se muestran.
function consolaVirtual() {
	const vc = new VirtualConsole();
	vc.sendTo(console, { omitJSDOMErrors: true });
	vc.on("jsdomError", (error) => {
		const mensaje = (error && error.message) || String(error);
		if (/Not implemented: navigation/.test(mensaje)) return;
		console.error("[jsdom]", mensaje);
	});
	return vc;
}

async function nuevaPagina(ruta) {
	const respuesta = await fetch(MOCK + ruta);
	if (!respuesta.ok) {
		throw new Error("❌ el mock no sirvió " + ruta + " (HTTP " + respuesta.status + ")");
	}
	const dom = new JSDOM(await respuesta.text(), {
		url: MOCK + ruta,
		runScripts: "dangerously", // el JS vanilla del mock (filas, combobox, Depositar)
		pretendToBeVisual: true,
		virtualConsole: consolaVirtual(),
	});
	// El shim usa fetch relativo: se resuelve contra el mock (el proxy
	// /api-proxy del mock habla con la API real — la invariante sin-CORS
	// de la API queda intacta).
	dom.window.fetch = (url, opciones) =>
		fetch(new URL(url, MOCK + ruta).href, opciones);
	return dom;
}

function ejecutarUserscript(dom) {
	dom.window.eval(SHIM);
	dom.window.eval(USERSCRIPT);
}

function migrarLocalStorage(origen, destino) {
	// El envío en curso (título + timestamp) vive en localStorage: en un
	// navegador sobrevive la navegación; entre páginas de jsdom hay que
	// llevarlo a mano.
	for (let i = 0; i < origen.length; i++) {
		const clave = origen.key(i);
		if (clave && clave.startsWith("vb:")) {
			destino.setItem(clave, origen.getItem(clave));
		}
	}
}

(async () => {
	// --- 1. Formulario: auto-relleno ---
	const dom = await nuevaPagina("/mock/submit");
	ejecutarUserscript(dom);
	const doc = dom.window.document;

	await esperar(
		() => (doc.querySelector('input[name="dc.title"]') || {}).value !== "",
		10000,
		"el formulario no se rellenó: ¿publicaste la ficha en el buzón?"
	);

	const titulo = doc.querySelector('input[name="dc.title"]').value;
	const autor = doc.querySelector('input[name="dc.contributor.author"]').value;
	const dniTipo = (doc.querySelector('select[name="renati.author_QUALDROP_METADATA"]') || {}).value || "";
	const dniValor = (doc.querySelector('input[name="renati.author_QUALDROP_VALUE"]') || {}).value;
	const derechos = (doc.getElementById("dc_rights") || {}).value;

	const espera = {
		titulo: "Estrategias lúdicas",
		autor: "Ana María Pérez García",
		dniTipo: "renati.author.dni",
		dniValor: "12345678",
		derechos: "Acceso abierto",
	};
	const fallas = [];
	if (!titulo.includes(espera.titulo)) fallas.push("título");
	if (autor !== espera.autor) fallas.push("autor");
	if (!dniTipo.endsWith(espera.dniTipo)) fallas.push("DNI (tipo)");
	if (dniValor !== espera.dniValor) fallas.push("DNI (número)");
	if (derechos !== espera.derechos) fallas.push("Acceso abierto (fix dc.rights)");
	if (fallas.length) {
		throw new Error("❌ campos sin llenar o incorrectos: " + fallas.join(", "));
	}
	console.log("  ✅ relleno: título, autor, DNI y 'Acceso abierto'");

	// --- 2. Depositar: timestamp ---
	// Precondición: el wrapper guarda el envío en curso cuando termina de
	// rellenar (microtask). Esperarla: el clic no debe ganarle a la cola.
	await esperar(
		() => dom.window.localStorage.getItem("vb:vb_envio") !== null,
		5000,
		"el envío en curso nunca quedó registrado tras el relleno"
	);
	doc.getElementById("deposit").click();
	await dormir(400);
	const envio = JSON.parse(dom.window.localStorage.getItem("vb:vb_envio") || "null");
	if (!envio || !envio.timestamp) {
		throw new Error("❌ el clic en Depositar no registró el timestamp");
	}
	if (!envio.tramite_id) {
		throw new Error("❌ el envío en curso no guardó el tramite_id");
	}
	console.log("  ✅ timestamp del clic en Depositar:", envio.timestamp);
	console.log("  ✅ trámite del envío en curso:", envio.tramite_id);

	// --- 3. Página del ítem: reporte del handle ---
	const domItem = await nuevaPagina("/mock/item");
	migrarLocalStorage(dom.window.localStorage, domItem.window.localStorage);
	const envioMigrado = domItem.window.localStorage.getItem("vb:vb_envio");
	if (!envioMigrado) {
		throw new Error("❌ el envío en curso no migró a la página del ítem (localStorage)");
	}
	ejecutarUserscript(domItem);
	await dormir(1500);
	const toastItem = domItem.window.document.getElementById("vb-toast");
	if (toastItem) {
		console.log("  [diag] toast del ítem:", toastItem.textContent);
	}

	await esperar(
		async () => {
			const r = await fetch(API + "/deposito");
			return r.status === 200;
		},
		8000,
		"el handle nunca llegó al buzón (GET /deposito vacío)"
	);

	const respuesta = await fetch(API + "/deposito");
	const deposito = await respuesta.json();
	if (!deposito.handle || !deposito.handle.includes("hdl.handle.net")) {
		throw new Error("❌ el handle reportado no parece handle: " + deposito.handle);
	}
	if (!deposito.timestamp) {
		throw new Error("❌ el depósito llegó sin timestamp");
	}
	if (deposito.tramite_id !== envio.tramite_id) {
		throw new Error(
			"❌ el depósito no lleva el trámite del envío: " +
				deposito.tramite_id +
				" ≠ " +
				envio.tramite_id
		);
	}
	const tituloObservado = String(deposito.titulo_observado || "");
	if (!tituloObservado.includes("Estrategias lúdicas")) {
		throw new Error("❌ el título observado no corresponde a la tesis: " + tituloObservado);
	}
	console.log("  ✅ handle en el buzón:", deposito.handle);
	console.log("  ✅ timestamp reportado:", deposito.timestamp);
	console.log("  ✅ título observado:", tituloObservado);

	// --- 4. Hallazgo 12: el botón flotante debe ser usable en una
	// SEGUNDA carga de página (el fail-closed anterior lo ocultaba si
	// el buzón cambió entre cargas). La ficha sigue en el buzón
	// (última gana): el botón debe mostrar el título y rellenar al
	// pulsarlo — el caso del operador que abre otra pestaña después.
	const domTarde = await nuevaPagina("/mock/submit");
	migrarLocalStorage(dom.window.localStorage, domTarde.window.localStorage);
	ejecutarUserscript(domTarde);
	const docTarde = domTarde.window.document;

	await esperar(
		() => docTarde.getElementById("vb-boton") !== null,
		5000,
		"el botón flotante no apareció en la segunda página (hallazgo 12)"
	);
	const textoBoton = docTarde.getElementById("vb-boton").textContent;
	if (!textoBoton.includes("Rellenar")) {
		throw new Error("❌ el botón flotante no dice 'Rellenar': " + textoBoton);
	}
	console.log("  ✅ botón flotante en la segunda página:", textoBoton.slice(0, 60));

	// Pulsar el botón: debe re-consultar el buzón y rellenar. Se limpia
	// el título antes del clic para que la espera dependa del clic y no
	// del auto-relleno que ya ocurrió (la ficha sigue en el buzón).
	docTarde.querySelector('input[name="dc.title"]').value = "";
	docTarde.getElementById("vb-boton").click();
	await esperar(
		() => (docTarde.querySelector('input[name="dc.title"]') || {}).value !== "",
		5000,
		"el botón flotante no rellenó el formulario al pulsarlo (hallazgo 12)"
	);
	console.log("  ✅ relleno tras pulsar el botón en la segunda página (hallazgo 12 cerrado)");

	// --- 5. Re-llenado: no pisa lo que corrigió el operador (PR #71, b1) ---
	// Con el título ya coincidente, un nuevo "Rellenar" NO debe tocar los
	// campos: el operador corrigió el asesor a mano y ese cambio se queda.
	const asesorEditado = "Mag. Asesor Corregido A Mano";
	const inputAsesor = docTarde.querySelector('input[name="dc.contributor.advisor"]');
	inputAsesor.value = asesorEditado;
	const timestampPrevio = JSON.parse(
		domTarde.window.localStorage.getItem("vb:vb_envio") || "null"
	);
	docTarde.getElementById("vb-boton").click();
	await dormir(600);
	const asesorFinal = docTarde.querySelector('input[name="dc.contributor.advisor"]').value;
	if (asesorFinal !== asesorEditado) {
		throw new Error("❌ el re-llenado pisó la edición del operador: " + asesorFinal);
	}
	const envioTarde = JSON.parse(domTarde.window.localStorage.getItem("vb:vb_envio") || "null");
	if (!envioTarde || envioTarde.timestamp !== (timestampPrevio && timestampPrevio.timestamp)) {
		throw new Error("❌ el re-llenado borró el timestamp del clic en Depositar");
	}
	console.log("  ✅ re-llenado: conserva la edición del operador y el timestamp");

	// --- 6. Dos autores: el "+" real agrega la fila y la llena (PR #71, M5) ---
	// Se publica una ficha con dos autores (botón del mock) y se carga una
	// página nueva: el formulario debe quedar con DOS autores y DOS DNIs.
	const domDos = await nuevaPagina("/mock/submit");
	const docDos = domDos.window.document;
	await esperar(
		() => docDos.getElementById("btn-publicar-ficha-dos") !== null,
		5000,
		"el mock no sirvió el botón de ficha con dos autores"
	);
	docDos.getElementById("btn-publicar-ficha-dos").click();
	await esperar(
		async () => {
			const r = await fetch(MOCK + "/api-proxy/ficha-pendiente");
			if (r.status !== 200) return false;
			const sobre = await r.json();
			const ficha = sobre.ficha || {};
			const autores = (ficha.extraidos || []).find((e) => e.campo === "dc.contributor.author");
			return autores && Array.isArray(autores.valor) && autores.valor.length === 2;
		},
		8000,
		"la ficha de dos autores nunca llegó al buzón"
	);

	const domDos2 = await nuevaPagina("/mock/submit");
	ejecutarUserscript(domDos2);
	const docDos2 = domDos2.window.document;
	await esperar(
		() => docDos2.querySelectorAll('input[name="dc.contributor.author"]').length >= 2,
		10000,
		"el botón + no agregó la segunda fila de autor"
	);
	await esperar(
		() =>
			Array.from(docDos2.querySelectorAll('input[name="dc.contributor.author"]')).every(
				(el) => el.value !== ""
			),
		10000,
		"las filas de autor quedaron vacías"
	);
	const autoresDos = Array.from(
		docDos2.querySelectorAll('input[name="dc.contributor.author"]')
	).map((el) => el.value);
	const esperadoAutores = ["Ana María Pérez García", "Luis Alberto Ramírez Vega"];
	if (JSON.stringify(autoresDos) !== JSON.stringify(esperadoAutores)) {
		throw new Error("❌ autores con dos filas: " + JSON.stringify(autoresDos));
	}
	await esperar(
		() =>
			Array.from(docDos2.querySelectorAll('input[name="renati.author_QUALDROP_VALUE"]')).every(
				(el) => el.value !== ""
			) &&
			docDos2.querySelectorAll('input[name="renati.author_QUALDROP_VALUE"]').length >= 2,
		10000,
		"los DNI de los dos autores no quedaron llenos"
	);
	const dnisDos = Array.from(
		docDos2.querySelectorAll('input[name="renati.author_QUALDROP_VALUE"]')
	).map((el) => el.value);
	if (JSON.stringify(dnisDos) !== JSON.stringify(["12345678", "87654321"])) {
		throw new Error("❌ DNI con dos filas: " + JSON.stringify(dnisDos));
	}
	console.log("  ✅ dos autores: el + agregó la fila y los DNI quedaron alineados");

	// --- 7. El handle se reporta para el TRÁMITE vigente ---
	// Publicar una ficha nueva invalida el depósito anterior (contrato
	// v1.13.0). El papeleo necesita un depósito del trámite actual: por
	// eso el clic en Depositar y el reporte del handle se repiten con la
	// ficha de dos autores.
	docDos2.getElementById("deposit").click();
	await dormir(400);
	const envioDos = JSON.parse(domDos2.window.localStorage.getItem("vb:vb_envio") || "null");
	if (!envioDos || !envioDos.timestamp) {
		throw new Error("❌ el clic en Depositar no registró el timestamp del trámite de dos autores");
	}

	const domItemDos = await nuevaPagina("/mock/item");
	migrarLocalStorage(domDos2.window.localStorage, domItemDos.window.localStorage);
	ejecutarUserscript(domItemDos);
	await esperar(
		async () => {
			const r = await fetch(API + "/deposito");
			if (r.status !== 200) return false;
			const d = await r.json();
			return d.tramite_id === envioDos.tramite_id;
		},
		8000,
		"el handle no llegó al buzón para el trámite vigente (dos autores)"
	);
	const depositoDos = await (await fetch(API + "/deposito")).json();
	console.log("  ✅ handle reportado para el trámite vigente:", depositoDos.tramite_id);

	console.log("OK");
	process.exit(0);
})().catch((e) => {
	console.error(e.message || e);
	process.exit(1);
});
