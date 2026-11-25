// Test de componente del flujo de la ficha de depósito (Actividad 15).
// Runner: vitest con jsdom + @testing-library/react (`npm test`).
//
// La pantalla `FichaDeposito.jsx` monta el trámite completo —editar los
// datos extraídos, completar los del operador, publicar en el buzón,
// esperar el reporte del userscript, aceptar el handle y descargar la
// constancia y la fila del registro— y no tenía ninguna prueba de
// componente: solo existían tests de las funciones puras de `ficha.js`.
//
// Estos tests fijan ese flujo con una API simulada que responde como la
// real (buzón de una ranura, 404 mientras no hay depósito, 204 al
// publicar, papeleo al final). Cada paso del checklist de la Actividad 15
// queda cubierto y reproducible en CI.
//
// Se fusionaron ambos conjuntos de pruebas:
// - master: flujo completo de la Actividad 15 (publicar, esperar, aceptar,
//   rechazar, descarga de constancia y fila del registro, resguardo local).
// - rama frontend/timeout-429-orcid-papeleo: ORCID del asesor como campo
//   extraído, configuración de papeleo y resguardo versionado por contenido
//   con caducidad (F1/F5).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import FichaDeposito from './FichaDeposito.jsx'

const HANDLE = 'https://hdl.handle.net/123456/1'
const TIMESTAMP = '2026-11-04T10:30:00-05:00'

// Ficha que devuelve `POST /validar` con semáforo verde (valores ya
// corregidos por el motor; los manuales vienen vacíos).
const FICHA = {
  extraidos: [
    { campo: 'dc.title', valor: 'Estrategias ludicas para la motricidad' },
    { campo: 'dc.contributor.author', valor: ['Ana Maria Perez Garcia'] },
    { campo: 'dc.contributor.advisor', valor: 'Mag. Carlos Alberto Rodriguez Miranda' },
    { campo: 'dc.description.abstract', valor: 'Resumen de demostracion.' },
    { campo: 'dc.subject', valor: ['motricidad', 'juego'] },
    { campo: 'dc.date.issued', valor: '2026' },
    { campo: 'escuela', valor: 'ESCUELA PROFESIONAL DE EDUCACION INICIAL' },
  ],
  manuales: [
    { campo: 'matricula', valor: null },
    { campo: 'renati.author.dni', valor: null },
    { campo: 'renati.advisor.dni', valor: null },
    { campo: 'renati.advisor.orcid', valor: null },
  ],
}

const REPORTE_VERDE = {
  semaforo: 'verde',
  resumen: {
    total: 49,
    total_evaluadas: 43,
    reglas_no_aplicables: 6,
    fallidos_error: 0,
    fallidos_warning: 0,
  },
  metadatos: { archivo_nombre: 'tesis.docx', archivo_tamano_bytes: 1024 },
  resultados: [],
  ficha_deposito: FICHA,
}

// Ficha para pruebas de ORCID del asesor y resguardo (rama).
const FICHA_ORCID = {
  extraidos: [
    { campo: 'dc.title', valor: 'La motivación en la universidad', pagina: 1, detectado: true },
    { campo: 'dc.contributor.author', valor: ['Ana Pérez'], pagina: 1, detectado: true },
    {
      campo: 'renati.advisor.orcid',
      valor: '0000-0002-1825-0097',
      pagina: 1,
      detectado: true,
    },
  ],
  manuales: [
    { campo: 'matricula', valor: ['20201234'] },
    { campo: 'renati.author.dni', valor: ['70112233'] },
  ],
}

const DATA_ORCID = {
  semaforo: 'verde',
  ficha_deposito: FICHA_ORCID,
  metadatos: { archivo_nombre: 'tesis.docx', archivo_tamano_bytes: 1024 },
}

const ARCHIVO = { nombre: 'tesis.docx', tamano: 1024, hash: 'hash-abc' }

