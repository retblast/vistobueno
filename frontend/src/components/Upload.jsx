import { useState, useCallback, useEffect, useRef } from 'react'

// Estructura base: pantalla de carga con drag & drop.
// Replica el mockup mockups/carga.html pero con interactividad real:
//  - Valida tipo (DOCX) y tamaño (≤ 10 MB, igual que el backend).
//  - Llama al endpoint POST /validar del backend (Integrante 1).
//  - Errores HTTP con detalle JSON → se muestran al usuario (sin mock).
//  - Sin conexión / proxy sin backend → mock como modo demo (avisado en Report).
// Constantes y validación de archivo a nivel de módulo (sin dependencia de
// estado): así handleFiles puede ser useCallback([]) sin violar exhaustive-deps.
const MAX_BYTES = 10 * 1024 * 1024 // 10 MB, igual que el backend
// Sin respuesta a los 30 s se aborta la petición y se avisa (fetch no tiene
// timeout por defecto: sin esto el spinner quedaría girando para siempre si
// el backend cuelga). Coherente con el `curl -m` del script E2E.
const TIMEOUT_VALIDACION_MS = 30000
// Con depósito solicitado el backend puede tardar más tras validar: envío de
// notificación (SMTP, hasta 10 s) + alta en DSpace (httpx, 30 s por solicitud;
// ver validator/dspace.py). El cliente espera más para no abortar un depósito
// que el servidor terminaría igual (contrato v1.6).
const TIMEOUT_DEPOSITO_MS = 90000
const acceptedTypes = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
]
// Validación de formato de correo en el cliente para evitar un 422 innecesario.
// Si llega a llegarse con formato inválido, el backend responde 422 con
// detail en español que el banner actual ya muestra (sin cambios).
const esCorreoValido = (c) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c)

// Ficha de depósito (contrato v1.6): DSpace exige título y autor para crear
// el ítem; el resto es opcional. Sin esto el alta llegaría hasta DSpace y
// fallaría con un 422 que el operador vería tarde (en el badge de deposito).
// Exportada para su unit test (vitest): ver Upload.ficha.test.js.
export function fichaIncompleta(ficha) {
  const titulo = typeof ficha?.titulo === 'string' ? ficha.titulo.trim() : ''
  const autores = typeof ficha?.autores === 'string' ? ficha.autores.trim() : ''
  return titulo === '' || autores === ''
}

// Devuelve {titulo, texto} si el archivo no es válido; null si pasa.
const validarArchivo = (selected) => {
  if (!acceptedTypes.includes(selected.type) && !selected.name?.toLowerCase().endsWith('.docx')) {
    return { titulo: 'Archivo no compatible.', texto: 'El archivo no es .docx. Selecciona un documento de Word.' }
  }
  if (selected.size > MAX_BYTES) {
    return {
      titulo: 'Archivo demasiado grande.',
      texto: `El archivo pesa ${(selected.size / 1024 / 1024).toFixed(1)} MB. El límite es de 10 MB.`,
    }
  }
  return null
}

// Iconos SVG inline de la dropzone (sin emoji: se renderizan igual en todos
// los sistemas y en capturas headless).
const IconoArchivo = () => (
  <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </svg>
)
const IconoCheck = () => (
  <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor"
    strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="m8.5 12.5 2.5 2.5 4.5-5.5" />
  </svg>
)
const IconoCruz = () => (
  <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor"
    strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="m9 9 6 6M15 9l-6 6" />
  </svg>
)

