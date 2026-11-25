// Tests de componente del envío con Enter (Upload).
// Runner: vitest con jsdom + @testing-library/react (`npm test`).
// Cubren la observación N1 de la revisión del PR #62: la promesa de Enter
// tiene que ser precisa según el estado del formulario.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Upload from './Upload.jsx'

const ARCHIVO_DOCX = new File(
  ['contenido'],
  'tesis.docx',
  { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }
)

function seleccionarArchivo(container) {
  const input = container.querySelector('#file-input')
  fireEvent.change(input, { target: { files: [ARCHIVO_DOCX] } })
}

describe('Upload — envío con Enter', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        semaforo: 'verde',
        resultados: [],
        resumen: { total: 0, fallidos_error: 0, fallidos_warning: 0 },
        notificado: false,
        deposito: { estado: 'no_solicitado' },
      }),
    })
  })

  it('envía la validación al pulsar Enter con el formulario completo', async () => {
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)

    const correo = screen.getByLabelText(/Correo del estudiante/i)
    fireEvent.change(correo, { target: { value: 'estudiante@correo.unt.edu.pe' } })

    // jsdom no implementa el envío implícito del navegador (Enter en un
    // <form>); se dispara el evento submit, que es lo que el navegador
    // genera en ese caso.
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1))
    expect(globalThis.fetch.mock.calls[0][0]).toContain('/validar')
    expect(globalThis.fetch.mock.calls[0][1].method).toBe('POST')
  })

  it('sin archivo, Enter lleva el foco a la dropzone (botón deshabilitado)', () => {
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    const correo = screen.getByLabelText(/Correo del estudiante/i)

    fireEvent.keyDown(correo, { key: 'Enter' })

    const dropzone = container.querySelector('.dropzone')
    expect(dropzone).toHaveFocus()
    expect(screen.getByRole('button', { name: /Validar documento/i })).toBeDisabled()
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('con correo inválido, Enter lleva el foco al campo de correo', () => {
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)

    const correo = screen.getByLabelText(/Correo del estudiante/i)
    fireEvent.change(correo, { target: { value: 'correo-invalido' } })
    fireEvent.keyDown(correo, { key: 'Enter' })

    expect(correo).toHaveFocus()
    expect(screen.getByRole('button', { name: /Validar documento/i })).toBeDisabled()
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('el botón de validar es type="submit" y el de quitar archivo es type="button"', () => {
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)

    expect(screen.getByRole('button', { name: /Validar documento/i })).toHaveAttribute('type', 'submit')
    expect(screen.getByRole('button', { name: /Quitar archivo/i })).toHaveAttribute('type', 'button')
  })

  // Regresión F1 (segunda revisión del PR #62): el manejador de Enter del
  // formulario interceptaba cualquier Enter, y con `preventDefault()` anulaba
  // la activación por defecto de los botones y de la casilla.
  //
  // jsdom no implementa la activación implícita de un control con Enter, así
  // que el helper emula lo que hace el navegador: si la aplicación cancela
  // el evento, el control NO se activa; si no lo cancela, se activa.
  const pulsarEnterComoElNavegador = (elemento) => {
    const evento = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    elemento.dispatchEvent(evento)
    const cancelado = evento.defaultPrevented
    if (!cancelado && elemento.tagName === 'BUTTON') fireEvent.click(elemento)
    return cancelado
  }

  it('F1: Enter sobre «Quitar archivo» quita el archivo (no se intercepta)', () => {
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)

    const correo = screen.getByLabelText(/Correo del estudiante/i)
    fireEvent.change(correo, { target: { value: 'correo-invalido' } })

    const quitar = screen.getByRole('button', { name: /Quitar archivo/i })
    const cancelado = pulsarEnterComoElNavegador(quitar)

    expect(cancelado).toBe(false)
    // El archivo se quitó: vuelve a la zona de carga en estado vacío.
    expect(screen.getByText('Arrastre aquí su documento .docx')).toBeInTheDocument()
  })

  it('F1: Enter sobre la casilla «Enviar observaciones» no se intercepta', () => {
    render(<Upload onValidated={() => {}} apiUrl="" />)
    const casilla = screen.getByRole('checkbox', { name: /Enviar observaciones por correo/i })

    const cancelado = pulsarEnterComoElNavegador(casilla)

    expect(cancelado).toBe(false)
  })

  it('F1: Enter sobre el campo de correo con el formulario incompleto sí se intercepta', () => {
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    const correo = screen.getByLabelText(/Correo del estudiante/i)

    const cancelado = pulsarEnterComoElNavegador(correo)

    expect(cancelado).toBe(true)
    expect(container.querySelector('.dropzone')).toHaveFocus()
  })
})