const respuestaPapeleo = (cuerpo) => ({
  ok: true,
  status: 200,
  headers: { get: () => null },
  json: async () => cuerpo,
})

const renderFichaOrcid = (props = {}) =>
  render(
    <FichaDeposito
      data={DATA_ORCID}
      apiUrl=""
      archivo={ARCHIVO}
      onBack={() => {}}
      {...props}
    />
  )

// Instala una API simulada. `deposito` controla lo que responde el buzón:
// null = todavía no hay depósito (404), objeto = reporte del userscript.
// `tramites` enumera las identidades que devuelve cada publicación.
function instalarApi({
  deposito = null,
  tramites = ['tramite-1'],
  venceEn = new Date(Date.now() + 60 * 60 * 1000).toISOString(),
} = {}) {
  const llamadas = []
  let publicaciones = 0
  globalThis.fetch = vi.fn(async (url, opciones = {}) => {
    llamadas.push({ url, opciones })
    const ruta = String(url)

    if (ruta.includes('/papeleo-config')) {
      return {
        ok: true,
        status: 200,
        headers: { get: () => null },
        json: async () => ({
          nombre_responsable: 'Lic. Biblioteca FECyC',
          plantilla_configurada: true,
        }),
      }
    }

    if (ruta.includes('/ficha-pendiente')) {
      const indice = Math.min(publicaciones, tramites.length - 1)
      const tramiteId = tramites[indice]
      publicaciones += 1
      return {
        ok: true,
        status: 201,
        json: async () => ({ tramite_id: tramiteId, vence_en: venceEn }),
        headers: new Headers(),
      }
    }
    if (ruta.includes('/deposito')) {
      const indice = Math.max(0, publicaciones - 1)
      const tramiteId = tramites[Math.min(indice, tramites.length - 1)]
      const respuesta = typeof deposito === 'function' ? deposito({ indice, tramiteId }) : deposito
      if (!respuesta) {
        return { ok: false, status: 404, json: async () => null, headers: new Headers() }
      }
      const cuerpo = {
        tramite_id: tramiteId,
        ...respuesta,
      }
      return {
        ok: true,
        status: 200,
        json: async () => cuerpo,
        headers: new Headers(),
      }
    }
    if (ruta.includes('/constancia')) {
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob(['constancia'], { type: 'application/msword' }),
        headers: new Headers({ 'Content-Disposition': 'attachment; filename="constancia.docx"' }),
      }
    }
    if (ruta.includes('/fila-registro')) {
      if (ruta.includes('formato=json')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ filas: ['titulo\tautor\t20261234'] }),
          headers: new Headers(),
        }
      }
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob(['fila'], { type: 'text/tab-separated-values' }),
        headers: new Headers(),
      }
    }
    return { ok: true, status: 200, json: async () => ({}), headers: new Headers() }
  })
  return llamadas
}

// Los campos del operador alineados por autor (matrícula y DNI del autor)
// son un input por autor: la etiqueta del input es el nombre del autor y el
// id lleva el índice. Se localizan por id, no por etiqueta.
const campoPorAutor = (container, campo, indice = 0) =>
  container.querySelector(`[id="${campo}-${indice}"]`)

// Rellena los datos del operador: un valor por autor (matrícula y DNI).
function completarDatosOperador(container) {
  fireEvent.change(campoPorAutor(container, 'matricula'), { target: { value: '20261234' } })
  fireEvent.change(campoPorAutor(container, 'renati.author.dni'), {
    target: { value: '87654321' },
  })
}

