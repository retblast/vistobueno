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
			if (respuesta.status !== 200) {
				alRecibir(null, "sin_ficha"); // vacía o expirada
				return;
			}
			let sobre = null;
			try {
				sobre = JSON.parse(respuesta.responseText);
			} catch (e) {
				sobre = null;
			}
			if (!sobre || !sobre.ficha || !sobre.tramite_id) {
				// La API anterior a v1.13.0 devolvía la ficha pelada. Sin
				// `tramite_id` no se puede atar el depósito: fail-closed.
				alRecibir(null, "contrato_desactualizado");
				return;
			}
			alRecibir(sobre);
		});
	}

	function _tituloEsperadoDeFicha(sobre) {
		return (VBMapeador.valorExtraido(sobre.ficha, "dc.title") || "").trim();
	}

	function reportarDeposito(handle, intento) {
		const envio = GM_getValue(CLAVE_ENVIO, null);
		if (!envio) return;
		if (!envio.tramite_id) {
			mostrarToast(
				"El envío en curso no tiene trámite: vuelve a preparar la ficha en VistoBueno."
			);
			return;
		}
		// El ítem abierto debe ser la tesis preparada: un ítem ajeno
		// (otra pestaña, una búsqueda) no debe pisar la ranura del buzón.
		const tituloItem = VBCompuertas.tituloDeItem(doc);
		if (!tituloItem) {
			mostrarToast("La página del ítem no declara su título; no se reportó a VistoBueno.");
			return;
		}
		if (envio.titulo && !VBCompuertas.titulosCoinciden(envio.titulo, tituloItem)) {
			mostrarToast(
				"El ítem abierto no coincide con la tesis preparada; no se reportó a VistoBueno."
			);
			return;
		}
		// Sin el clic en "Depositar" no hay hora del depósito: no se
		// inventa una al abrir la página del ítem.
		if (!envio.timestamp) {
			mostrarToast(
				"No se registró el clic en Depositar; el handle no se reportó a VistoBueno."
			);
			return;
		}
		pedir(
			"/deposito",
			"POST",
			{
				tramite_id: envio.tramite_id,
				handle: handle,
				titulo_observado: tituloItem,
				timestamp: envio.timestamp,
			},
			function (respuesta) {
				if (respuesta.status === 204 || respuesta.status === 200) {
					GM_setValue(CLAVE_ENVIO, null);
					visto.reintentoNoAntes = 0;
					mostrarToast("Handle enviado a VistoBueno ✓ (" + handle + ")");
					return;
				}
				if (respuesta.status === 404 || respuesta.status === 409) {
					// El trámite ya no está vigente: reintentar no ayudaría.
					GM_setValue(CLAVE_ENVIO, null);
					mostrarToast(
						"La ficha de este depósito ya no está vigente (HTTP " +
							respuesta.status +
							"); vuelve a prepararla."
					);
					return;
				}
				const intentoActual = intento || 0;
				if (intentoActual < 2) {
					// Fallo temporal: hasta tres intentos con espera breve.
					setTimeout(function () {
						reportarDeposito(handle, intentoActual + 1);
					}, 1000 * (intentoActual + 1));
					return;
				}
				mostrarToast(
					"No se pudo reportar el handle a VistoBueno (HTTP " +
						respuesta.status +
						"). Se reintentará al cambiar la página."
				);
				// Libera el handle para un reintento posterior, con
				// enfriamiento: el propio toast muta el DOM y dispararía
				// el observador otra vez (bucle de reintentos).
				visto.handle = null;
				visto.reintentoNoAntes = Date.now() + 30000;
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
			obtenerFicha(function (sobre, motivo) {
				if (sobre) {
					llenar(sobre);
					return;
				}
				if (motivo === "contrato_desactualizado") {
					mostrarToast(
						"La API de VistoBueno no devuelve tramite_id: actualiza la app y el userscript."
					);
					return;
				}
				mostrarToast("Sin ficha pendiente: expiró o no se preparó en VistoBueno.");
			});
		});
		doc.body.appendChild(boton);
	}

	// --- Flujo principal ---

	function _tituloDelFormulario() {
		const el = doc.querySelector(VBCompuertas.SELECTORES.titulo);
		return el ? (el.value || "").trim() : "";
	}

	function llenar(sobre) {
		const ficha = sobre.ficha;
		const tramiteId = sobre.tramite_id;
		const tituloFicha = (VBMapeador.valorExtraido(ficha, "dc.title") || "").trim();
		const tituloActual = _tituloDelFormulario();
		const envio = GM_getValue(CLAVE_ENVIO, null);
		// Si el userscript YA llenó ESTE trámite y el formulario sigue
		// mostrando su título, NO se vuelve a llenar: el operador ya
		// corrigió lo que quiso y un segundo relleno pisaría sus
		// cambios (revisión PR #71, b1).
		//
		// La condición exige el mismo `tramite_id`: una ficha nueva con
		// el mismo título es otro trámite y sí se debe rellenar. También
		// exige un envío registrado: si el operador escribió el título a
		// mano (sin relleno previo), el llenado sigue adelante.
		const yaLleno =
			envio &&
			envio.tramite_id === tramiteId &&
			envio.titulo &&
			tituloFicha &&
			VBCompuertas.titulosCoinciden(envio.titulo, tituloFicha);
		if (yaLleno && tituloActual && VBCompuertas.titulosCoinciden(tituloActual, tituloFicha)) {
			mostrarToast("El formulario ya tiene esta tesis: no se volvió a rellenar.");
			return;
		}
		const plan = VBMapeador.construirPlan(ficha, VBCompuertas.SELECTORES);
		VBEjecutor.aplicarPlan(doc, plan).then(function (resumen) {
			const partes = ["Rellenado de VistoBueno — revisa antes de continuar."];
			if (resumen.exitosos.length) partes.push("Lleno: " + resumen.exitosos.join(", ") + ".");
			if (resumen.fallidos.length) partes.push("A mano: " + resumen.fallidos.join(", ") + ".");
			if (resumen.omitidos.length) partes.push("Sin dato: " + resumen.omitidos.join(", ") + ".");
			mostrarToast(partes.join(" "), 12000);
			// El timestamp del clic en "Depositar" se conserva solo si es
			// el MISMO trámite: un trámite nuevo empieza sin hora (PR #71).
			const previo = GM_getValue(CLAVE_ENVIO, null);
			GM_setValue(CLAVE_ENVIO, {
				tramite_id: tramiteId,
				titulo: VBMapeador.valorExtraido(ficha, "dc.title") || null,
				timestamp: previo && previo.tramite_id === tramiteId ? previo.timestamp || null : null,
			});
		});
	}

	function alAbrirFormulario() {
		obtenerFicha(function (sobre, motivo) {
			if (sobre) {
				mostrarBoton(_tituloEsperadoDeFicha(sobre));
				llenar(sobre);
				return;
			}
			if (motivo === "contrato_desactualizado") {
				mostrarToast(
					"La API de VistoBueno no devuelve tramite_id: actualiza la app y el userscript."
				);
			}
			// Sin ficha: el botón aparece igual (texto genérico) para
			// que el operador pueda pulsarlo tras publicar la ficha
			// desde VistoBueno con la página ya cargada (hallazgo 12:
			// el auto-relleno solo ocurre si la ficha ya estaba; el
			// botón manual rescate el caso de publicar después).
			mostrarBoton(null);
		});
	}

	// El SPA de DSpace navega sin recargar: un observador detecta tanto la
	// aparición del formulario como la página del ítem con el handle. El
	// estado se recalcula en cada pasada para que una SEGUNDA tesis (u otro
	// ítem abierto después) no quede bloqueada por la anterior.
	const visto = { formulario: false, handle: null, reintentoNoAntes: 0 };

	function revisar() {
		const hayFormulario = VBCompuertas.esFormularioTesis(doc);
		if (hayFormulario && !visto.formulario) {
			alAbrirFormulario();
		}
		visto.formulario = hayFormulario;

		const handle = VBCompuertas.esPaginaItem(doc) ? VBCompuertas.extraerHandle(doc) : null;
		if (!handle) {
			visto.handle = null;
			return;
		}
		if (handle !== visto.handle) {
			// Tras agotar los reintentos, el handle queda en enfriamiento:
			// sin este bloqueo, cada mutación del DOM (incluido el toast)
			// volvería a intentarlo y el reporte nunca pararía.
			if (visto.reintentoNoAntes && Date.now() < visto.reintentoNoAntes) {
				return;
			}
			visto.handle = handle;
			reportarDeposito(handle);
		}
	}

	let temporizador = null;
	function revisarConCalma() {
		clearTimeout(temporizador);
		temporizador = setTimeout(revisar, 300);
	}

	// Se observa el documento entero: `citation_title` vive en <head> y el
	// cuerpo del ítem se renderiza por separado; con solo <body> la
	// compuerta podía ver el handle antes que el meta y no reintentar.
	new MutationObserver(revisarConCalma).observe(doc.documentElement, {
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
					envio.timestamp = VBReloj.ahoraLima();
					GM_setValue(CLAVE_ENVIO, envio);
				}
			}
		},
		true
	);

	revisar();
})();