// ── Parte 1 de Arreglos.txt v9: timeout del navegador y 429 ─────────────
// El backend limita las validaciones seguidas y responde 429 con la cabecera
// `Retry-After` (en segundos). La espera real puede ser de varios minutos:
// la pantalla debe decir cuánto falta, deshabilitar el reintento hasta la
// hora indicada, conservar el archivo y el correo, y no reintentar sola.
describe('Upload — límite de peticiones (429) y timeout', () => {
  const respuesta429 = (retryAfter, detalle) => ({
    ok: false,
    status: 429,
    headers: {
      get: (nombre) => (nombre.toLowerCase() === 'retry-after' ? retryAfter : null),
    },
    json: async () => ({ detail: detalle }),
  })

  const escribirCorreo = (container, valor = 'estudiante@correo.unt.edu.pe') => {
    const correo = screen.getByLabelText(/Correo del estudiante/i)
    fireEvent.change(correo, { target: { value: valor } })
  }

  afterEach(() => {
    vi.useRealTimers()
  })

  it('un 429 con espera larga muestra la espera real y la hora de reintento', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      respuesta429('223', 'Demasiadas peticiones de validación seguidas.')
    )
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    escribirCorreo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/HTTP 429/i)).toBeInTheDocument())
    // El mensaje del servidor se conserva tal cual.
    expect(screen.getByText(/Demasiadas peticiones de validación seguidas\./i)).toBeInTheDocument()
    // La espera real y la hora exacta: 223 s = 3 min 43 s.
    expect(screen.getByText(/Faltan 3 min 43 s\. Podrá reintentar a las \d{2}:\d{2}\./)).toBeInTheDocument()
    // Mientras hay espera, el botón de validar queda deshabilitado.
    expect(screen.getByRole('button', { name: /Validar documento/i })).toBeDisabled()
  })

  it('el 429 conserva el archivo y el correo ya escritos', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(respuesta429('223', 'Espere.'))
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    escribirCorreo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/HTTP 429/i)).toBeInTheDocument())
    expect(screen.getByText('tesis.docx')).toBeInTheDocument()
    expect(screen.getByLabelText(/Correo del estudiante/i)).toHaveValue('estudiante@correo.unt.edu.pe')
  })

  it('el reintento es manual: no hay segunda petición automática', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(respuesta429('223', 'Espere.'))
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/HTTP 429/i)).toBeInTheDocument())
    // Ni una petición más: el reintento lo decide el operador.
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('cuando termina la cuenta el botón se habilita y avisa que ya se puede reintentar', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    globalThis.fetch = vi.fn().mockResolvedValue(respuesta429('3', 'Espere.'))
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/HTTP 429/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Validar documento/i })).toBeDisabled()

    // Pasa la cuenta (3 s).
    await vi.advanceTimersByTimeAsync(3100)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Validar documento/i })).not.toBeDisabled()
    )
    expect(screen.getByText(/Ya puede reintentar la validación/i)).toBeInTheDocument()
  })

  it('el reintento manual conserva el archivo y no genera peticiones paralelas', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let resolver = null
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(respuesta429('2', 'Espere.'))
      .mockImplementationOnce(
        () => new Promise((resolve) => {
          resolver = resolve
        })
      )
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/HTTP 429/i)).toBeInTheDocument())
    await vi.advanceTimersByTimeAsync(2100)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Validar documento/i })).not.toBeDisabled()
    )

    fireEvent.submit(container.querySelector('form'))
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2))
    // Mientras corre la validación, el botón queda deshabilitado: no hay
    // peticiones paralelas.
    const boton = container.querySelector('button[type="submit"]')
    expect(boton).toBeDisabled()
    expect(boton.textContent).toMatch(/Validando/i)
    // El archivo sigue seleccionado para el reintento.
    expect(screen.getByText('tesis.docx')).toBeInTheDocument()

    resolver({ ok: true, status: 200, json: async () => ({ semaforo: 'verde', resultados: [] }) })
  })

  it('sin Retry-After se muestra el mensaje del servidor y no se inventa un plazo', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(respuesta429(null, 'Espere un momento.'))
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/HTTP 429/i)).toBeInTheDocument())
    expect(screen.getByText(/Espere un momento\./i)).toBeInTheDocument()
    expect(screen.queryByText(/Podrá reintentar a las/i)).not.toBeInTheDocument()
    // Sin espera activa, el operador puede reintentar cuando quiera.
    expect(screen.getByRole('button', { name: /Validar documento/i })).not.toBeDisabled()
  })

  it('el timeout del navegador avisa que pasaron 2 minutos y conserva el archivo', async () => {
    const errorAbort = new Error('aborted')
    errorAbort.name = 'AbortError'
    globalThis.fetch = vi.fn().mockRejectedValue(errorAbort)
    const { container } = render(<Upload onValidated={() => {}} apiUrl="" />)
    seleccionarArchivo(container)
    fireEvent.submit(container.querySelector('form'))

    await waitFor(() => expect(screen.getByText(/El servidor tardó demasiado\./i)).toBeInTheDocument())
    expect(screen.getByText(/superó los 2 minutos sin respuesta/i)).toBeInTheDocument()
    expect(screen.getByText('tesis.docx')).toBeInTheDocument()
  })
})
