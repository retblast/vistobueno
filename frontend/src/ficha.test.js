// Tests de la lógica de la ficha de depósito (AUD-16). Runner: vitest
// (`npm test`). Sin DOM: las funciones puras de src/ficha.js concentran las
// reglas del flujo y se prueban aquí; la pantalla las consume.
import { describe, it, expect } from 'vitest'
import {
  CAMPO_AUTORES,
  CAMPO_DNI_AUTOR,
  CAMPO_MATRICULA,
  CAMPO_TITULO,
  autoresDe,
  construirCuerpoConstancia,
  construirCuerpoFilaRegistro,
  debeMostrarFicha,
  establecerValor,
  faltantesDe,
  formatearTimestamp,
  generarFilaRegistro,
  interpretarSondeo,
  listaDe,
  normalizar,
  planDeDescargas,
  tituloCoincide,
  tituloDe,
  valorDe,
} from './ficha.js'

const fichaCon = (extraidos, manuales = []) => ({ extraidos, manuales })

const FICHA_EJEMPLO = fichaCon(
  [
    { campo: CAMPO_TITULO, valor: 'La motivación\r\nen la universidad', pagina: 1, detectado: true },
    { campo: CAMPO_AUTORES, valor: ['Ana Pérez', 'Luis Quispe'], pagina: 1, detectado: true },
  ],
  [
    { campo: CAMPO_MATRICULA, valor: ['20201234', '20205678'] },
    { campo: CAMPO_DNI_AUTOR, valor: ['70112233', '70223344'] },
  ]
)

describe('debeMostrarFicha (la ficha solo existe con semáforo verde)', () => {
  it('verde con ficha → true', () => {
    expect(debeMostrarFicha({ semaforo: 'verde', ficha_deposito: FICHA_EJEMPLO })).toBe(true)
  })

  it('rojo con ficha → false (invariante del contrato v1.7)', () => {
    expect(debeMostrarFicha({ semaforo: 'rojo', ficha_deposito: FICHA_EJEMPLO })).toBe(false)
  })

  it('verde sin ficha → false', () => {
    expect(debeMostrarFicha({ semaforo: 'verde', ficha_deposito: null })).toBe(false)
    expect(debeMostrarFicha({ semaforo: 'verde' })).toBe(false)
  })

  it('payload vacío o inválido → false (no rompe la app)', () => {
    expect(debeMostrarFicha(null)).toBe(false)
    expect(debeMostrarFicha(undefined)).toBe(false)
    expect(debeMostrarFicha({})).toBe(false)
    expect(debeMostrarFicha({ semaforo: 'verde', ficha_deposito: { extraidos: null } })).toBe(false)
  })
})

describe('ficha: lectura y escritura de campos', () => {
  it('valorDe lee extraídos y manuales', () => {
    expect(valorDe(FICHA_EJEMPLO, CAMPO_TITULO)).toBe('La motivación\r\nen la universidad')
    expect(valorDe(FICHA_EJEMPLO, CAMPO_MATRICULA)).toEqual(['20201234', '20205678'])
    expect(valorDe(FICHA_EJEMPLO, 'no.existe')).toBeNull()
  })

  it('establecerValor no muta la ficha original', () => {
    const copia = establecerValor(FICHA_EJEMPLO, CAMPO_TITULO, 'Título corregido')
    expect(tituloDe(copia)).toBe('Título corregido')
    expect(tituloDe(FICHA_EJEMPLO)).toBe('La motivación\r\nen la universidad')
  })

  it('establecerValor agrega un campo que el servidor no trajo', () => {
    const copia = establecerValor(FICHA_EJEMPLO, 'renati.advisor.dni', '45678912')
    expect(valorDe(copia, 'renati.advisor.dni')).toBe('45678912')
  })
})

describe('manuales por autor (alineación por posición)', () => {
  it('autoresDe lee la lista de autores', () => {
    expect(autoresDe(FICHA_EJEMPLO)).toEqual(['Ana Pérez', 'Luis Quispe'])
  })

  it('autoresDe tolera texto con saltos de línea', () => {
    const ficha = fichaCon([{ campo: CAMPO_AUTORES, valor: 'Ana Pérez\nLuis Quispe' }])
    expect(autoresDe(ficha)).toEqual(['Ana Pérez', 'Luis Quispe'])
  })

  it('listaDe parte un texto en elementos', () => {
    const ficha = fichaCon([], [{ campo: CAMPO_MATRICULA, valor: '20201234\n20205678' }])
    expect(listaDe(ficha, CAMPO_MATRICULA)).toEqual(['20201234', '20205678'])
  })

  it('faltantesDe detecta la desalineación de matrículas', () => {
    const desalineada = establecerValor(FICHA_EJEMPLO, CAMPO_MATRICULA, ['20201234'])
    const faltantes = faltantesDe(desalineada)
    expect(faltantes.join(' ')).toContain('matrícula')
    expect(faltantes.join(' ')).toContain('2 autor(es)')
  })

  it('faltantesDe no reporta nada con la ficha completa', () => {
    expect(faltantesDe(FICHA_EJEMPLO)).toEqual([])
  })

  it('faltantesDe avisa título y autores vacíos', () => {
    const vacia = fichaCon([], [])
    expect(faltantesDe(vacia).join(' ')).toContain('título')
    expect(faltantesDe(vacia).join(' ')).toContain('autores')
  })
})

