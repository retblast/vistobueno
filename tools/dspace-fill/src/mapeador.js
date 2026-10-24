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
