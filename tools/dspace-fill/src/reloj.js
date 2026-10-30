// Reloj del userscript: fecha y hora de pared en la zona del Perú.
//
// El registro oficial y la constancia muestran la hora peruana. `Date`
// no la da directamente: `toISOString()` devuelve UTC, que en Lima va
// 5 horas adelantado y después de las 19:00 cambia el día. Este módulo
// formatea el instante en America/Lima con `Intl`, sin depender de la
// zona horaria configurada en el navegador.

const VBReloj = (() => {
	const ZONA = "America/Lima";

	// Un solo formateador: `formatToParts` entrega los campos por nombre
	// y evita depender del orden o de los separadores del locale.
	const FORMATO = new Intl.DateTimeFormat("en-CA", {
		timeZone: ZONA,
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
		hourCycle: "h23",
	});

	function ahoraLima(ahora) {
		// `ahora` es inyectable para los tests; en producción es `new Date()`.
		const partes = FORMATO.formatToParts(ahora || new Date());
		const dato = (tipo) => partes.find((parte) => parte.type === tipo).value;
		// ISO 8601 sin offset: el userscript reporta hora de pared del
		// Perú y la API interpreta un timestamp sin offset como Lima.
		return (
			dato("year") +
			"-" +
			dato("month") +
			"-" +
			dato("day") +
			"T" +
			dato("hour") +
			":" +
			dato("minute") +
			":" +
			dato("second")
		);
	}

	return { ZONA, ahoraLima };
})();

if (typeof module !== "undefined" && module.exports) {
	module.exports = VBReloj;
}
