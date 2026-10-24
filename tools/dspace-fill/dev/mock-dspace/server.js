// Servidor del ensayo general (mock-dspace): páginas locales que imitan
// el flujo de DSpace (formulario de envío + ítem archivado) para
// ejercitar el userscript SIN Tampermonkey y SIN tocar la instancia real.
//
// Rutas:
//   /                  → índice del mock
//   /mock/submit       → formulario de envío (mismos name/id del real)
//   /mock/item         → ítem archivado con handle
//   /shim-gm.js        → shim de GM_* (corre el userscript como script común)
//   /userscript.js     → dist del userscript (build de dev/build.js)
//   /api-proxy/<ruta>  → proxy same-origin hacia la API real de
//                        VistoBueno (127.0.0.1:8000): el buzón viaja por
//                        aquí porque un fetch de página no cruza orígenes
//                        sin CORS — y la API mantiene la invariante sin-CORS.
//
// Uso (desde la raíz del repo): nix run .#mock-dspace
// Checklist del ensayo: dev/mock-dspace/README.md

const http = require("http");
const fs = require("fs");
const path = require("path");

const PUERTO = Number(process.env.MOCK_PORT || 8080);
const API_PUERTO = 8000;
const RAIZ = path.join(__dirname, "..", ".."); // tools/dspace-fill/

const TIPOS = {
	".html": "text/html; charset=utf-8",
	".js": "application/javascript; charset=utf-8",
};

function servirArchivo(resp, rutaRelativa) {
	const absoluta = path.join(RAIZ, rutaRelativa);
	if (!fs.existsSync(absoluta)) {
		resp.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
		resp.end("No encontrado en el mock: " + rutaRelativa);
		return;
	}
	resp.writeHead(200, { "Content-Type": TIPOS[path.extname(absoluta)] || "text/plain" });
	fs.createReadStream(absoluta).pipe(resp);
}

function proxyApi(resp, metodo, rutaApi, cuerpo) {
	// Reenvía la solicitud al buzón de la API real y devuelve tal cual:
	// el userscript (vía shim) habla same-origin con este servidor.
	// El method viaja por parámetro (closure): un `req` global se
	// pisaría entre requests concurrentes (hallazgo 13).
	const peticion = http.request(
		{
			host: "127.0.0.1",
			port: API_PUERTO,
			method: metodo,
			path: rutaApi,
			headers: {
				"Content-Type": "application/json",
				// Longitud en BYTES, no en caracteres: los títulos con
				// acentos ocupan más de un byte en UTF-8 y una longitud
				// corta trunca el JSON del otro lado (el API responde 422).
				"Content-Length": cuerpo ? Buffer.byteLength(cuerpo, "utf8") : 0,
			},
		},
		function (respuesta) {
			resp.writeHead(respuesta.statusCode, {
				"Content-Type": respuesta.headers["content-type"] || "application/json",
			});
			respuesta.pipe(resp);
		}
	);
	peticion.on("error", function () {
		resp.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" });
		resp.end("La API de VistoBueno no responde en 127.0.0.1:" + API_PUERTO + " — ¿corrió nix run .#serve?");
	});
	if (cuerpo) peticion.write(cuerpo);
	peticion.end();
}

const rutas = {
	"/": ["dev/mock-dspace/index.html"],
	"/mock/submit": ["dev/mock-dspace/submit.html"],
	"/mock/item": ["dev/mock-dspace/item.html"],
	"/shim-gm.js": ["dev/shim-gm.js"],
	"/userscript.js": ["dist/vistobueno-dspace-fill.user.js"],
};

const servidor = http.createServer(function (solicitud, respuesta) {
	const pedazos = [];
	solicitud.on("data", function (p) {
		pedazos.push(p);
	});
	solicitud.on("end", function () {
		const cuerpo = pedazos.length ? Buffer.concat(pedazos).toString() : null;
		const url = solicitud.url.split("?")[0];

		if (url.startsWith("/api-proxy/")) {
			proxyApi(respuesta, solicitud.method, "/" + url.slice("/api-proxy/".length), cuerpo);
			return;
		}
		const ruta = rutas[url];
		if (ruta) {
			servirArchivo(respuesta, ruta[0]);
			return;
		}
		respuesta.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
		respuesta.end("Ruta desconocida del mock: " + url);
	});
});

servidor.listen(PUERTO, "127.0.0.1", function () {
	console.log("Mock de DSpace (ensayo general) en http://127.0.0.1:" + PUERTO);
	console.log("Buzón proxificado a la API real: 127.0.0.1:" + API_PUERTO);
	console.log("Checklist: tools/dspace-fill/dev/mock-dspace/README.md");
});
