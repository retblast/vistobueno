// Tests del ejecutor: aplicar un plan sobre el fixture del DOM real.
// El combobox de derechos se prueba en su modo de fallo visible (el
// listbox vacío → false; el operador selecciona a mano como hoy).

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const VBEjecutor = require(path.join(__dirname, "..", "src", "ejecutor.js"));
const VBMapeador = require(path.join(__dirname, "..", "src", "mapeador.js"));
const { SELECTORES } = require(path.join(__dirname, "..", "src", "compuertas.js"));

function domFormulario() {
	const html = fs.readFileSync(path.join(__dirname, "fixtures", "form.html"), "utf8");
	return new JSDOM(html);
}

function fichaCompleta() {
	return {
		extraidos: [
			{ campo: "dc.title", valor: "Taller de dramatización de títeres", pagina: 1, detectado: true },
			{ campo: "dc.contributor.author", valor: ["Cerna Vidal Kassiel", "Varas Vega Cinthya"], pagina: 1, detectado: true },
			{ campo: "dc.contributor.advisor", valor: "Ms. Ada Lovelace", pagina: 1, detectado: true },
			{ campo: "dc.description.abstract", valor: "Resumen del trabajo.", pagina: 3, detectado: true },
			{ campo: "dc.subject", valor: ["títeres", "lectura"], pagina: 3, detectado: true },
			{ campo: "dc.date.issued", valor: "2026", pagina: null, detectado: true },
		],
		manuales: [
			{ campo: "matricula", valor: ["15185003-20", "10130003-23"] },
			{ campo: "renati.author.dni", valor: ["12345678", "87654321"] },
			{ campo: "renati.advisor.dni", valor: "11222333" },
			{ campo: "renati.advisor.orcid", valor: "0000-0002-1825-0097" },
		],
	};
}

// Dormir inmediato: el combobox no renderiza opciones en el fixture, así
// que el reintento no necesita esperar de verdad.
const dormirRapido = async () => {};

test("el plan llena los campos de texto del formulario", async () => {
	const dom = domFormulario();
	const doc = dom.window.document;
	const plan = VBMapeador.construirPlan(fichaCompleta(), SELECTORES);

	await VBEjecutor.aplicarPlan(doc, plan, { dormir: dormirRapido });

	assert.strictEqual(doc.querySelector(SELECTORES.titulo).value, "Taller de dramatización de títeres");
	assert.strictEqual(doc.querySelector(SELECTORES.asesor).value, "Ms. Ada Lovelace");
	assert.strictEqual(doc.querySelector(SELECTORES.resumen).value, "Resumen del trabajo.");
	assert.strictEqual(doc.querySelector(SELECTORES.anho).value, "2026");
	assert.strictEqual(doc.querySelector(SELECTORES.orcidAsesor).value, "0000-0002-1825-0097");
});

test("las filas repetidas se llenan por índice (autores y palabras)", async () => {
	const dom = domFormulario();
	const doc = dom.window.document;
	const plan = VBMapeador.construirPlan(fichaCompleta(), SELECTORES);

	const resumen = await VBEjecutor.aplicarPlan(doc, plan, { dormir: dormirRapido });

	// El fixture trae UNA fila por campo y sin botón "+": los valores
	// extra quedan pendientes y el resumen lo reporta (fallo visible).
	assert.strictEqual(doc.querySelector(SELECTORES.autores).value, "Cerna Vidal Kassiel");
	assert.ok(resumen.fallidos.includes("filas"));
	assert.ok(resumen.fallidos.includes("combobox"));
});

test("el QUALDROP elige la opción DNI por sufijo y llena el número", async () => {
	const dom = domFormulario();
	const doc = dom.window.document;
	const ficha = fichaCompleta();
	ficha.extraidos.find((e) => e.campo === "dc.contributor.author").valor = ["Cerna Vidal Kassiel"];
	ficha.manuales.find((m) => m.campo === "renati.author.dni").valor = ["12345678"];
	ficha.manuales.find((m) => m.campo === "renati.advisor.dni").valor = "11222333";
	const plan = VBMapeador.construirPlan(ficha, SELECTORES);

	await VBEjecutor.aplicarPlan(doc, plan, { dormir: dormirRapido });

	const metaAutor = doc.querySelector(SELECTORES.dniAutorMeta);
	assert.strictEqual(metaAutor.value, "0: renati.author.dni");
	assert.strictEqual(doc.querySelector(SELECTORES.dniAutorValor).value, "12345678");
	const metaAsesor = doc.querySelector(SELECTORES.dniAsesorMeta);
	assert.strictEqual(metaAsesor.value, "0: renati.advisor.dni");
	assert.strictEqual(doc.querySelector(SELECTORES.dniAsesorValor).value, "11222333");
});

test("el combobox sin opciones falla visible y devuelve el input a vacío", async () => {
	const dom = domFormulario();
	const doc = dom.window.document;
	const plan = VBMapeador.construirPlan(fichaCompleta(), SELECTORES);

	const resumen = await VBEjecutor.aplicarPlan(doc, plan, { dormir: dormirRapido });

	assert.ok(resumen.fallidos.includes("combobox"));
	assert.strictEqual(doc.querySelector(SELECTORES.derechosInput).value, "");
});

test("el combobox coopera cuando el listbox renderiza la opción", async () => {
	const dom = domFormulario();
	const doc = dom.window.document;
	// Simular el render de Angular: la opción aparece tras el primer reintento.
	let renderizado = false;
	setTimeout(() => {
		const listbox = doc.querySelector(SELECTORES.derechosListbox);
		const opcion = doc.createElement("button");
		opcion.type = "button"; // dentro del form: sin type sería submit
		opcion.textContent = "Acceso abierto";
		listbox.appendChild(opcion);
		renderizado = true;
	}, 50);

	const plan = VBMapeador.construirPlan(fichaCompleta(), SELECTORES);
	const resumen = await VBEjecutor.aplicarPlan(doc, plan, {
		dormir: (ms) => new Promise((r) => setTimeout(r, ms)),
	});

	assert.ok(renderizado);
	assert.ok(resumen.exitosos.includes("combobox"));
	assert.strictEqual(doc.querySelector(SELECTORES.derechosInput).value, "Acceso abierto");
});

test("operación sobre selector ausente queda como fallida, no explota", async () => {
	const dom = domFormulario();
	const doc = dom.window.document;
	const plan = {
		operaciones: [
			{ tipo: "texto", selector: "input[name=\"no.existe\"]", valor: "x" },
			{ tipo: "filas", selector: "input[name=\"tampoco\"]", valores: ["x"] },
			{ tipo: "qualdrop", selectorMeta: "select[name=\"cero\"]", opcionSufijo: "x", selectorValor: "input[name=\"cero\"]", valores: ["x"] },
		],
		omitidos: [],
	};
	const resumen = await VBEjecutor.aplicarPlan(doc, plan, { dormir: dormirRapido });
	assert.deepStrictEqual(resumen.fallidos, ["texto", "filas", "qualdrop"]);
});
