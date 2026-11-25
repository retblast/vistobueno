// Tests de la lógica pura de la pantalla de carga (timeout y 429).
// Runner: vitest (`npm test`).
// Contexto: Arreglos.txt v9, Parte 1 (timeout del navegador y espera real
// cuando el backend responde 429 con la cabecera `Retry-After`).
import { describe, it, expect } from 'vitest'
import {
  formatearEspera,
  horaDeReintento,
  leerRetryAfter,
  mensajeEspera,
  textoEspera,
  textoEsperaHasta,
  TIMEOUT_VALIDACION_MINUTOS,
} from './upload'

const respuestaCon = (retryAfter) => ({
  headers: {
    get: (nombre) => (nombre.toLowerCase() === 'retry-after' ? retryAfter : null),
  },
})

describe('timeout del navegador', () => {
  it('espera 2 minutos antes de abortar la petición', () => {
    expect(TIMEOUT_VALIDACION_MINUTOS).toBe(2)
  })
})

describe('leerRetryAfter', () => {
  it('devuelve los segundos de la cabecera Retry-After', () => {
    expect(leerRetryAfter(respuestaCon('223'))).toBe(223)
  })

  it('devuelve null si la cabecera no viene', () => {
    expect(leerRetryAfter(respuestaCon(null))).toBeNull()
  })

  it('devuelve null si la cabecera no es un número', () => {
    expect(leerRetryAfter(respuestaCon('pronto'))).toBeNull()
  })

  it('devuelve null si la espera es cero o negativa', () => {
    expect(leerRetryAfter(respuestaCon('0'))).toBeNull()
    expect(leerRetryAfter(respuestaCon('-5'))).toBeNull()
  })

  it('no rompe si la respuesta no tiene cabeceras', () => {
    expect(leerRetryAfter({})).toBeNull()
    expect(leerRetryAfter(null)).toBeNull()
  })
})

describe('formatearEspera', () => {
  it('muestra minutos y segundos', () => {
    expect(formatearEspera(134)).toBe('2 min 14 s')
  })

  it('muestra solo segundos cuando no llega al minuto', () => {
    expect(formatearEspera(45)).toBe('45 s')
  })

  it('muestra solo minutos cuando son exactos', () => {
    expect(formatearEspera(120)).toBe('2 min')
  })

  it('nunca muestra una espera negativa', () => {
    expect(formatearEspera(-10)).toBe('0 s')
  })
})

describe('mensajeEspera / textoEspera', () => {
  it('indica cuánto falta y la hora exacta de reintento', () => {
    // 2026-11-24 15:40:00 local
    const ahora = new Date(2026, 10, 24, 15, 40, 0).getTime()
    const info = mensajeEspera(134, ahora)
    expect(info.faltan).toBe('2 min 14 s')
    expect(info.hasta).toBe('15:42')
    expect(textoEspera(134, ahora)).toBe('Faltan 2 min 14 s. Podrá reintentar a las 15:42.')
  })

  it('horaDeReintento usa formato 24 h', () => {
    expect(horaDeReintento(new Date(2026, 10, 24, 9, 5, 0).getTime())).toBe('09:05')
  })

  it('textoEsperaHasta descuenta sobre el momento límite', () => {
    const ahora = new Date(2026, 10, 24, 15, 40, 0).getTime()
    const limite = ahora + 134 * 1000
    expect(textoEsperaHasta(limite, ahora)).toBe('Faltan 2 min 14 s. Podrá reintentar a las 15:42.')
  })
})