describe('FichaDeposito — flujo de la Actividad 15', () => {
  beforeEach(() => {
    window.localStorage.clear()
    // jsdom no implementa la descarga de archivos ni createObjectURL.
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock')
    globalThis.URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('no muestra la ficha cuando el semáforo es rojo', () => {
    instalarApi()
    render(
      <FichaDeposito
        data={{ ...REPORTE_VERDE, semaforo: 'rojo', ficha_deposito: null }}
        apiUrl=""
        archivo={ARCHIVO}
        onBack={() => {}}
      />
    )
    expect(screen.getByText(/Ficha de depósito no disponible/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Preparar depósito/i })).toBeNull()
  })

  it('muestra los datos extraídos y los del operador', () => {
    instalarApi()
    render(<FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />)

    expect(screen.getByRole('heading', { name: /Ficha de depósito/i })).toBeTruthy()
    expect((screen.getByLabelText(/^Título$/i)).value).toBe(
      'Estrategias ludicas para la motricidad'
    )
    expect((screen.getByLabelText(/^Autores$/i)).value).toBe('Ana Maria Perez Garcia')
    expect(screen.getByText(/1 autor en la ficha/i)).toBeTruthy()
  })

  it('bloquea «Preparar depósito» mientras falten matrícula o DNI', async () => {
    instalarApi()
    render(<FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />)

    const boton = screen.getByRole('button', { name: /Preparar depósito/i })
    expect(boton).toBeDisabled()
    expect(screen.getByText(/Faltan datos para preparar el depósito/i)).toBeTruthy()
    expect(screen.getByText(/Faltan matrícula\(s\)/i)).toBeTruthy()
    expect(screen.getByText(/Faltan DNI\(s\) de autor/i)).toBeTruthy()
  })

  it('publica la ficha editada en el buzón y abre el panel de espera', async () => {
    const llamadas = instalarApi()
    const { container } = render(
      <FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />
    )

    // Editar un valor extraído (paso 3 del checklist).
    fireEvent.change(screen.getByLabelText(/^Título$/i), {
      target: { value: 'Estrategias ludicas revisadas' },
    })

    // Completar los datos del operador (paso 4): un valor por autor.
    completarDatosOperador(container)

    const boton = screen.getByRole('button', { name: /Preparar depósito/i })
    await waitFor(() => expect(boton).not.toBeDisabled())

    fireEvent.click(boton)

    await waitFor(() =>
      // El texto aparece dos veces: el botón cambia de etiqueta y el panel
      // de espera muestra el encabezado. Basta con que exista el panel.
      expect(screen.getAllByText(/Esperando el depósito/i).length).toBeGreaterThan(0)
    )
    expect(screen.getByText(/Ficha publicada en el buzón/i)).toBeTruthy()

    const publicacion = llamadas.find((c) => c.url.includes('/ficha-pendiente'))
    expect(publicacion).toBeTruthy()
    expect(publicacion.opciones.method).toBe('POST')
    const enviado = JSON.parse(publicacion.opciones.body)
    const titulo = enviado.extraidos.find((c) => c.campo === 'dc.title')
    expect(titulo.valor).toBe('Estrategias ludicas revisadas')
    const matriculaEnviada = enviado.manuales.find((c) => c.campo === 'matricula')
    expect(matriculaEnviada.valor).toEqual(['20261234'])
  })

  it('acepta el handle reportado y habilita el papeleo', async () => {
    instalarApi({
      deposito: { handle: HANDLE, titulo: 'Estrategias ludicas para la motricidad', timestamp: TIMESTAMP },
    })
    const { container } = render(
      <FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />
    )

    completarDatosOperador(container)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled()
    )
    fireEvent.click(screen.getByRole('button', { name: /Preparar depósito/i }))

    // El panel de espera deja el puesto al reporte del userscript.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Aceptar depósito/i })).toBeTruthy()
    )
    expect(screen.getByText(HANDLE)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Aceptar depósito/i }))

    await waitFor(() => expect(screen.getByText(/Papeleo/i)).toBeTruthy())
    expect(
      screen.getByRole('button', { name: /Constancia de Ana Maria Perez Garcia/i })
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: /Fila del registro \(\.tsv\)/i })).toBeTruthy()
  })

  it('avisa cuando el título recibido no coincide con la ficha', async () => {
    instalarApi({
      deposito: { handle: HANDLE, titulo: 'Un titulo completamente distinto', timestamp: TIMESTAMP },
    })
    const { container } = render(
      <FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />
    )

    completarDatosOperador(container)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled()
    )
    fireEvent.click(screen.getByRole('button', { name: /Preparar depósito/i }))

    await waitFor(() =>
      expect(screen.getByText(/El título recibido no coincide con la ficha/i)).toBeTruthy()
    )
    // El handle no se usa a ciegas: sigue disponible el botón de rechazo.
    expect(screen.getByRole('button', { name: /Rechazar y volver/i })).toBeTruthy()
  })

  it('ignora un depósito de otro trámite', async () => {
    const llamadas = instalarApi({
      deposito: {
        tramite_id: 'tramite-anterior',
        handle: HANDLE,
        titulo_observado: 'Estrategias ludicas para la motricidad',
        timestamp: TIMESTAMP,
      },
    })
    const { container } = render(
      <FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />
    )

    completarDatosOperador(container)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled()
    )
    fireEvent.click(screen.getByRole('button', { name: /Preparar depósito/i }))

    await waitFor(() =>
      expect(llamadas.some((c) => c.url.includes('/deposito'))).toBe(true)
    )
    expect(screen.queryByRole('button', { name: /Aceptar depósito/i })).toBeNull()
  })

  it('un trámite nuevo borra el handle y el papeleo anterior', async () => {
    const llamadas = instalarApi({
      tramites: ['tramite-1', 'tramite-2'],
      deposito: {
        tramite_id: 'tramite-1',
        handle: HANDLE,
        titulo_observado: 'Estrategias ludicas para la motricidad',
        timestamp: TIMESTAMP,
      },
    })
    const { container } = render(
      <FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />
    )

    completarDatosOperador(container)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled()
    )
    fireEvent.click(screen.getByRole('button', { name: /Preparar depósito/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Aceptar depósito/i })).toBeTruthy()
    )
    fireEvent.click(screen.getByRole('button', { name: /Aceptar depósito/i }))
    await waitFor(() => expect(screen.getByText(/Papeleo/i)).toBeTruthy())
    expect(screen.getByText(HANDLE)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Preparar depósito/i }))
    await waitFor(() =>
      expect(llamadas.filter((c) => c.url.includes('/ficha-pendiente')).length).toBe(2)
    )
    expect(screen.queryByText(/Papeleo/i)).toBeNull()
    expect(screen.queryByText(HANDLE)).toBeNull()
    expect(screen.queryByRole('button', { name: /Aceptar depósito/i })).toBeNull()
  })

  it('descarga la constancia del autor y la fila del registro', async () => {
    const llamadas = instalarApi({
      deposito: { handle: HANDLE, titulo: 'Estrategias ludicas para la motricidad', timestamp: TIMESTAMP },
    })
    const { container } = render(
      <FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={() => {}} />
    )

    completarDatosOperador(container)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled()
    )
    fireEvent.click(screen.getByRole('button', { name: /Preparar depósito/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Aceptar depósito/i })).toBeTruthy()
    )
    fireEvent.click(screen.getByRole('button', { name: /Aceptar depósito/i }))

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /Constancia de Ana Maria Perez Garcia/i })
      ).toBeTruthy()
    )
    fireEvent.click(screen.getByRole('button', { name: /Constancia de Ana Maria Perez Garcia/i }))

    await waitFor(() =>
      expect(llamadas.some((c) => c.url.includes('/constancia'))).toBe(true)
    )
    const peticionConstancia = llamadas.find((c) => c.url.includes('/constancia'))
    const cuerpo = JSON.parse(peticionConstancia.opciones.body)
    expect(cuerpo.handle).toBe(HANDLE)
    expect(cuerpo.timestamp).toBe(TIMESTAMP)
    expect(cuerpo.tramite_id).toBe('tramite-1')
    expect(cuerpo.indice_autor).toBe(0)

    // La fila en JSON se muestra en pantalla para copiar o pegar.
    fireEvent.click(screen.getByRole('button', { name: /Ver la fila \(texto\)/i }))
    await waitFor(() => expect(container.querySelector('.ficha-filas pre')).toBeTruthy())
    expect(container.querySelector('.ficha-filas pre').textContent).toContain('20261234')
  })

  it('resguarda la ficha editada y la borra al volver al reporte', async () => {
    const onBack = vi.fn()
    instalarApi()
    render(<FichaDeposito data={REPORTE_VERDE} apiUrl="" archivo={ARCHIVO} onBack={onBack} />)

    fireEvent.change(screen.getByLabelText(/^Título$/i), {
      target: { value: 'Titulo con datos del operador' },
    })

    await waitFor(() =>
      expect(window.localStorage.getItem('vb-ficha-deposito')).toContain('Titulo con datos')
    )

    fireEvent.click(screen.getAllByRole('button', { name: /Volver al reporte/i })[0])
    expect(onBack).toHaveBeenCalled()
    expect(window.localStorage.getItem('vb-ficha-deposito')).toBeNull()
  })
})

