// Shim de desarrollo: implementa GM_* sobre APIs vanilla para correr el
// userscript SIN Tampermonkey (tests con jsdom y ensayo general con
// mock-dspace). En modo shim el buzón se accede por el proxy same-origin
// del mock (/api-proxy), porque un fetch de página no puede cruzar
// orígenes sin CORS — y la API real mantiene la invariante sin-CORS.
//
// Cargar ANTES del userscript: <script src="shim-gm.js"></script>

(function () {
	"use strict";
	window.__VISTOBUENO_SHIM__ = true;

	window.GM_setValue = function (clave, valor) {
		localStorage.setItem("vb:" + clave, JSON.stringify(valor));
	};

	window.GM_getValue = function (clave, porDefecto) {
		const bruto = localStorage.getItem("vb:" + clave);
		return bruto === null ? porDefecto : JSON.parse(bruto);
	};

	window.GM_xmlhttpRequest = function (opciones) {
		const configuracion = { method: opciones.method || "GET" };
		if (opciones.data !== undefined) {
			configuracion.body = opciones.data;
			configuracion.headers = { "Content-Type": "application/json" };
		}
		fetch(opciones.url, configuracion)
			.then(async function (respuesta) {
				const texto = await respuesta.text();
				if (opciones.onload) {
					opciones.onload({ status: respuesta.status, responseText: texto });
				}
			})
			.catch(function (error) {
				if (opciones.onerror) opciones.onerror(error);
			});
	};
})();
