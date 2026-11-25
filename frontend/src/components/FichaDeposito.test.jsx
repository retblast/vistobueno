// Tests de componente de la pantalla de ficha de depósito.
// Runner: vitest con jsdom + @testing-library/react (`npm test`).
// Cubren: el ORCID del asesor como campo extraído con aviso de revisión
// (Arreglos.txt v9, Parte 2), la sección de configuración de papeleo y el
// resguardo local versionado, por contenido y con caducidad (F1/F5).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import FichaDeposito from './FichaDeposito.jsx'

const FICHA = {
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

const DATA = {
  semaforo: 'verde',
  ficha_deposito: FICHA,
  metadatos: { archivo_nombre: 'tesis.docx', archivo_tamano_bytes: 1024 },
}

const respuestaPapeleo = (cuerpo) => ({
  ok: true,
  status: 200,
  headers: { get: () => null },
  json: async () => cuerpo,
})

const renderFicha = (props = {}) =>
  render(
    <FichaDeposito
      data={DATA}
      apiUrl=""
      archivo={{ nombre: 'tesis.docx', tamano: 1024, hash: 'hash-abc' }}
      onBack={() => {}}
      {...props}
    />
  )

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
    renderFicha()
    const campo = screen.getByLabelText(/ORCID del asesor/i)
    expect(campo).toHaveValue('0000-0002-1825-0097')
    expect(screen.getByText(/verifique que sea el ORCID del asesor y no el de un autor/i)).toBeInTheDocument()
    // El ORCID no es un dato que escribe el operador: no aparece entre los
    // campos manuales.
    expect(screen.queryByLabelText(/ORCID del asesor/i, { selector: '#manual-renati.advisor.orcid' })).toBeNull()
  })

  it('si no se detectó un ORCID válido, avisa y pide escribirlo a mano', async () => {
    const data = {
      ...DATA,
      ficha_deposito: {
        extraidos: FICHA.extraidos.map((c) =>
          c.campo === 'renati.advisor.orcid' ? { ...c, valor: null, detectado: false } : c
        ),
        manuales: FICHA.manuales,
      },
    }
    renderFicha({ data })
    expect(screen.getByText(/no se detect[óo] un ORCID válido/i)).toBeInTheDocument()
    expect(screen.getByText(/escr[ií]balo a mano/i)).toBeInTheDocument()
  })

  it('el ORCID no bloquea «Preparar depósito»', async () => {
    renderFicha()
    await waitFor(() => expect(screen.getByRole('button', { name: /Preparar depósito/i })).not.toBeDisabled())
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
    renderFicha()
    await waitFor(() =>
      expect(screen.getByText(/Configuración completa/i)).toBeInTheDocument()
    )
    expect(screen.getByLabelText(/Nombre del responsable/i)).toHaveValue('Lic. Biblioteca FECyC')
  })

  it('si falta algo, dice exactamente qué corregir', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respuestaPapeleo({ nombre_responsable: '', plantilla_configurada: false })
    )
    renderFicha()
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
    renderFicha()
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
    renderFicha()
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
    renderFicha()
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
    renderFicha()
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
    renderFicha()
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
    renderFicha()
    await waitFor(() =>
      expect(screen.getByText(/Se recuperó la ficha guardada en este navegador/i)).toBeInTheDocument()
    )
    expect(screen.getByLabelText(/ORCID del asesor/i)).toHaveValue('0000-0000-1111-2222')
  })
})
