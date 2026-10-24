// ==UserScript==
// @name         VistoBueno — rellenador del formulario de depósito UNT
// @namespace    vistobueno
// @version      1.0.0
// @description  Pre-llena el formulario oficial de depósito de DSpace (repositorio UNT) con la ficha de VistoBueno, captura el momento del depósito y reporta el handle del ítem. Ver docs/PLAN_FICHA_DEPOSITO.md.
// @match        https://repositorio.unitru.edu.pe/*
// @run-at       document-idle
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      localhost
// ==/UserScript==


// Compuertas del rellenador: decisiones puras sobre el DOM y los textos.
// Se puede requerir en node (CommonJS) o correr en el navegador tras la
// concatenación (dist/): el archivo declara su namespace global.

const VBCompuertas = (() => {
	// Selectores estables del formulario oficial de la instancia
	// (evidencia: captura del formulario real; ver recursos/har-analisis/).
	// Se evitan los ids con prefijo numérico (7_array-0-…): ese índice
	// cambia por fila y por versión del UI; name e id fijos no.
	const SELECTORES = {
		titulo: 'input[name="dc.title"]',
		autores: 'input[name="dc.contributor.author"]',
		asesor: 'input[name="dc.contributor.advisor"]',
		resumen: 'textarea[name="dc.description.abstract"]',
		palabrasClave: 'input[name="dc.subject"]',
		anho: 'input#dc_date_issued_year',
		dniAutorMeta: 'select[name="renati.author_QUALDROP_METADATA"]',
		dniAutorValor: 'input[name="renati.author_QUALDROP_VALUE"]',
		dniAsesorMeta: 'select[name="renati.advisor_QUALDROP_METADATA"]',
		dniAsesorValor: 'input[name="renati.advisor_QUALDROP_VALUE"]',
		orcidAsesor: 'input[name="renati.advisor.orcid"]',
		derechosInput: 'input#dc_rights',
		derechosListbox: '#combobox_dc_rights_listbox',
		depositar: '#deposit',
	};

	function esFormularioTesis(doc) {
		// Compuerta por forma (fail-closed): si la página no tiene los
		// campos de la tesis, el plan no tocaría nada — mejor no intentar.
		if (!doc) return false;
		const requeridos = [SELECTORES.titulo, SELECTORES.autores, SELECTORES.resumen];
		return requeridos.every((sel) => doc.querySelector(sel) !== null);
	}

	function extraerHandle(doc) {
		// En la página del ítem archivado el handle vive en un enlace
		// https://hdl.handle.net/20.500.14414/NNNN.
		if (!doc) return null;
		const enlace = doc.querySelector('a[href*="hdl.handle.net"]');
		return enlace ? enlace.getAttribute("href") : null;
	}

	function normalizar(texto) {
		// Minúsculas, sin acentos, espacios colapsados: para comparar
		// títulos entre la ficha y el ítem sin morir por el detalle.
		if (typeof texto !== "string") return "";
		return texto
			.normalize("NFD")
			.replace(/[\u0300-\u036f]/g, "")
			.toLowerCase()
			.replace(/\s+/g, " ")
			.trim();
	}

	function titulosCoinciden(tituloFicha, tituloItem) {
		// La SPA lo usa para cotejar el handle reportado contra la ficha
		// en vuelo; aquí se exporta para probarlo y reutilizarlo.
		const a = normalizar(tituloFicha);
		const b = normalizar(tituloItem);
		if (!a || !b) return false;
		return a === b || a.includes(b) || b.includes(a);
	}

	return { SELECTORES, esFormularioTesis, extraerHandle, normalizar, titulosCoinciden };
})();

if (typeof module !== "undefined" && module.exports) {
	module.exports = VBCompuertas;
}


// Mapeador del rellenador: ficha de VistoBueno (JSON del buzón) → plan
// de relleno determinista. Puro: ni DOM ni red; todo el comportamiento
// se prueba en node sin navegador.