describe('FichaDeposito — ORCID del asesor', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respuestaPapeleo({ nombre_responsable: 'Lic. Biblioteca FECyC', plantilla_configurada: true })
    )
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('muestra el ORCID precargado con el aviso de que se detectó en el documento', async () => {
    renderFichaOrcid()
    const campo = screen.getByLabelText(/ORCID del asesor/i)
    expect(campo).toHaveValue('0000-0002-1825-0097')
    expect(screen.getByText(/verifique que sea el ORCID del asesor y no el de un autor/i)).toBeInTheDocument()
    // El ORCID no es un dato que escribe el operador: no aparece entre los
    // campos manuales.
    expect(screen.queryByLabelText(/ORCID del asesor/i, { selector: '#manual-renati.advisor.orcid' })).toBeNull()
  })

  it('si no se detectó un ORCID válido, avisa y pide escribirlo a mano', async () => {
    const data = {
      ...DATA_ORCID,
      ficha_deposito: {
        extraidos: FICHA_ORCID.extraidos.map((c) =>
          c.campo === 'renati.advisor.orcid' ? { ...c, valor: null, detectado: false } : c
        ),
        manuales: FICHA_ORCID.manuales,
      },
    }
    renderFichaOrcid({ data })
    expect(screen.getByText(/no se detect[óo] un ORCID válido/i)).toBeInTheDocument()
    expect(screen.getByText(/escr[ií]balo a mano/i)).toBeInTheDocument()
  })

  it('el ORCID no bloquea «Preparar depósito»', async () => {
    renderFichaOrcid()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled()
    )
  })
})

