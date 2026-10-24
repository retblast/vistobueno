// Construye el userscript instalable: concatena encabezado + módulos +
// wrapper en dist/. El artefacto resultante se commitea (como
// docs/openapi_spec.json) y el CI verifica el drift.
//
// Uso: node tools/dspace-fill/dev/build.js

const fs = require("fs");
const path = require("path");

const raiz = path.join(__dirname, "..");
const partes = [
	"src/encabezado.js",
	"src/compuertas.js",
	"src/mapeador.js",
	"src/ejecutor.js",
	"src/wrapper.js",
];

const contenido = partes
	.map((rel) => fs.readFileSync(path.join(raiz, rel), "utf8"))
	.join("\n\n")
	+ "\n\n// Generado por dev/build.js — editar los src/ y reconstruir.\n";

const destino = path.join(raiz, "dist", "vistobueno-dspace-fill.user.js");
fs.mkdirSync(path.dirname(destino), { recursive: true });
fs.writeFileSync(destino, contenido);
console.log("Construido: " + destino + " (" + contenido.length + " bytes)");
