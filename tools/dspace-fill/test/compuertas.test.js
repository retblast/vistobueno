// Tests de las compuertas: forma del formulario, handle y comparación
// de títulos. El DOM sale del fixture (jsdom).

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const { esFormularioTesis, extraerHandle, normalizar, titulosCoinciden } = require(
	path.join(__dirname, "..", "src", "compuertas.js")
);

function domDesde(rel) {
	const html = fs.readFileSync(path.join(__dirname, "fixtures", rel), "utf8");
	return new JSDOM(html);
}

test("esFormularioTesis: true en el fixture del formulario", () => {
	const dom = domDesde("form.html");
	assert.strictEqual(esFormularioTesis(dom.window.document), true);
});

test("esFormularioTesis: false en una página sin formulario (fail-closed)", () => {
	const dom = domDesde("item.html");
	assert.strictEqual(esFormularioTesis(dom.window.document), false);
});

test("esFormularioTesis: false sin document", () => {
	assert.strictEqual(esFormularioTesis(null), false);
});

test("extraerHandle encuentra el handle de la página del ítem", () => {
	const dom = domDesde("item.html");
	assert.strictEqual(
		extraerHandle(dom.window.document),
		"https://hdl.handle.net/20.500.14414/27871"
	);
});

test("extraerHandle devuelve null fuera de páginas de ítem", () => {
	const dom = domDesde("form.html");
	assert.strictEqual(extraerHandle(dom.window.document), null);
});

test("normalizar quita acentos, mayúsculas y espacios extra", () => {
	assert.strictEqual(normalizar("  Taller  de Títeres "), "taller de titeres");
	assert.strictEqual(normalizar("Árbol Año Él"), "arbol ano el");
	assert.strictEqual(normalizar(null), "");
});

test("titulosCoinciden tolera acentos y ediciones menores", () => {
	assert.strictEqual(titulosCoinciden("Taller de dramatización de títeres", "Taller de Dramatización de Títeres"), true);
	assert.strictEqual(titulosCoinciden("Taller de dramatización de títeres", "Taller de dramatización de títeres (edición 2)"), true);
	assert.strictEqual(titulosCoinciden("Una tesis", "Otra tesis completamente distinta"), false);
	assert.strictEqual(titulosCoinciden("", "Algo"), false);
});