describe('FichaDeposito — configuración de papeleo', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('con nombre y plantilla configurados, avisa que la configuración está completa', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respuestaPapeleo({ nombre_responsable: 'Lic. Biblioteca FECyC', plantilla_configurada: true })
    )
    renderFichaOrcid()
    await waitFor(() =>
      expect(screen.getByText(/Configuración completa/i)).toBeInTheDocument()
    )
    expect(screen.getByLabelText(/Nombre del responsable/i)).toHaveValue('Lic. Biblioteca FECyC')
  })

  it('si falta algo, dice exactamente qué corregir', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respuestaPapeleo({ nombre_responsable: '', plantilla_configurada: false })
    )
    renderFichaOrcid()
    await waitFor(() => expect(screen.getByText(/Falta configuración de papeleo/i)).toBeInTheDocument())
    expect(screen.getByText(/Falta el nombre del responsable/i)).toBeInTheDocument()
    expect(screen.getByText(/Falta la plantilla oficial Modelo B/i)).toBeInTheDocument()
  })

  it('si el servidor no expone el endpoint, la pantalla lo dice y no se rompe', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: { get: () => null },
      json: async () => ({ detail: 'No encontrado' }),
    })
    renderFichaOrcid()
    await waitFor(() =>
      expect(screen.getByText(/todavía no expone la configuración de papeleo/i)).toBeInTheDocument()
    )
    expect(screen.getByRole('button', { name: /Preparar depósito/i })).toBeInTheDocument()
  })

  it('el nombre del responsable se guarda en el servidor', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        respuestaPapeleo({ nombre_responsable: '', plantilla_configurada: false })
      )
      .mockResolvedValueOnce(
        respuestaPapeleo({ nombre_responsable: 'Lic. Biblioteca FECyC', plantilla_configurada: false })
      )
    globalThis.fetch = fetchMock
    renderFichaOrcid()
    await waitFor(() => expect(screen.getByLabelText(/Nombre del responsable/i)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/Nombre del responsable/i), {
      target: { value: 'Lic. Biblioteca FECyC' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Guardar nombre/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const [, opciones] = fetchMock.mock.calls[1]
    expect(opciones.method).toBe('POST')
    expect(JSON.parse(opciones.body)).toEqual({ nombre_responsable: 'Lic. Biblioteca FECyC' })
  })
})

