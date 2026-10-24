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
const { JSDOM } = require("jsdom");

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

async function nuevaPagina(ruta) {
	const respuesta = await fetch(MOCK + ruta);
	if (!respuesta.ok) {
		throw new Error("❌ el mock no sirvió " + ruta + " (HTTP " + respuesta.status + ")");
	}
	const dom = new JSDOM(await respuesta.text(), {
		url: MOCK + ruta,
		runScripts: "dangerously", // el JS vanilla del mock (filas, combobox, Depositar)
		pretendToBeVisual: true,
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
	console.log("  ✅ timestamp del clic en Depositar:", envio.timestamp);

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
	console.log("  ✅ handle en el buzón:", deposito.handle);
	console.log("  ✅ timestamp reportado:", deposito.timestamp);

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

	console.log("OK");
	process.exit(0);
})().catch((e) => {
	console.error(e.message || e);
	process.exit(1);
});