const VBMapeador = (() => {
	// Valor canónico del vocabulario common_rights (la causa del bug
	// http/https documentado en DSPACE_API §11): se selecciona por el
	// TEXTO visible, que es como el combobox de Angular filtra opciones.
	const ACCESO_ABIERTO = "Acceso abierto";

	function valorExtraido(ficha, campo) {
		if (!ficha || !Array.isArray(ficha.extraidos)) return null;
		const item = ficha.extraidos.find((e) => e && e.campo === campo);
		return item ? item.valor : null;
	}

	function valorManual(ficha, campo) {
		if (!ficha || !Array.isArray(ficha.manuales)) return null;
		const item = ficha.manuales.find((m) => m && m.campo === campo);
		return item ? item.valor : null;
	}

	function comoLista(valor) {
		if (valor === null || valor === undefined) return [];
		if (Array.isArray(valor)) return valor.filter((v) => typeof v === "string" && v.trim());
		return typeof valor === "string" && valor.trim() ? [valor] : [];
	}

	function construirPlan(ficha, selectores) {
		// Cada operación es independiente: si falta el dato, la operación
		// se omite y queda en el resumen (el toast lo muestra; el
		// operador completa a mano — fallo visible, nunca silencioso).
		const operaciones = [];
		const omitidos = [];

		const titulo = valorExtraido(ficha, "dc.title");
		if (typeof titulo === "string" && titulo.trim()) {
			operaciones.push({ tipo: "texto", selector: selectores.titulo, valor: titulo.trim() });
		} else {
			omitidos.push("título");
		}

		const autores = comoLista(valorExtraido(ficha, "dc.contributor.author"));
		if (autores.length) {
			operaciones.push({ tipo: "filas", selector: selectores.autores, valores: autores });
		} else {
			omitidos.push("autores");
		}

		const asesor = valorExtraido(ficha, "dc.contributor.advisor");
		if (typeof asesor === "string" && asesor.trim()) {
			operaciones.push({ tipo: "texto", selector: selectores.asesor, valor: asesor.trim() });
		} else {
			omitidos.push("asesor");
		}

		const resumen = valorExtraido(ficha, "dc.description.abstract");
		if (typeof resumen === "string" && resumen.trim()) {
			operaciones.push({ tipo: "texto", selector: selectores.resumen, valor: resumen.trim() });
		} else {
			omitidos.push("resumen");
		}

		const palabras = comoLista(valorExtraido(ficha, "dc.subject"));
		if (palabras.length) {
			operaciones.push({ tipo: "filas", selector: selectores.palabrasClave, valores: palabras });
		} else {
			omitidos.push("palabras clave");
		}

		// Solo el AÑO del campo de fecha: día y mes son widgets de solo
		// lectura (picker); el operador los elige como siempre.
		const anho = valorExtraido(ficha, "dc.date.issued");
		if (typeof anho === "string" && /^\d{4}$/.test(anho.trim())) {
			operaciones.push({ tipo: "texto", selector: selectores.anho, valor: anho.trim() });
		} else if (anho) {
			operaciones.push({ tipo: "anhoDesdeTexto", selector: selectores.anho, valor: anho });
		} else {
			omitidos.push("año de emisión");
		}

		// QUALDROP de DNI del autor: filas alineadas por posición con los
		// autores; la opción se identifica por el sufijo renati.author.dni.
		const dnisAutor = comoLista(valorManual(ficha, "renati.author.dni"));
		if (dnisAutor.length) {
			operaciones.push({
				tipo: "qualdrop",
				selectorMeta: selectores.dniAutorMeta,
				opcionSufijo: "renati.author.dni",
				selectorValor: selectores.dniAutorValor,
				valores: dnisAutor,
			});
		}

		const dniAsesor = comoLista(valorManual(ficha, "renati.advisor.dni"))[0];
		if (dniAsesor) {
			operaciones.push({
				tipo: "qualdrop",
				selectorMeta: selectores.dniAsesorMeta,
				opcionSufijo: "renati.advisor.dni",
				selectorValor: selectores.dniAsesorValor,
				valores: [dniAsesor],
			});
		}

		const orcid = comoLista(valorManual(ficha, "renati.advisor.orcid"))[0];
		if (orcid) {
			operaciones.push({ tipo: "texto", selector: selectores.orcidAsesor, valor: orcid });
		}

		// Fix del bug dc.rights: SIEMPRE se intenta (el default del
		// formulario es el http roto; el vocabulario solo tiene el
		// https canónico). Si el combobox no coopera, el operador lo
		// selecciona a mano como hace hoy — fallo visible en el resumen.
		operaciones.push({
			tipo: "combobox",
			selectorInput: selectores.derechosInput,
			selectorListbox: selectores.derechosListbox,
			texto: ACCESO_ABIERTO,
		});

		return { operaciones, omitidos: omitidos };
	}

	return { construirPlan, valorExtraido, valorManual, comoLista, ACCESO_ABIERTO };
})();