describe('FichaDeposito — resguardo local (F1/F5)', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respuestaPapeleo({ nombre_responsable: 'Lic. Biblioteca FECyC', plantilla_configurada: true })
    )
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('un resguardo de la versión anterior no se restaura y se explica por qué', async () => {
    window.localStorage.setItem(
      'vb-ficha-deposito',
      JSON.stringify({ clave: 'tesis.docx', ficha: { extraidos: [], manuales: [] } })
    )
    renderFichaOrcid()
    await waitFor(() =>
      expect(screen.getByText(/versión anterior de la pantalla no se restauró/i)).toBeInTheDocument()
    )
    // La ficha del servidor sigue en pantalla (no se pierde el trabajo).
    expect(screen.getByLabelText(/ORCID del asesor/i)).toHaveValue('0000-0002-1825-0097')
  })

  it('un resguardo de otro documento se descarta', async () => {
    window.localStorage.setItem(
      'vb-ficha-deposito',
      JSON.stringify({
        version: 2,
        identidad: 'hash:otro-documento',
        creado: Date.now(),
        ficha: { extraidos: [{ campo: 'matricula', valor: ['99999999'] }], manuales: [] },
      })
    )
    renderFichaOrcid()
    await waitFor(() =>
      expect(screen.getByText(/pertenecía a otro documento/i)).toBeInTheDocument()
    )
  })

  it('un resguardo caducado se descarta', async () => {
    window.localStorage.setItem(
      'vb-ficha-deposito',
      JSON.stringify({
        version: 2,
        identidad: 'hash:hash-abc',
        creado: Date.now() - 60 * 60 * 1000 - 1000,
        ficha: { extraidos: [], manuales: [] },
      })
    )
    renderFichaOrcid()
    await waitFor(() => expect(screen.getByText(/había caducado/i)).toBeInTheDocument())
  })

  it('el resguardo vigente del mismo documento sí se restaura', async () => {
    window.localStorage.setItem(
      'vb-ficha-deposito',
      JSON.stringify({
        version: 2,
        identidad: 'hash:hash-abc',
        creado: Date.now(),
        ficha: {
          extraidos: [
            { campo: 'renati.advisor.orcid', valor: '0000-0000-1111-2222', detectado: true },
          ],
          manuales: [],
        },
      })
    )
    renderFichaOrcid()
    await waitFor(() =>
      expect(screen.getByText(/Se recuperó la ficha guardada en este navegador/i)).toBeInTheDocument()
    )
    expect(screen.getByLabelText(/ORCID del asesor/i)).toHaveValue('0000-0000-1111-2222')
  })
})
