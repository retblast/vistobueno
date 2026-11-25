// Tests de la lógica de la ficha de depósito (AUD-16). Runner: vitest
// (`npm test`). Sin DOM: las funciones puras de src/ficha.js concentran las
// reglas del flujo y se prueban aquí; la pantalla las consume.
import { describe, it, expect } from 'vitest'
import {
  CAMPO_AUTORES,
  CAMPO_DNI_AUTOR,
  CAMPO_MATRICULA,
  CAMPO_ORCID_ASESOR,
  CAMPO_TITULO,
  CAMPOS_EXTRAIDOS,
  CAMPOS_MANUALES,
  ESTADO_PAPELEO,
  autoresDe,
  cabecerasBuzon,
  construirCuerpoConstancia,
  construirCuerpoFilaRegistro,
  debeMostrarFicha,
  borrarResguardo,
  establecerValor,
  estadoPapeleoDe,
  faltantesDe,
  formatearTimestamp,
  generarFilaRegistro,
  guardarResguardo,
  identidadDeArchivo,
  interpretarSondeo,
  leerResguardo,
  listaDe,
  normalizar,
  mensajeDeDescarte,
  planDeDescargas,
  publicarFicha,
  sondearDeposito,
  timestampEsValido,
  tituloCoincide,
  tituloDe,
  valorDe,
} from './ficha.js'

const fichaCon = (extraidos, manuales = []) => ({ extraidos, manuales })

const TRAMITE_ID = 'tramite-1'
const VENCE_EN = new Date(Date.now() + 60_000).toISOString()
const TRAMITE = { tramiteId: TRAMITE_ID, venceEn: VENCE_EN }

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
    const resultado = interpretarSondeo(
      404,
      { detail: 'Sin depósito reportado' },
      TRAMITE
    )
    expect(resultado.estado).toBe('esperando')
    expect(resultado.mensaje).toBeUndefined()
  })

  it('200 → recibido con handle, título, timestamp y trámite', () => {
    const resultado = interpretarSondeo(
      200,
      {
        tramite_id: TRAMITE_ID,
        handle: 'https://hdl.handle.net/1234/5678',
        titulo_observado: 'La motivación en la universidad',
        timestamp: '2026-10-28T10:15:00',
      },
      TRAMITE
    )
    expect(resultado.estado).toBe('recibido')
    expect(resultado.tramiteId).toBe(TRAMITE_ID)
    expect(resultado.handle).toBe('https://hdl.handle.net/1234/5678')
    expect(resultado.titulo).toBe('La motivación en la universidad')
    expect(resultado.timestamp).toBe('2026-10-28T10:15:00')
  })

  it('un depósito de otro trámite se ignora', () => {
    const resultado = interpretarSondeo(
      200,
      {
        tramite_id: 'tramite-anterior',
        handle: 'https://hdl.handle.net/1234/5678',
        timestamp: '2026-10-28T10:15:00',
      },
      TRAMITE
    )
    expect(resultado.estado).toBe('ajeno')
    expect(resultado.handle).toBeUndefined()
  })

  it('un trámite expirado no habilita papeleo', () => {
    const vencido = {
      tramiteId: TRAMITE_ID,
      venceEn: new Date(Date.now() - 1000).toISOString(),
    }
    const resultado = interpretarSondeo(404, {}, vencido)
    expect(resultado.estado).toBe('expirado')
  })

  it('un depósito sin timestamp válido no habilita papeleo', () => {
    const resultado = interpretarSondeo(
      200,
      {
        tramite_id: TRAMITE_ID,
        handle: 'https://hdl.handle.net/1234/5678',
        timestamp: 'no-es-una-fecha',
      },
      TRAMITE
    )
    expect(resultado.estado).toBe('invalido')
  })

  it('otro status → error con el detalle del servidor', () => {
    const resultado = interpretarSondeo(500, { detail: 'Error interno' }, TRAMITE)
    expect(resultado.estado).toBe('error')
    expect(resultado.mensaje).toContain('Error interno')
  })
})