if (typeof module !== "undefined" && module.exports) {
	module.exports = VBMapeador;
}


// Ejecutor del rellenador: aplica un plan de relleno sobre el DOM del
// formulario oficial. Toma el document por parámetro (no globals) para
// que node + jsdom puedan probarlo contra el fixture del DOM real.
//
// Mecánica Angular: los reactive forms escuchan eventos, no asignaciones
// directas — se usa el setter nativo del prototipo del elemento y se
// despachan input/change (el patrón estándar de los autocompletadores).

const VBEjecutor = (() => {
	// El botón "+" de filas repetibles no está en la captura estática
	// (lo renderiza Angular en vivo): candidatos por orden; si ninguno
	// funciona, se llenan las filas existentes y el resumen avisa.
	const BOTONES_AGREGAR = [
		"ds-add-button button",
		"ds-add-group-buttons button",
		"button.add-button",
		"button[data-test='add']",
	];

	function _evento(doc, el, tipo) {
		const vista = el.ownerDocument.defaultView;
		el.dispatchEvent(new vista.Event(tipo, { bubbles: true }));
	}

	function _ponerTexto(doc, el, valor) {
		const prototipo = Object.getPrototypeOf(el);
		const descriptor = Object.getOwnPropertyDescriptor(prototipo, "value");
		if (descriptor && descriptor.set) {
			descriptor.set.call(el, valor);
		} else {
			el.value = valor; // respaldo: DOM sin setter nativo (fixture mínimo)
		}
		_evento(doc, el, "input");
		_evento(doc, el, "change");
		return true;
	}

	function _elegirOpcion(doc, select, sufijo) {
		const opcion = Array.from(select.options || []).find(
			(o) => (o.value || "").endsWith(sufijo) || (o.value || "").includes(sufijo)
		);
		if (!opcion) return false;
		select.value = opcion.value;
		_evento(doc, select, "change");
		return true;
	}

	function _aplicarTexto(doc, op) {
		const el = doc.querySelector(op.selector);
		if (!el) return false;
		return _ponerTexto(doc, el, op.valor);
	}

	function _aplicarAnhoDesdeTexto(doc, op) {
		// El valor puede venir como "2026", "2026-10-19" o similar: el
		// campo del formulario espera solo el año (maxlength=4).
		const anho = String(op.valor).match(/\d{4}/);
		if (!anho) return false;
		return _aplicarTexto(doc, { selector: op.selector, valor: anho[0] });
	}

	function _aplicarFilas(doc, op) {
		const existentes = Array.from(doc.querySelectorAll(op.selector));
		if (!existentes.length) return false;
		const necesarios = op.valores.length;
		for (let i = existentes.length; i < necesarios; i++) {
			_agregarFila(doc, op.selector);
		}
		const filas = Array.from(doc.querySelectorAll(op.selector));
		let aplicadas = 0;
		filas.slice(0, necesarios).forEach((el, i) => {
			if (op.valores[i] !== undefined && _ponerTexto(doc, el, op.valores[i])) {
				aplicadas++;
			}
		});
		// Éxito solo si TODAS las filas necesarias recibieron valor: si el
		// botón "+" no apareció y sobró gente por llenar, el resumen debe
		// mostrar "a mano" (fallo visible, nunca una fila silenciosa).
		return aplicadas === necesarios && filas.length >= necesarios;
	}

	function _agregarFila(doc, selectorCercano) {
		// Busca el botón "+" más cercano al campo (mismo contenedor de
		// formulario) y lo pulsa; si no aparece, no insiste: el resumen
		// reporta filas pendientes y el operador agrega a mano.
		for (const sel of BOTONES_AGREGAR) {
			const boton = doc.querySelector(sel);
			if (boton) {
				boton.click();
				const despues = doc.querySelectorAll(selectorCercano).length;
				if (despues > 0) return true;
			}
		}
		return false;
	}

	function _aplicarQualdrop(doc, op) {
		const metas = Array.from(doc.querySelectorAll(op.selectorMeta));
		const valores = Array.from(doc.querySelectorAll(op.selectorValor));
		if (!metas.length || !valores.length) return false;
		const necesarios = op.valores.length;
		for (let i = metas.length; i < necesarios; i++) {
			_agregarFila(doc, op.selectorMeta);
		}
		const metasFinal = Array.from(doc.querySelectorAll(op.selectorMeta));
		const valoresFinal = Array.from(doc.querySelectorAll(op.selectorValor));
		let aplicadas = 0;
		for (let i = 0; i < Math.min(necesarios, metasFinal.length, valoresFinal.length); i++) {
			const metaOk = _elegirOpcion(doc, metasFinal[i], op.opcionSufijo);
			const valorOk = _ponerTexto(doc, valoresFinal[i], op.valores[i]);
			if (metaOk && valorOk) aplicadas++;
		}
		// Igual que las filas: si faltaron filas del QUALDROP, el resumen
		// lo reporta como pendiente en vez de callarse la diferencia.
		return aplicadas === necesarios && metasFinal.length >= necesarios;
	}

	async function _aplicarCombobox(doc, op, dormir) {
		// El combobox de Angular (ng-bootstrap) filtra opciones al
		// tipear y las renderiza en el listbox. Se escribe el texto
		// canónico y se reintenta la opción unas pocas veces (Angular
		// renderiza async); si nunca aparece → false (el resumen avisa
		// y el operador selecciona a mano, como hace hoy).
		const input = doc.querySelector(op.selectorInput);
		if (!input) return false;
		_ponerTexto(doc, input, op.texto);
		const intentos = 8;
		for (let i = 0; i < intentos; i++) {
			await dormir(120);
			const listbox = doc.querySelector(op.selectorListbox);
			if (!listbox) continue;
			const opciones = listbox.querySelectorAll(
				'option, [role="option"], .dropdown-item, button, a'
			);
			for (const el of opciones) {
				const texto = (el.textContent || "").replace(/\s+/g, " ").trim();
				if (texto === op.texto) {
					el.click();
					_evento(doc, input, "change");
					return true;
				}
			}
		}
		// Sin opciones renderizadas: devolver el input al estado visible
		// original para no dejar texto suelto engañoso.
		_ponerTexto(doc, input, "");
		return false;
	}

	async function aplicarPlan(doc, plan, opciones) {
		const config = opciones || {};
		const dormir = config.dormir || ((ms) => new Promise((r) => setTimeout(r, ms)));
		const exitosos = [];
		const fallidos = [];
		for (const op of plan.operaciones) {
			let ok = false;
			if (op.tipo === "texto") ok = _aplicarTexto(doc, op);
			else if (op.tipo === "anhoDesdeTexto") ok = _aplicarAnhoDesdeTexto(doc, op);
			else if (op.tipo === "filas") ok = _aplicarFilas(doc, op);
			else if (op.tipo === "qualdrop") ok = _aplicarQualdrop(doc, op);
			else if (op.tipo === "combobox") ok = await _aplicarCombobox(doc, op, dormir);
			if (ok) exitosos.push(op.tipo);
			else fallidos.push(op.tipo);
		}
		return { exitosos, fallidos, omitidos: plan.omitidos };
	}

	return { aplicarPlan, BOTONES_AGREGAR };
})();

if (typeof module !== "undefined" && module.exports) {
	module.exports = VBEjecutor;
}


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


// Generado por dev/build.js — editar los src/ y reconstruir.
