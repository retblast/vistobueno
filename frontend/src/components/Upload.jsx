import { useState, useCallback, useRef } from 'react'

// Estructura base: pantalla de carga con drag & drop.
// Replica el mockup mockups/carga.html pero con interactividad real:
//  - Valida tipo (DOCX) y tamaño (≤ 10 MB, igual que el backend).
//  - Llama al endpoint POST /validar del backend (Integrante 1).
//  - Errores HTTP con detalle JSON → se muestran al usuario (sin mock).
//  - Sin conexión / proxy sin backend → mock como modo demo (avisado en Report).
function Upload({ onValidated, apiUrl }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragActivo, setDragActivo] = useState(false)
  const inputRef = useRef(null)

  const MAX_BYTES = 10 * 1024 * 1024 // 10 MB, igual que el backend
  const acceptedTypes = [
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]

  const validarArchivo = (selected) => {
    if (!selected) return false
    if (!acceptedTypes.includes(selected.type) && !selected.name?.toLowerCase().endsWith('.docx')) {
      setError('El archivo no es .docx. Selecciona un documento de Word.')
      return false
    }
    if (selected.size > MAX_BYTES) {
      setError(`El archivo pesa ${(selected.size / 1024 / 1024).toFixed(1)} MB. El límite es de 10 MB.`)
      return false
    }
    return true
  }

  const handleFiles = useCallback((files) => {
    if (files && files[0]) {
      if (validarArchivo(files[0])) {
        setError(null)
        setFile(files[0])
      } else {
        setFile(null)
      }
    }
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragActivo(false)
    handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  const onDragOver = useCallback((e) => {
    e.preventDefault()
    if (!loading) setDragActivo(true)
  }, [loading])

  const onDragLeave = useCallback(() => {
    setDragActivo(false)
  }, [])

  const openPicker = useCallback(() => {
    if (!loading) inputRef.current?.click()
  }, [loading])

  const onDropzoneClick = useCallback((e) => {
    // Solo abrir el selector si el click no fue en el label/botón (evita doble apertura)
    if (e.target.closest('label') || e.target.closest('button')) return
    openPicker()
  }, [openPicker])

  const quitarArchivo = useCallback(() => {
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }, [])

  const cerrarError = useCallback(() => setError(null), [])

  // Fallback a reporte mock SOLO cuando no hay respuesta útil del backend
  // (error de red o proxy sin cuerpo JSON). Modo demo, siempre avisado en Report.
  const cargarMock = async (motivo) => {
    const { MOCK_REPORT } = await import('../mocks')
    onValidated({
      ...MOCK_REPORT,
      __mock: true,
      __mockMotivo: `${motivo} Este es un reporte de ejemplo; el resultado real podría diferir.`,
    })
  }

  const validate = async () => {
    if (!file || loading) return
    setLoading(true)
    setError(null)
    try {
      let res
      try {
        const form = new FormData()
        form.append('archivo', file)
        res = await fetch(`${apiUrl}/validar`, {
          method: 'POST',
          body: form,
        })
      } catch {
        // Error de red (backend caído, sin proxy, etc.) → mock como modo demo
        await cargarMock('No se pudo conectar con el servidor de validación.')
        return
      }

      if (res.ok) {
        try {
          const data = await res.json()
          onValidated(data)
        } catch {
          await cargarMock('El servidor devolvió una respuesta inválida.')
        }
        return
      }

      // HTTP != 2xx: si hay cuerpo JSON (detail/message), mostrar el error real y NO mock
      let detail = null
      try {
        const errBody = await res.json()
        detail = errBody?.detail ?? errBody?.message ?? null
        if (Array.isArray(detail)) {
          detail = detail
            .map((d) => (typeof d === 'string' ? d : d?.msg || JSON.stringify(d)))
            .join('; ')
        }
      } catch {
        detail = null
      }

      if (detail) {
        // Respuesta HTTP con detalle del backend (413/415/422/500, etc.)
        setError(`El servidor rechazó la validación (HTTP ${res.status}): ${detail}`)
        return
      }

      // HTTP sin JSON útil (p.ej. proxy 500 con body vacío cuando el backend está caído)
      // → fallback a mock como modo demo
      await cargarMock(`El servidor respondió HTTP ${res.status} sin detalle.`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <div className="card">
        <h2>Sube tu tesis</h2>
        <p className="intro">
          Adjunta tu documento en formato <strong>DOCX</strong> y
          recibe un reporte automático de cumplimiento con las directivas de formato de la UNT.
        </p>

        <div
          className={`dropzone ${dragActivo ? 'drag' : ''} ${loading ? 'loading' : ''}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={onDropzoneClick}
        >
          <div className="icono" aria-hidden="true">📄</div>
          <div className="txt-principal">{loading ? 'Validando tu documento…' : 'Arrastra tu archivo aquí'}</div>
          <div className="txt-sec">o selecciónalo desde tu computadora</div>

          <input
            type="file"
            id="file-input"
            ref={inputRef}
            accept=".docx"
            disabled={loading}
            onChange={(e) => handleFiles(e.target.files)}
          />
          <label htmlFor="file-input" className={`btn-select ${loading ? 'disabled' : ''}`}>
            {loading ? 'Validando…' : 'Seleccionar archivo'}
          </label>

          <div className="nota-formatos">
            Formato permitido: .docx · Tamaño máximo: 10 MB
          </div>
        </div>

        {file && (
          <div className="archivo">
            <div className="fila">
              <div className="meta">
                <span className="ext">{file.name.split('.').pop().toUpperCase()}</span>
                <div>
                  <div className="nombre">{file.name}</div>
                  <div className="detalle">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                </div>
              </div>
              <div className="acciones-archivo">
                <button
                  className="btn-quitar"
                  onClick={quitarArchivo}
                  disabled={loading}
                  title="Quitar archivo"
                  aria-label="Quitar archivo seleccionado"
                >
                  ✕
                </button>
                <button className="btn-validar" onClick={validate} disabled={loading}>
                  {loading ? (
                    <><span className="spinner" aria-hidden="true"></span> Validando…</>
                  ) : (
                    'Validar ✦'
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="aviso error" role="alert">
            <div className="aviso-fila">
              <strong>No se pudo validar.</strong>
              <button className="aviso-cerrar" onClick={cerrarError} aria-label="Cerrar aviso">✕</button>
            </div>
            <span className="ejemplos">{error}</span>
          </div>
        )}
      </div>
    </main>
  )
}

export default Upload
