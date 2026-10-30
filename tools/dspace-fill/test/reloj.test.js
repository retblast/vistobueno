// Tests del reloj: el timestamp del depósito debe ser hora de pared del
// Perú (America/Lima, UTC-5 sin horario de verano), no UTC.

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const { ahoraLima } = require(path.join(__dirname, "..", "src", "reloj.js"));

test("ahoraLima convierte UTC a la hora del Perú (UTC-5)", () => {
	// 02:30 UTC del 30 es 21:30 del 29 en Lima: el día retrocede.
	assert.strictEqual(ahoraLima(new Date("2026-10-30T02:30:00Z")), "2026-10-29T21:30:00");
});

test("ahoraLima usa medianoche 00, no 24", () => {
	// 05:00 UTC es medianoche en Lima; `hourCycle: h23` evita "24:00".
	assert.strictEqual(ahoraLima(new Date("2026-10-30T05:00:00Z")), "2026-10-30T00:00:00");
});

test("ahoraLima no emite offset ni sufijo UTC", () => {
	// La API interpreta un timestamp sin offset como hora de Lima.
	const valor = ahoraLima(new Date("2026-12-31T23:59:59Z"));
	assert.match(valor, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/);
	assert.strictEqual(valor, "2026-12-31T18:59:59");
});
