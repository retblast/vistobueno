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
