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
