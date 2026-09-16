import { useState, useCallback } from 'react'

// Estructura base: pantalla de carga con drag & drop.
// Replica el mockup mockups/carga.html pero con interactividad real:
//  - Valida tipo (DOCX/PDF) y tamaño (≤ 25 MB).
//  - Llama al endpoint POST /validar del backend (Integrante 1).
//  - Si la API no está disponible, usa datos mock para visualizar el reporte.
function Upload({ onValidated, apiUrl }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragActivo, setDragActivo] = useState(false)

  const acceptedTypes = [
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/pdf'
  ]

  const validarArchivo = (selected) => {
    if (!selected) return false
    if (!acceptedTypes.includes(selected.type)) {
      setError('Formato no soportado. Debes subir un archivo DOCX o PDF.')
      return false
    }
    if (selected.size > 25 * 1024 * 1024) {
      setError('El archivo excede el límite de 25 MB.')
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
    setDragActivo(true)
  }, [])

  const onDragLeave = useCallback(() => {
    setDragActivo(false)
  }, [])

  const validate = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('archivo', file)
      const res = await fetch(`${apiUrl}/validar`, {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        throw new Error(`Error del servidor: ${res.status}`)
      }
      const data = await res.json()
      onValidated(data)
    } catch (e) {
      // Si la API no está disponible (Integrante 1 aún no la tiene),
      // usamos datos mock del mockup para visualizar el componente de reporte.
      console.warn('API no disponible, usando datos mock:', e.message)
      const { MOCK_REPORT } = await import('../App')
      onValidated(MOCK_REPORT)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <div className="card">
        <h2>Sube tu tesis</h2>
        <p className="intro">
          Adjunta tu documento en formato <strong>DOCX</strong> o <strong>PDF</strong> y
          recibe un reporte automático de cumplimiento con las directivas de formato de la UNT.
        </p>

        <div
          className={`dropzone ${dragActivo ? 'drag' : ''}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
        >
          <div className="icono">📄</div>
          <div className="txt-principal">Arrastra tu archivo aquí</div>
          <div className="txt-sec">o selecciónalo desde tu computadora</div>

          <input
            type="file"
            id="file-input"
            accept=".docx,.pdf"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <label htmlFor="file-input" className="btn-select">Seleccionar archivo</label>

          <div className="nota-formatos">
            Formatos permitidos: .docx, .pdf · Tamaño máximo: 25 MB
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
              <button className="btn-validar" onClick={validate} disabled={loading}>
                {loading ? 'Validando...' : 'Validar ✦'}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="aviso error">
            <strong>No pudimos procesar tu archivo.</strong>
            <span className="ejemplos">{error}</span>
          </div>
        )}
      </div>
    </main>
  )
}

export default Upload