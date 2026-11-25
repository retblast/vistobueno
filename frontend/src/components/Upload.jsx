import { useState, useCallback, useEffect, useRef } from 'react'
import {
  hashDeArchivo,
  leerRetryAfter,
  mensajeEspera,
  textoEsperaHasta,
  TIMEOUT_VALIDACION_MINUTOS,
} from '../upload'

// Estructura base: pantalla de carga con drag & drop.
// Replica el mockup mockups/carga.html pero con interactividad real:
//  - Valida tipo (DOCX) y tamaño (≤ 10 MB, igual que el backend).
//  - Llama al endpoint POST /validar del backend (Integrante 1).
//  - Errores HTTP con detalle JSON → se muestran al usuario (sin mock).
//  - Sin conexión / proxy sin backend → mock como modo demo (avisado en Report).
// Constantes y validación de archivo a nivel de módulo (sin dependencia de
// estado): así handleFiles puede ser useCallback([]) sin violar exhaustive-deps.
const MAX_BYTES = 10 * 1024 * 1024 // 10 MB, igual que el backend
// Sin respuesta a los 2 minutos se aborta la petición y se avisa (fetch no
// tiene timeout por defecto: sin esto el spinner quedaría girando para siempre
// si el backend cuelga). Con una tesis real la validación tarda más de 30 s
// y el navegador cortaba la petición aunque el servidor siguiera trabajando:
// el timeout del navegador NO cancela el trabajo del servidor, solo deja de
// esperarlo (el operador puede reintentar y el backend responde lo que tenga).
const TIMEOUT_VALIDACION_MS = TIMEOUT_VALIDACION_MINUTOS * 60 * 1000
// Intervalo de refresco de la cuenta regresiva del 429 (1 s).
const INTERVALO_ESPERA_MS = 1000
const acceptedTypes = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
]
// Validación de formato de correo en el cliente para evitar un 422 innecesario.
// Si llega a llegarse con formato inválido, el backend responde 422 con
// detail en español que el banner actual ya muestra (sin cambios).
const esCorreoValido = (c) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c)

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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // Espera activa por límite de peticiones (HTTP 429 con `Retry-After`).
  // { restante: segundos, momentoHasta: epoch ms }. Mientras exista, el
  // botón «Validar documento» queda deshabilitado: el reintento es siempre
  // manual y nunca antes de la hora que indique el servidor.
  const [espera, setEspera] = useState(null)
  const [reintentoDisponible, setReintentoDisponible] = useState(false)
  const [dragActivo, setDragActivo] = useState(false)
  const inputRef = useRef(null)
  const zonaRef = useRef(null)
  const correoRef = useRef(null)
  // Guard síncrono de validación en curso: `loading` (estado) llega tarde para
  // un doble clic en el mismo tick y no cubre el drop sobre la zona.
  const cargandoRef = useRef(false)
  // Momento límite de la espera por 429 (epoch ms). Vive en un ref para que
  // el intervalo de la cuenta regresiva no se reinicie en cada segundo.
  const esperaRef = useRef(null)
  // Identidad del archivo por contenido (hash SHA-256): viaja al reporte
  // para que el resguardo de la ficha no se confunda entre dos archivos con
  // el mismo nombre.
  const identidadRef = useRef(null)

  // Cuenta regresiva del 429: cada segundo descuenta lo que falta. Cuando
  // llega a cero, la espera se cierra y se avisa que ya se puede reintentar
  // (el reintento lo decide el operador: no hay reintento automático).
  const esperaActiva = Boolean(espera)
  useEffect(() => {
    if (!esperaActiva) return undefined
    const timer = setInterval(() => {
      const actual = esperaRef.current
      if (!actual) return
      const restante = Math.max(0, Math.ceil((actual.momentoHasta - Date.now()) / 1000))
      if (restante === 0) {
        esperaRef.current = null
        setEspera(null)
        setReintentoDisponible(true)
      } else {
        setEspera({ ...actual, restante })
      }
    }, INTERVALO_ESPERA_MS)
    return () => clearInterval(timer)
  }, [esperaActiva])

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
        // Identidad del documento por contenido (hash). Se calcula en
        // segundo plano: si el navegador no lo permite, se usa nombre+tamaño.
        identidadRef.current = { nombre: files[0].name, tamano: files[0].size, hash: '' }
        hashDeArchivo(files[0]).then((hash) => {
          if (identidadRef.current?.nombre === files[0].name) {
            identidadRef.current = { ...identidadRef.current, hash }
          }
        })
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

  // Fallback a reporte mock SOLO en desarrollo (modo demo, siempre avisado).
  // Decisión AUD-18 (2026-10-28): en producción un reporte de ejemplo puede
  // confundir al operador (parece un resultado real), así que el build de
  // producción muestra el error verdadero y deja reintentar.
  const fallbackSinBackend = async (motivo) => {
    if (import.meta.env.DEV) {
      const { MOCK_REPORT } = await import('../mocks')
      onValidated(
        {
          ...MOCK_REPORT,
          __mock: true,
          __mockMotivo: `${motivo} Este es un reporte de ejemplo; el resultado real podría diferir.`,
        },
        identidadRef.current
      )
      return
    }
    setError({
      titulo: 'No se pudo obtener el reporte del servidor.',
      texto: `${motivo} Intente nuevamente; si el problema persiste, consulte al administrador.`,
      tipo: 'servidor',
    })
  }

  const validate = async () => {
    if (!file || cargandoRef.current) return
    if (esperaRef.current) return
    cargandoRef.current = true
    setLoading(true)
    setError(null)
    setReintentoDisponible(false)
    // Igual que el backend: el correo viaja sin espacios extremos.
    const correoLimpio = (correo || '').trim()
    try {
      let res
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_VALIDACION_MS)
      try {
        const form = new FormData()
        form.append('archivo', file)
        // Correo del estudiante (opcional): viaja en la MISMA solicitud POST /validar.
        if (correoLimpio && esCorreoValido(correoLimpio)) form.append('correo', correoLimpio)
        // Opt-in de envío: "true"/"1" solo si el operador marcó la casilla
        // (el backend lo interpreta como default: false).
        if (notificar && correoLimpio && esCorreoValido(correoLimpio)) form.append('notificar', 'true')
        res = await fetch(`${apiUrl}/validar`, {
          method: 'POST',
          body: form,
          signal: controller.signal,
        })
      } catch (e) {
        if (e?.name === 'AbortError') {
          // superó el timeout: el servidor puede estar vivo pero colgado.
          // NO cae al mock (sería mentira decir "no se pudo conectar").
          // Abortar la espera del navegador NO cancela el trabajo del
          // servidor: solo deja de esperarlo.
          setError({
            titulo: 'El servidor tardó demasiado.',
            texto:
              `La validación superó los ${TIMEOUT_VALIDACION_MINUTOS} minutos sin respuesta. ` +
              'El servidor puede seguir trabajando: esperar en el navegador no cancela la validación. ' +
              'Intente nuevamente o consulte al administrador.',
            tipo: 'servidor',
          })
          return
        }
        // Error de red (backend caído, sin proxy, etc.) → mock como modo demo
        await fallbackSinBackend('No se pudo conectar con el servidor de validación.')
        return
      } finally {
        clearTimeout(timeoutId)
      }

      if (res.ok) {
        try {
          const data = await res.json()
          onValidated(data, identidadRef.current)
        } catch {
          await fallbackSinBackend('El servidor devolvió una respuesta inválida.')
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

      // 429: el servidor limitó las validaciones seguidas y dice CUÁNTO
      // falta con la cabecera `Retry-After` (en segundos). La espera real
      // puede ser de varios minutos, así que se muestra cuánto falta y a qué
      // hora se puede reintentar; el botón queda deshabilitado hasta entonces
      // y el reintento es siempre manual. El archivo y el correo ya
      // seleccionados se conservan.
      if (res.status === 429) {
        const retryAfter = leerRetryAfter(res)
        if (retryAfter !== null) {
          const info = mensajeEspera(retryAfter)
          esperaRef.current = { restante: info.restante, momentoHasta: info.momentoHasta }
          setEspera({ restante: info.restante, momentoHasta: info.momentoHasta })
          setReintentoDisponible(false)
          setError({
            titulo: 'El servidor pidió esperar antes de reintentar (HTTP 429).',
            texto: detail ?? 'El servidor limitó las validaciones seguidas.',
            tipo: 'servidor',
          })
        } else {
          // Sin `Retry-After` no se inventa ningún plazo: se muestra lo que
          // diga el servidor y el reintento queda disponible de inmediato.
          setError({
            titulo: 'El servidor pidió esperar antes de reintentar (HTTP 429).',
            texto: detail ?? 'El servidor limitó las validaciones seguidas. Intente nuevamente.',
            tipo: 'servidor',
          })
        }
        return
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
      await fallbackSinBackend(`El servidor respondió HTTP ${res.status} sin detalle.`)
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
      : espera
        ? 'Espere a que termine la cuenta para volver a validar.'
        : null

  // Enter-to-submit: el card es un <form>, así Enter en el correo (o en
  // cualquier campo) dispara el envío implícito del navegador, que este
  // onSubmit traduce a `validate()`, como espera el operador. `noValidate`
  // deja la validación en nuestras reglas (con sus mensajes aria-live); la
  // burbuja nativa del navegador duplicaría el aviso y no sería accesible.
  // Enter/Space sobre la dropzone no llega aquí: su onKeyDown hace
  // preventDefault() y abre el selector de archivos.
  const onFormSubmit = (e) => {
    e.preventDefault()
    validate()
  }

  // El botón «Validar documento» queda deshabilitado mientras falte el
  // archivo .docx o el correo sea inválido; en ese estado el navegador no
  // dispara el envío implícito con Enter y la pulsación se perdería. En vez
  // de eso, Enter en el campo de correo lleva el foco al elemento pendiente
  // (la dropzone o el propio campo), donde ya está el aviso correspondiente.
  //
  // La intercepción se limita al campo de correo a propósito: si se
  // interceptara cualquier Enter del formulario, se anularía la activación
  // por defecto de los botones («Quitar archivo», «Cerrar aviso») y de la
  // casilla «Enviar observaciones» (regresión detectada en la segunda
  // revisión del PR #62, hallazgo F1).
  const onFormKeyDown = (e) => {
    if (e.key !== 'Enter') return
    if (e.target !== correoRef.current) return
    if (file && !(correo && correoError)) return
    e.preventDefault()
    if (!file) zonaRef.current?.focus()
    else correoRef.current?.focus()
  }

  return (
    <main>
      <form className="card" noValidate onSubmit={onFormSubmit} onKeyDown={onFormKeyDown}>
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
            ref={correoRef}
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
                  type="button"
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
            type="submit"
            className="btn-validar"
            disabled={loading || !file || !!(correo && correoError) || Boolean(espera)}
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
              <button type="button" className="aviso-cerrar" onClick={cerrarError} aria-label="Cerrar aviso">✕</button>
            </div>
            <span className="ejemplos">{error.texto}</span>
          </div>
        )}
        {espera && (
          <div className="aviso warn" role="status" aria-live="polite">
            <span className="ejemplos">{textoEsperaHasta(espera.momentoHasta)}</span>
          </div>
        )}
        {reintentoDisponible && !espera && (
          <div className="aviso ok" role="status">
            <span className="ejemplos">Ya puede reintentar la validación con el mismo archivo.</span>
          </div>
        )}
      </form>
    </main>
  )
}

export default Upload