function Upload({ onValidated, apiUrl }) {
  const [file, setFile] = useState(null)
  const [correo, setCorreo] = useState('')
  const [correoError, setCorreoError] = useState(null)
  // Opt-in de notificación (v1.3.0): solo envía `notificar=true` si el operador
  // lo pide explícitamente. Así el estudiante no recibe correo por validaciones
  // intermedias (el backend exige además correo válido, semáforo rojo y SMTP activo).
  const [notificar, setNotificar] = useState(false)
  // Ficha de depósito DSpace (contrato v1.6): opt-in del operador con los
  // metadatos del ítem. El backend solo deposita con semáforo verde y el
  // ítem queda en la cola de aprobación de la sede (nunca se publica directo).
  const [depositar, setDepositar] = useState(false)
  const [ficha, setFicha] = useState({ titulo: '', autores: '', asesor: '', resumen: '', palabrasClave: '' })
  const [fichaError, setFichaError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragActivo, setDragActivo] = useState(false)
  const inputRef = useRef(null)
  const zonaRef = useRef(null)
  // Guard síncrono de validación en curso: `loading` (estado) llega tarde para
  // un doble clic en el mismo tick y no cubre el drop sobre la zona.
  const cargandoRef = useRef(false)

  // Al volver del reporte ("Validar otro archivo") Upload se remonta de cero:
  // devuelve el foco a la dropzone (no lo pierde en <body>). En la carga inicial
  // de la app NO roba el foco.
  const primeraCarga = useRef(true)
  useEffect(() => {
    if (primeraCarga.current) {
      primeraCarga.current = false
      return
    }
    zonaRef.current?.focus()
  }, [])

  const onCorreoChange = (e) => {
    const v = e.target.value
    setCorreo(v)
    // El backend hace strip() antes de validar (api.py): validar el valor
    // limpio evita rechazar en el cliente correos que el servidor aceptaría
    // (p. ej. un espacio pegado al copiar/pegar).
    const limpio = v.trim()
    const invalido = limpio && !esCorreoValido(limpio)
    setCorreoError(invalido ? 'Formato de correo inválido (ej: correo@ejemplo.com).' : null)
    // Sin correo válido no hay notificación posible: se desmarca el opt-in
    // para que la petición no quede en un estado inconsistente.
    if (!limpio || invalido) setNotificar(false)
  }

  // Limpia el input para que re-elegir el MISMO archivo vuelva a disparar
  // onChange (el File ya guardado en el estado sigue siendo válido).
  // Ignora drop/cambio de archivo mientras valida: la selección no debe
  // cambiar bajo un resultado que corresponde al archivo anterior.
  const handleFiles = useCallback((files) => {
    if (cargandoRef.current) return
    if (files && files[0]) {
      const err = validarArchivo(files[0])
      if (err) {
        setError({ ...err, tipo: 'archivo' })
        setFile(null)
        // El error se muestra dentro de la dropzone: el foco va ahí para que
        // teclado/lector de pantalla queden en la zona que cambió.
        zonaRef.current?.focus()
      } else {
        setError(null)
        setFile(files[0])
      }
    }
    if (inputRef.current) inputRef.current.value = ''
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

  // Cerrar el error devuelve el foco a la dropzone (no lo pierde en <body>).
  const cerrarError = useCallback(() => {
    setError(null)
    zonaRef.current?.focus()
  }, [])

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
    if (!file || cargandoRef.current) return
    // Defensivo: el botón ya se deshabilita con la ficha incompleta, pero el
    // guard evita cualquier otra vía de envío con un depósito que fallaría
    // en DSpace por ítem sin título/autor.
    if (depositar && fichaIncompleta(ficha)) {
      setFichaError('Para depositar, complete al menos el título y los autores.')
      return
    }
    cargandoRef.current = true
    setLoading(true)
    setError(null)
    // Igual que el backend: el correo viaja sin espacios extremos.
    const correoLimpio = (correo || '').trim()
    try {
      let res
      // Con depósito solicitado el backend puede tardar mucho más (DSpace):
      // el timeout se amplía para esa solicitud (contrato v1.6).
      const depositoPedible = depositar && !fichaIncompleta(ficha)
      const timeoutMs = depositoPedible ? TIMEOUT_DEPOSITO_MS : TIMEOUT_VALIDACION_MS
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
      try {
        const form = new FormData()
        form.append('archivo', file)
        // Correo del estudiante (opcional): viaja en la MISMA solicitud POST /validar.
        if (correoLimpio && esCorreoValido(correoLimpio)) form.append('correo', correoLimpio)
        // Opt-in de envío: "true"/"1" solo si el operador marcó la casilla
        // (el backend lo interpreta como default: false).
        if (notificar && correoLimpio && esCorreoValido(correoLimpio)) form.append('notificar', 'true')
        // Ficha de depósito (v1.6): los metadatos solo viajan si se pidió
        // depositar; el backend ignora campos vacíos (solo envía con contenido).
        if (depositar && !fichaIncompleta(ficha)) {
          form.append('depositar', 'true')
          const limpio = (v) => v.trim()
          if (limpio(ficha.titulo)) form.append('titulo', limpio(ficha.titulo))
          if (limpio(ficha.autores)) form.append('autores', limpio(ficha.autores))
          if (limpio(ficha.asesor)) form.append('asesor', limpio(ficha.asesor))
          if (limpio(ficha.resumen)) form.append('resumen', limpio(ficha.resumen))
          if (limpio(ficha.palabrasClave)) form.append('palabras_clave', limpio(ficha.palabrasClave))
        }
        res = await fetch(`${apiUrl}/validar`, {
          method: 'POST',
          body: form,
          signal: controller.signal,
        })
      } catch (e) {
        if (e?.name === 'AbortError') {
          // superó el timeout: el servidor puede estar vivo pero colgado.
          // NO cae al mock (sería mentira decir "no se pudo conectar").
          setError({
            titulo: 'El servidor tardó demasiado.',
            texto: `La validación superó los ${Math.round(timeoutMs / 1000)} segundos sin respuesta. Intente nuevamente o consulte al administrador.`,
            tipo: 'servidor',
          })
          return
        }
        // Error de red (backend caído, sin proxy, etc.) → mock como modo demo
        await cargarMock('No se pudo conectar con el servidor de validación.')
        return
      } finally {
        clearTimeout(timeoutId)
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
        setError({
          titulo: `El servidor rechazó la validación (HTTP ${res.status}).`,
          texto: detail,
          tipo: 'servidor',
        })
        return
      }

      // HTTP sin JSON útil (p.ej. proxy 500 con body vacío cuando el backend está caído)
      // → fallback a mock como modo demo
      await cargarMock(`El servidor respondió HTTP ${res.status} sin detalle.`)
    } finally {
      cargandoRef.current = false
      setLoading(false)
    }
  }

  // Estado visual de la zona de carga (Arreglos.txt v7):
  //   vacío → seleccionado → procesando → (inválido | error)
  const estado = loading
    ? 'procesando'
    : error?.tipo === 'archivo'
      ? 'invalido'
      : error
        ? 'error'
        : file
          ? 'seleccionado'
          : 'vacio'

  // Texto principal/secundario de la dropzone según el estado.
  const estadoTextos = {
    vacio: ['Arrastre aquí su documento .docx', 'o selecciónelo desde su equipo'],
    seleccionado: ['Archivo listo para validar', 'Pulse «Validar documento» para continuar'],
    invalido: [error?.titulo ?? 'Archivo no válido', error?.texto ?? ''],
    procesando: ['Validando documento…', 'Esto puede tardar unos segundos'],
    error: ['No se pudo validar el documento', 'Revise el mensaje de detalle a continuación'],
  }
  const [estadoPrincipal, estadoSec] = estadoTextos[estado]

  const ayudaValidar = !file
    ? 'Seleccione un archivo .docx para habilitar la validación.'
    : correo && correoError
      ? 'Corrija el correo del estudiante o déjelo vacío.'
      : depositar && fichaIncompleta(ficha)
        ? 'Complete el título y los autores de la ficha, o desmarque «Depositar en el repositorio».'
        : null

  return (
    <main>
      <div className="card">
        <h2>Validar documento de tesis</h2>
        <p className="intro">
          Adjunte el documento en formato <strong>DOCX</strong> para
          obtener un reporte automático de cumplimiento con las directivas de formato de la UNT.
        </p>

        <div
          ref={zonaRef}
          className={`dropzone estado-${estado} ${dragActivo ? 'drag' : ''} ${loading ? 'loading' : ''}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={onDropzoneClick}
          role="button"
          tabIndex={loading ? -1 : 0}
          aria-busy={loading}
          aria-label={
            loading
              ? 'Validando documento'
              : estado === 'invalido'
                ? 'Archivo no válido: seleccione otro documento'
                : 'Zona de carga: arrastre un documento DOCX o pulse Enter para examinar su equipo'
          }
          aria-describedby="nota-formatos"
          onKeyDown={(e) => {
            if (loading) return
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              openPicker()
            }
          }}
        >
          <div className="icono" aria-hidden="true">
            {estado === 'procesando' ? (
              <span className="spinner spinner-grande" />
            ) : estado === 'seleccionado' ? (
              <IconoCheck />
            ) : estado === 'invalido' || estado === 'error' ? (
              <IconoCruz />
            ) : (
              <IconoArchivo />
            )}
          </div>
          {/* role=status anuncia cambios de estado; role=alert SOLO para error
              de archivo dentro de la zona (el error de servidor ya tiene su
              propio banner role=alert: con alert aquí se anunciaría dos veces) */}
          <div className="txt-principal" role={error && error.tipo !== 'servidor' ? 'alert' : 'status'}>
            {estadoPrincipal}
          </div>
          <div className="txt-sec">{estadoSec}</div>

          <input
            type="file"
            id="file-input"
            ref={inputRef}
            accept=".docx"
            disabled={loading}
            // El dropzone (role=button) ya es el control accesible por teclado:
            // este input oculto no debe ser una parada de tabulación invisible.
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <label htmlFor="file-input" className={`btn-select ${loading ? 'disabled' : ''}`}>
            {loading ? 'Validando…' : file ? 'Cambiar archivo' : 'Examinar archivos'}
          </label>

          <div className="nota-formatos" id="nota-formatos">
            Formato .docx · Tamaño máximo: 10 MB
          </div>
        </div>

        <div className="campo-correo">
          <label htmlFor="correo-estudiante">
            Correo del estudiante <span className="opcional">(opcional)</span>
          </label>
          <input
            type="email"
            id="correo-estudiante"
            placeholder="estudiante@correo.unt.edu.pe"
            value={correo}
            onChange={onCorreoChange}
            disabled={loading}
            aria-invalid={correoError ? 'true' : 'false'}
            aria-describedby={correoError ? 'correo-error' : 'correo-ayuda'}
          />
          {correoError ? (
            <div id="correo-error" className="campo-error" role="alert">{correoError}</div>
          ) : (
            <div id="correo-ayuda" className="campo-ayuda">
              El correo se usará únicamente para enviar el reporte de validación al estudiante.
            </div>
          )}
          <label
            className={`check-notificar ${!correo || correoError ? 'disabled' : ''}`}
            title={
              !correo || correoError
                ? 'Escriba un correo válido para habilitar el envío de observaciones'
                : undefined
            }
          >
            <input
              type="checkbox"
              checked={notificar}
              onChange={(e) => setNotificar(e.target.checked)}
              disabled={loading || !correo || !!correoError}
              aria-describedby="notificar-ayuda"
            />
            <span>Enviar observaciones por correo al estudiante</span>
          </label>
          <div id="notificar-ayuda" className="campo-ayuda">
            El envío solo se intenta si el documento tiene errores bloqueantes
            (semáforo rojo) y las notificaciones están habilitadas en el servidor.
          </div>
        </div>

        {/* Ficha de depósito DSpace (contrato v1.6): opt-in del operador.
            Solo se deposita con semáforo verde; el ítem queda en la cola de
            aprobación de la sede (nunca se publica directo). */}
        <details className="ficha-deposito" open={depositar}>
          <summary>Depositar en el repositorio digital (opcional)</summary>
          <div className="ficha-cuerpo">
            <label className={`check-depositar ${loading ? 'disabled' : ''}`}>
              <input
                type="checkbox"
                checked={depositar}
                onChange={(e) => {
                  setDepositar(e.target.checked)
                  if (!e.target.checked) setFichaError(null)
                }}
                disabled={loading}
                aria-describedby="depositar-ayuda"
              />
              <span>Depositar en el repositorio institucional (DSpace)</span>
            </label>
            <div id="depositar-ayuda" className="campo-ayuda">
              Solo se deposita si el resultado es verde; el ítem queda en la cola de
              aprobación de la sede. Título y autores son obligatorios para el ítem.
            </div>
            {depositar && (
              <div className="ficha-campos">
                <label htmlFor="ficha-titulo">
                  Título del trabajo <span className="req">(*)</span>
                </label>
                <input
                  type="text"
                  id="ficha-titulo"
                  value={ficha.titulo}
                  onChange={(e) => setFicha((f) => ({ ...f, titulo: e.target.value }))}
                  disabled={loading}
                  aria-invalid={fichaError ? 'true' : 'false'}
                  aria-describedby={fichaError ? 'ficha-error' : undefined}
                />
                <label htmlFor="ficha-autores">
                  Autor(es) <span className="req">(*)</span>
                </label>
                <textarea
                  id="ficha-autores"
                  rows="2"
                  placeholder="Separados por «;» o en líneas separadas"
                  value={ficha.autores}
                  onChange={(e) => setFicha((f) => ({ ...f, autores: e.target.value }))}
                  disabled={loading}
                  aria-invalid={fichaError ? 'true' : 'false'}
                  aria-describedby={fichaError ? 'ficha-error' : undefined}
                ></textarea>
                <label htmlFor="ficha-asesor">Asesor(a)</label>
                <input
                  type="text"
                  id="ficha-asesor"
                  value={ficha.asesor}
                  onChange={(e) => setFicha((f) => ({ ...f, asesor: e.target.value }))}
                  disabled={loading}
                />
                <label htmlFor="ficha-resumen">Resumen</label>
                <textarea
                  id="ficha-resumen"
                  rows="3"
                  value={ficha.resumen}
                  onChange={(e) => setFicha((f) => ({ ...f, resumen: e.target.value }))}
                  disabled={loading}
                ></textarea>
                <label htmlFor="ficha-palabras">Palabras clave</label>
                <input
                  type="text"
                  id="ficha-palabras"
                  placeholder="Separadas por «;» o comas"
                  value={ficha.palabrasClave}
                  onChange={(e) => setFicha((f) => ({ ...f, palabrasClave: e.target.value }))}
                  disabled={loading}
                />
                {fichaError ? (
                  <div id="ficha-error" className="campo-error" role="alert">{fichaError}</div>
                ) : (
                  <div className="campo-ayuda">
                    Los metadatos viajan solo con esta validación; el servidor
                    completa la fecha y la colección de la sede.
                  </div>
                )}
              </div>
            )}
          </div>
        </details>

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
              </div>
            </div>
          </div>
        )}

        {/* Acción principal: siempre en el mismo lugar y a todo el ancho
            (Arreglos.txt v7: «hacer más visible el botón Validar documento»). */}
        <div className="acciones-form">
          <button
            className="btn-validar"
            onClick={validate}
            disabled={loading || !file || !!(correo && correoError) || (depositar && fichaIncompleta(ficha))}
            aria-describedby={ayudaValidar ? 'validar-ayuda' : undefined}
          >
            {loading ? (
              <><span className="spinner" aria-hidden="true"></span> Validando…</>
            ) : (
              'Validar documento'
            )}
          </button>
          {ayudaValidar && (
            <p className="ayuda-accion" id="validar-ayuda">{ayudaValidar}</p>
          )}
        </div>

        {error && error.tipo === 'servidor' && (
          <div className="aviso error" role="alert">
            <div className="aviso-fila">
              <strong>{error.titulo}</strong>
              <button className="aviso-cerrar" onClick={cerrarError} aria-label="Cerrar aviso">✕</button>
            </div>
            <span className="ejemplos">{error.texto}</span>
          </div>
        )}
      </div>
    </main>
  )
}

export default Upload