describe('cotejo de títulos (nunca usar un handle a ciegas)', () => {
  it('normaliza acentos, mayúsculas y espacios', () => {
    expect(normalizar('  ÁREA    Geómetra ')).toBe('area geometra')
  })

  it('exige igualdad después de normalizar', () => {
    expect(tituloCoincide('La motivación en la universidad', 'la MOTIVACIÓN en la universidad')).toBe(true)
    expect(tituloCoincide('La motivación en la universidad', 'La motivación en la universidad UNT')).toBe(false)
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

  it('el cuerpo de la constancia lleva el índice del autor y el trámite', () => {
    const cuerpo = construirCuerpoConstancia(
      FICHA_EJEMPLO,
      'https://hdl.handle.net/1/2',
      '2026-10-28T10:15:00',
      1,
      TRAMITE_ID
    )
    expect(cuerpo.indice_autor).toBe(1)
    expect(cuerpo.tramite_id).toBe(TRAMITE_ID)
    expect(cuerpo.handle).toBe('https://hdl.handle.net/1/2')
    expect(cuerpo.timestamp).toBe('2026-10-28T10:15:00')
    expect(cuerpo.ficha).toBe(FICHA_EJEMPLO)
  })

  it('el cuerpo de la fila del registro lleva el trámite y no índice de autor', () => {
    const cuerpo = construirCuerpoFilaRegistro(
      FICHA_EJEMPLO,
      'https://hdl.handle.net/1/2',
      '2026-10-28T10:15:00',
      TRAMITE_ID
    )
    expect(cuerpo.indice_autor).toBeUndefined()
    expect(cuerpo.tramite_id).toBe(TRAMITE_ID)
    expect(Object.keys(cuerpo).sort()).toEqual([
      'ficha',
      'handle',
      'timestamp',
      'tramite_id',
    ])
  })
})

describe('timestampEsValido', () => {
  it('acepta una fecha ISO y rechaza un texto inválido', () => {
    expect(timestampEsValido('2026-10-28T15:04:00')).toBe(true)
    expect(timestampEsValido('no-es-una-fecha')).toBe(false)
    expect(timestampEsValido('October 28, 2026')).toBe(false)
    expect(timestampEsValido('')).toBe(false)
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

describe('publicarFicha (identidad del trámite)', () => {
  it('devuelve el tramite_id y el vencimiento del servidor', async () => {
    const fetchOriginal = globalThis.fetch
    globalThis.fetch = async () => ({
      ok: true,
      status: 201,
      json: async () => ({ tramite_id: TRAMITE_ID, vence_en: VENCE_EN }),
    })
    try {
      const publicado = await publicarFicha('', FICHA_EJEMPLO)
      expect(publicado.tramite_id).toBe(TRAMITE_ID)
      expect(publicado.vence_en).toBe(VENCE_EN)
    } finally {
      globalThis.fetch = fetchOriginal
    }
  })

  it('falla si el servidor no devuelve la identidad', async () => {
    const fetchOriginal = globalThis.fetch
    globalThis.fetch = async () => ({
      ok: true,
      status: 201,
      json: async () => ({}),
    })
    try {
      await expect(publicarFicha('', FICHA_EJEMPLO)).rejects.toThrow(/identidad/i)
    } finally {
      globalThis.fetch = fetchOriginal
    }
  })
})

// Token compartido del buzón (PR #66): el header solo viaja si hay token.
describe('cabecerasBuzon', () => {
  it('sin token no añade ninguna cabecera de autenticación', () => {
    expect(cabecerasBuzon('')).toEqual({})
    expect(cabecerasBuzon(undefined)).toEqual({})
  })

  it('con token envía el header X-VistoBueno-Token', () => {
    expect(cabecerasBuzon('secreto')).toEqual({ 'X-VistoBueno-Token': 'secreto' })
  })

  it('conserva las cabeceras propias de la petición', () => {
    expect(cabecerasBuzon('secreto', { 'Content-Type': 'application/json' })).toEqual({
      'Content-Type': 'application/json',
      'X-VistoBueno-Token': 'secreto',
    })
  })

  it('las peticiones del buzón envían el token cuando se define', async () => {
    const fetchOriginal = globalThis.fetch
    const llamadas = []
    globalThis.fetch = async (url, opciones) => {
      llamadas.push({ url, opciones })
      return {
        ok: true,
        status: 201,
        json: async () => ({ tramite_id: TRAMITE_ID, vence_en: VENCE_EN }),
      }
    }
    try {
      await publicarFicha('', { extraidos: {}, manuales: [] }, 'token-de-prueba')
      await sondearDeposito('', 'token-de-prueba', TRAMITE)
      expect(llamadas[0].opciones.headers['X-VistoBueno-Token']).toBe('token-de-prueba')
      expect(llamadas[1].opciones.headers['X-VistoBueno-Token']).toBe('token-de-prueba')
    } finally {
      globalThis.fetch = fetchOriginal
    }
  })

  it('sin token, las peticiones del buzón no llevan el header', async () => {
    const fetchOriginal = globalThis.fetch
    const llamadas = []
    globalThis.fetch = async (url, opciones) => {
      llamadas.push({ url, opciones })
      return {
        ok: true,
        status: 201,
        json: async () => ({ tramite_id: TRAMITE_ID, vence_en: VENCE_EN }),
      }
    }
    try {
      await publicarFicha('', { extraidos: {}, manuales: [] })
      await sondearDeposito('', '', TRAMITE)
      expect(llamadas[0].opciones.headers['X-VistoBueno-Token']).toBeUndefined()
      expect(llamadas[1].opciones.headers['X-VistoBueno-Token']).toBeUndefined()
    } finally {
      globalThis.fetch = fetchOriginal
    }
  })
})

// ── Parte 2 de Arreglos.txt v9: el ORCID del asesor pasa a campo extraído ─
// El motor lo detecta en la carátula: el operador solo lo verifica.
describe('ORCID del asesor (contrato v1.15.0)', () => {
  it('es un campo extraído y deja de ser manual', () => {
    expect(CAMPOS_EXTRAIDOS.some((c) => c.campo === CAMPO_ORCID_ASESOR)).toBe(true)
    expect(CAMPOS_MANUALES.some((c) => c.campo === CAMPO_ORCID_ASESOR)).toBe(false)
  })

  it('el campo extraído trae el aviso de revisión', () => {
    const campo = CAMPOS_EXTRAIDOS.find((c) => c.campo === CAMPO_ORCID_ASESOR)
    expect(campo.aviso).toMatch(/asesor/i)
    expect(campo.avisoSinDetectar).toMatch(/no se detect[óo]/i)
  })

  it('el valor editado se publica en extraidos, no en manuales', () => {
    const ficha = fichaCon(
      [{ campo: CAMPO_ORCID_ASESOR, valor: '0000-0002-1825-0097', detectado: true }],
      []
    )
    const editada = establecerValor(ficha, CAMPO_ORCID_ASESOR, '0000-0000-0000-0000')
    expect(valorDe(editada, CAMPO_ORCID_ASESOR)).toBe('0000-0000-0000-0000')
    expect(editada.extraidos.some((c) => c.campo === CAMPO_ORCID_ASESOR)).toBe(true)
    expect(editada.manuales.some((c) => c.campo === CAMPO_ORCID_ASESOR)).toBe(false)
  })

  it('si llega en manuales (contrato anterior) al editarlo pasa a extraidos', () => {
    const ficha = fichaCon([], [{ campo: CAMPO_ORCID_ASESOR, valor: null }])
    const editada = establecerValor(ficha, CAMPO_ORCID_ASESOR, '0000-0001-2345-6789')
    expect(editada.extraidos.some((c) => c.campo === CAMPO_ORCID_ASESOR)).toBe(true)
    expect(editada.manuales.some((c) => c.campo === CAMPO_ORCID_ASESOR)).toBe(false)
  })

  it('no bloquea «Preparar depósito» (no entra en faltantesDe)', () => {
    const ficha = fichaCon(
      [
        { campo: CAMPO_TITULO, valor: 'Una tesis', detectado: true },
        { campo: CAMPO_AUTORES, valor: ['Ana Pérez'], detectado: true },
      ],
      [
        { campo: CAMPO_MATRICULA, valor: ['20201234'] },
        { campo: CAMPO_DNI_AUTOR, valor: ['70112233'] },
      ]
    )
    expect(faltantesDe(ficha)).toEqual([])
  })
})

// ── Parte 3 de Arreglos.txt v9: resguardo versionado, por contenido y con
// caducidad (F1 y F5).
describe('resguardo local de la ficha', () => {
  const almacenFalso = () => {
    const datos = new Map()
    return {
      getItem: (clave) => (datos.has(clave) ? datos.get(clave) : null),
      setItem: (clave, valor) => datos.set(clave, valor),
      removeItem: (clave) => datos.delete(clave),
      datos,
    }
  }

  it('la identidad se calcula por contenido (hash), no por nombre', () => {
    expect(identidadDeArchivo({ nombre: 'tesis.docx', tamano: 100, hash: 'abc' })).toBe('hash:abc')
    // Dos archivos con el mismo nombre pero distinto contenido son distintos.
    expect(identidadDeArchivo({ nombre: 'tesis.docx', tamano: 100, hash: 'abc' })).not.toBe(
      identidadDeArchivo({ nombre: 'tesis.docx', tamano: 100, hash: 'xyz' })
    )
  })

  it('sin hash cae al nombre y el tamaño (nunca mezcla documentos distintos)', () => {
    expect(identidadDeArchivo({ nombre: 'tesis.docx', tamano: 100 })).toBe('archivo:tesis.docx|100')
    expect(identidadDeArchivo({ nombre: 'tesis.docx', tamano: 100 })).not.toBe(
      identidadDeArchivo({ nombre: 'tesis.docx', tamano: 200 })
    )
  })

  it('guarda y restaura el resguardo del mismo documento', () => {
    const almacen = almacenFalso()
    const ficha = fichaCon([{ campo: CAMPO_TITULO, valor: 'Una tesis' }])
    guardarResguardo(almacen, 'hash:abc', ficha, 1000)
    const lectura = leerResguardo(almacen, 'hash:abc', 2000)
    expect(lectura.motivo).toBeNull()
    expect(lectura.ficha).toEqual(ficha)
  })

  it('un resguardo de la versión anterior no se restaura', () => {
    const almacen = almacenFalso()
    almacen.setItem('vb-ficha-deposito', JSON.stringify({ clave: 'tesis.docx', ficha: { extraidos: [] } }))
    const lectura = leerResguardo(almacen, 'hash:abc', 1000)
    expect(lectura.ficha).toBeNull()
    expect(lectura.motivo).toBe('version')
    expect(mensajeDeDescarte(lectura.motivo)).toMatch(/versión anterior/i)
  })

  it('un resguardo de otro documento no se restaura (F1)', () => {
    const almacen = almacenFalso()
    guardarResguardo(almacen, 'hash:abc', fichaCon([]), 1000)
    const lectura = leerResguardo(almacen, 'hash:otro', 2000)
    expect(lectura.ficha).toBeNull()
    expect(lectura.motivo).toBe('identidad')
  })

  it('un resguardo caducado no se restaura (F5)', () => {
    const almacen = almacenFalso()
    guardarResguardo(almacen, 'hash:abc', fichaCon([]), 1000)
    const lectura = leerResguardo(almacen, 'hash:abc', 1000 + 60 * 60 * 1000 + 1)
    expect(lectura.ficha).toBeNull()
    expect(lectura.motivo).toBe('caducado')
  })

  it('borrar el resguardo lo elimina', () => {
    const almacen = almacenFalso()
    guardarResguardo(almacen, 'hash:abc', fichaCon([]), 1000)
    borrarResguardo(almacen)
    expect(almacen.getItem('vb-ficha-deposito')).toBeNull()
  })
})

// ── Configuración de papeleo (contrato propuesto, pendiente de Int1) ───
describe('estado de la configuración de papeleo', () => {
  it('con nombre y plantilla → listo', () => {
    const estado = estadoPapeleoDe({ nombre_responsable: 'Lic. Biblioteca FECyC', plantilla_configurada: true })
    expect(estado.estado).toBe(ESTADO_PAPELEO.listo)
    expect(estado.problemas).toEqual([])
  })

  it('sin nombre → dice qué falta', () => {
    const estado = estadoPapeleoDe({ nombre_responsable: '', plantilla_configurada: true })
    expect(estado.estado).toBe(ESTADO_PAPELEO.incompleto)
    expect(estado.problemas.join(' ')).toMatch(/nombre del responsable/i)
  })

  it('sin plantilla → dice qué falta', () => {
    const estado = estadoPapeleoDe({ nombre_responsable: 'Lic. Biblioteca FECyC', plantilla_configurada: false })
    expect(estado.estado).toBe(ESTADO_PAPELEO.incompleto)
    expect(estado.problemas.join(' ')).toMatch(/Modelo B/i)
  })
})