describe('sondeo del buzón (404 silencioso)', () => {
  it('404 → esperando, sin error', () => {
    const resultado = interpretarSondeo(404, { detail: 'Sin depósito reportado' })
    expect(resultado.estado).toBe('esperando')
    expect(resultado.mensaje).toBeUndefined()
  })

  it('200 → recibido con handle, título y timestamp', () => {
    const resultado = interpretarSondeo(200, {
      handle: 'https://hdl.handle.net/1234/5678',
      titulo: 'La motivación en la universidad',
      timestamp: '2026-10-28T10:15:00',
    })
    expect(resultado.estado).toBe('recibido')
    expect(resultado.handle).toBe('https://hdl.handle.net/1234/5678')
    expect(resultado.titulo).toBe('La motivación en la universidad')
    expect(resultado.timestamp).toBe('2026-10-28T10:15:00')
  })

  it('otro status → error con el detalle del servidor', () => {
    const resultado = interpretarSondeo(500, { detail: 'Error interno' })
    expect(resultado.estado).toBe('error')
    expect(resultado.mensaje).toContain('Error interno')
  })
})

describe('cotejo de títulos (nunca usar un handle a ciegas)', () => {
  it('normaliza acentos, mayúsculas y espacios', () => {
    expect(normalizar('  ÁREA    Geómetra ')).toBe('area geometra')
  })

  it('coincide por inclusión (ediciones menores del ítem)', () => {
    expect(tituloCoincide('La motivación en la universidad', 'La motivación en la universidad UNT')).toBe(true)
    expect(tituloCoincide('La motivación en la universidad', 'la MOTIVACIÓN en la universidad')).toBe(true)
  })

  it('no coincide con otro título', () => {
    expect(tituloCoincide('La motivación en la universidad', 'El aprendizaje colaborativo')).toBe(false)
  })

  it('sin uno de los dos títulos no se puede cotejar', () => {
    expect(tituloCoincide('', 'Un título')).toBe(false)
    expect(tituloCoincide('Un título', null)).toBe(false)
  })
})

describe('papeleo: una constancia y una fila por autor', () => {
  it('planDeDescargas lista una descarga por autor', () => {
    const plan = planDeDescargas(FICHA_EJEMPLO)
    expect(plan.total).toBe(2)
    expect(plan.constancias.map((c) => c.autor)).toEqual(['Ana Pérez', 'Luis Quispe'])
    expect(plan.constancias.map((c) => c.indice)).toEqual([0, 1])
  })

  it('planDeDescargas con una sola autora', () => {
    const ficha = fichaCon([{ campo: CAMPO_AUTORES, valor: ['Ana Pérez'] }])
    expect(planDeDescargas(ficha).total).toBe(1)
  })

  it('el cuerpo de la constancia lleva el índice del autor', () => {
    const cuerpo = construirCuerpoConstancia(FICHA_EJEMPLO, 'https://hdl.handle.net/1/2', '2026-10-28T10:15:00', 1)
    expect(cuerpo.indice_autor).toBe(1)
    expect(cuerpo.handle).toBe('https://hdl.handle.net/1/2')
    expect(cuerpo.timestamp).toBe('2026-10-28T10:15:00')
    expect(cuerpo.ficha).toBe(FICHA_EJEMPLO)
  })

  it('el cuerpo de la fila del registro no lleva índice de autor', () => {
    const cuerpo = construirCuerpoFilaRegistro(FICHA_EJEMPLO, 'https://hdl.handle.net/1/2', '2026-10-28T10:15:00')
    expect(cuerpo.indice_autor).toBeUndefined()
    expect(Object.keys(cuerpo).sort()).toEqual(['ficha', 'handle', 'timestamp'])
  })
})

describe('formatearTimestamp (fecha y hora del registro)', () => {
  it('formatea ISO 8601 en DD/MM/AA y HH:MM', () => {
    const momento = formatearTimestamp('2026-10-28T15:04:00')
    expect(momento.fecha).toBe('28/10/26')
    expect(momento.hora).toBe('15:04')
  })

  it('texto inválido o vacío → campos vacíos (no inventa fechas)', () => {
    expect(formatearTimestamp('no-es-una-fecha')).toEqual({ fecha: '', hora: '' })
    expect(formatearTimestamp('')).toEqual({ fecha: '', hora: '' })
    expect(formatearTimestamp(null)).toEqual({ fecha: '', hora: '' })
  })
})

describe('generarFilaRegistro (formato json)', () => {
  it('devuelve la lista de filas del servidor', async () => {
    const fetchOriginal = globalThis.fetch
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ filas: ['\tTesis\t20201234\t28/10/\t10/'] }),
    })
    try {
      const filas = await generarFilaRegistro('', { ficha: FICHA_EJEMPLO, handle: 'h', timestamp: 't' }, 'json')
      expect(filas).toHaveLength(1)
      expect(filas[0]).toContain('20201234')
    } finally {
      globalThis.fetch = fetchOriginal
    }
  })
})
