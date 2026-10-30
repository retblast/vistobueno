// Ejecutor del rellenador: aplica un plan de relleno sobre el DOM del
// formulario oficial. Toma el document por parámetro (no globals) para
// que node + jsdom puedan probarlo contra el fixture del DOM real.
//
// Mecánica Angular: los reactive forms escuchan eventos, no asignaciones
// directas — se usa el setter nativo del prototipo del elemento y se
// despachan input/change (el patrón estándar de los autocompletadores).

const VBEjecutor = (() => {
	// Cada fila repetible del formulario oficial (DSpace 8.1) vive en un
	// contenedor `#N_array` (evidencia: DOM real de "Editar envío"), y el
	// botón "+" de ESA fila es `button.ds-form-add-more`, dentro del mismo
	// contenedor. Los selectores adivinados de la versión anterior no
	// existían en la página: se llenaban las filas visibles y las demás
	// quedaban a mano sin avisar.
	const SELECTOR_ARRAY = '[id$="_array"]';
	const SELECTOR_AGREGAR = "button.ds-form-add-more";

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
		// Los QUALDROP del formulario real usan valores "N: campo" (p. ej.
		// "0: renati.author.dni"): basta con el sufijo exacto. El
		// `includes()` anterior podía elegir una opción de otro campo cuyo
		// nombre contuviera el sufijo.
		const opcion = Array.from(select.options || []).find((o) =>
			(o.value || "").endsWith(sufijo)
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
		// El botón se busca SOLO dentro del contenedor del campo: pulsar
		// un "+" global agregaría la fila de otro campo y desalinearía los
		// índices. Si el campo no existe o no hay botón, no se insiste: el
		// resumen reporta el faltante y el operador agrega a mano.
		const campo = doc.querySelector(selectorCercano);
		const contenedor = campo ? campo.closest(SELECTOR_ARRAY) : null;
		const boton = contenedor ? contenedor.querySelector(SELECTOR_AGREGAR) : null;
		if (!boton) return false;
		const antes = doc.querySelectorAll(selectorCercano).length;
		boton.click();
		// Angular agrega la fila en el mismo tick del clic; si no lo hizo,
		// no se insiste (la siguiente iteración no vería el cambio).
		return doc.querySelectorAll(selectorCercano).length > antes;
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

	return { aplicarPlan, SELECTOR_ARRAY, SELECTOR_AGREGAR };
})();

if (typeof module !== "undefined" && module.exports) {
	module.exports = VBEjecutor;
}
