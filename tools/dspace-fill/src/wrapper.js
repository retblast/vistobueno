// Wrapper del rellenador: pegamento delgado entre el entorno (Tampermonkey
// o el shim de desarrollo) y los módulos puros. Sin lógica de dominio:
// la viven compuertas.js, mapeador.js y ejecutor.js.

(function () {
	"use strict";

	const doc = document;
	const esShim = !!(window.__VISTOBUENO_SHIM__);
	// En Tampermonkey el buzón es la API local directa (GM_xmlhttpRequest
	// corre en el contexto de la extensión: sin CORS, sin mixed content).
	// Bajo el shim (ensayo general con mock-dspace) se usa el proxy del
	// mock: same-origin, la API real sigue sin CORS.
	const BASE = esShim ? "/api-proxy" : "http://localhost:8000";
	const CLAVE_ENVIO = "vb_envio";

	function pedir(ruta, metodo, cuerpo, alResponder) {
		const opciones = {
			method: metodo,
			url: BASE + ruta,
			onload: alResponder,
			onerror: function () {
				mostrarToast("VistoBueno no responde en " + BASE + " — ¿está corriendo la app?");
			},
		};
		if (cuerpo !== undefined) {
			opciones.data = JSON.stringify(cuerpo);
			opciones.headers = { "Content-Type": "application/json" };
		}
		GM_xmlhttpRequest(opciones);
	}

	function obtenerFicha(alRecibir) {
		pedir("/ficha-pendiente", "GET", undefined, function (respuesta) {
			if (respuesta.status === 200) {
				let ficha = null;
				try {
					ficha = JSON.parse(respuesta.responseText);
				} catch (e) {
					ficha = null;
				}
				alRecibir(ficha);
			} else {
				alRecibir(null); // sin ficha (vacía o expirada): no pasa nada
			}
		});
	}

	function reportarDeposito(handle) {
		const envio = GM_getValue(CLAVE_ENVIO, null);
		if (!envio) return;
		const timestamp =
			envio.timestamp || new Date().toISOString().slice(0, 19);
		pedir(
			"/deposito",
			"POST",
			{ handle: handle, titulo: envio.titulo || null, timestamp: timestamp },
			function (respuesta) {
				if (respuesta.status === 204 || respuesta.status === 200) {
					GM_setValue(CLAVE_ENVIO, null);
					mostrarToast("Handle enviado a VistoBueno ✓ (" + handle + ")");
				} else {
					mostrarToast("No se pudo reportar el handle a VistoBueno (HTTP " + respuesta.status + ").");
				}
			}
		);
	}

	// --- UI mínima: toast y botón flotante ---

	function mostrarToast(texto, ms) {
		let toast = doc.getElementById("vb-toast");
		if (!toast) {
			toast = doc.createElement("div");
			toast.id = "vb-toast";
			toast.style.cssText =
				"position:fixed;bottom:16px;right:16px;z-index:99999;background:#1a1a2e;" +
				"color:#eee;padding:10px 14px;border-radius:8px;font:13px sans-serif;" +
				"max-width:420px;box-shadow:0 2px 8px rgba(0,0,0,.4)";
			doc.body.appendChild(toast);
		}
		toast.textContent = texto;
		toast.style.display = "block";
		clearTimeout(toast.__vbTimer);
		toast.__vbTimer = setTimeout(function () {
			toast.style.display = "none";
		}, ms || 6000);
	}

	function mostrarBoton(tituloFicha) {
		if (doc.getElementById("vb-boton")) return;
		const boton = doc.createElement("button");
		boton.id = "vb-boton";
		boton.type = "button";
		// Sin ficha en el buzón: texto genérico (el click consulta de
		// nuevo; si la ficha llegó mientras tanto, rellena).
		boton.textContent = tituloFicha
			? "Rellenar con ficha de VistoBueno: «" + tituloFicha + "»"
			: "Rellenar con ficha de VistoBueno (consultar buzón)";
		boton.style.cssText =
			"position:fixed;top:16px;right:16px;z-index:99999;background:#28a745;color:#fff;" +
			"border:none;padding:10px 14px;border-radius:8px;font:13px sans-serif;cursor:pointer;" +
			"max-width:420px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap";
		boton.addEventListener("click", function () {
			obtenerFicha(function (ficha) {
				if (ficha) llenar(ficha);
				else mostrarToast("Sin ficha pendiente: expiró o no se preparó en VistoBueno.");
			});
		});
		doc.body.appendChild(boton);
	}

	// --- Flujo principal ---

	function llenar(ficha) {
		const plan = VBMapeador.construirPlan(ficha, VBCompuertas.SELECTORES);
		VBEjecutor.aplicarPlan(doc, plan).then(function (resumen) {
			const partes = ["Rellenado de VistoBueno — revisa antes de continuar."];
			if (resumen.exitosos.length) partes.push("Lleno: " + resumen.exitosos.join(", ") + ".");
			if (resumen.fallidos.length) partes.push("A mano: " + resumen.fallidos.join(", ") + ".");
			if (resumen.omitidos.length) partes.push("Sin dato: " + resumen.omitidos.join(", ") + ".");
			mostrarToast(partes.join(" "), 12000);
			GM_setValue(CLAVE_ENVIO, {
				titulo: VBMapeador.valorExtraido(ficha, "dc.title") || null,
				timestamp: null,
			});
		});
	}

	function alAbrirFormulario() {
		obtenerFicha(function (ficha) {
			if (ficha) {
				mostrarBoton(VBMapeador.valorExtraido(ficha, "dc.title"));
				llenar(ficha);
			} else {
				// Sin ficha: el botón aparece igual (texto genérico) para
				// que el operador pueda pulsarlo tras publicar la ficha
				// desde VistoBueno con la página ya cargada (hallazgo 12:
				// el auto-relleno solo ocurre si la ficha ya estaba; el
				// botón manual rescate el caso de publicar después).
				mostrarBoton(null);
			}
		});
	}

	// El SPA de DSpace navega sin recargar: un observador detecta tanto la
	// aparición del formulario como la página del ítem con el handle.
	const visto = { formulario: false, handle: false };

	function revisar() {
		if (!visto.formulario && VBCompuertas.esFormularioTesis(doc)) {
			visto.formulario = true;
			alAbrirFormulario();
		}
		if (!visto.handle) {
			const handle = VBCompuertas.extraerHandle(doc);
			if (handle) {
				visto.handle = true;
				reportarDeposito(handle);
			}
		}
	}

	let temporizador = null;
	function revisarConCalma() {
		clearTimeout(temporizador);
		temporizador = setTimeout(revisar, 300);
	}

	new MutationObserver(revisarConCalma).observe(doc.body, {
		childList: true,
		subtree: true,
	});

	// Momento del depósito: el clic en "Depositar" queda registrado como
	// timestamp del envío (alimenta HORA del registro y de la constancia).
	doc.addEventListener(
		"click",
		function (evento) {
			if (!evento.target) return;
			const boton = evento.target.closest
				? evento.target.closest(VBCompuertas.SELECTORES.depositar)
				: null;
			if (boton) {
				const envio = GM_getValue(CLAVE_ENVIO, null);
				if (envio) {
					envio.timestamp = new Date().toISOString().slice(0, 19);
					GM_setValue(CLAVE_ENVIO, envio);
				}
			}
		},
		true
	);

	revisar();
})();
