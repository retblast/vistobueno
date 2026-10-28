import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CAMPOS_EXTRAIDOS,
  CAMPOS_MANUALES,
  autoresDe,
  construirCuerpoConstancia,
  construirCuerpoFilaRegistro,
  debeMostrarFicha,
  descargarConstancia,
  establecerValor,
  faltantesDe,
  formatearTimestamp,
  generarFilaRegistro,
  listaDe,
  planDeDescargas,
  publicarFicha,
  sondearDeposito,
  tituloCoincide,
  tituloDe,
  valorDe,
} from '../ficha'

// Frecuencia del sondeo del buzón (handover S8 §2.3: ~3 s).
const INTERVALO_SONDEO_MS = 3000
// Clave del resguardo en localStorage: la ficha editada no debe perderse si el
// operador recarga la página a mitad del trámite.
const CLAVE_RESGUARDO = 'vb-ficha-deposito'

const cargarResguardo = (clave) => {
  try {
    const crudo = window.localStorage.getItem(CLAVE_RESGUARDO)
    if (!crudo) return null
    const guardado = JSON.parse(crudo)
    return guardado?.clave === clave ? guardado.ficha : null
  } catch {
    return null
  }
}

const guardarResguardo = (clave, ficha) => {
  try {
    window.localStorage.setItem(CLAVE_RESGUARDO, JSON.stringify({ clave, ficha }))
  } catch {
    // Sin localStorage (modo privado, cuota llena): la ficha sigue en memoria.
  }
}

const borrarResguardo = () => {
  try {
    window.localStorage.removeItem(CLAVE_RESGUARDO)
  } catch {
    // sin localStorage no hay resguardo que borrar
  }
}

function FichaDeposito({ data, apiUrl, onBack }) {
  const fichaInicial = data?.ficha_deposito
  // La clave del resguardo incluye el archivo: dos tesis no comparten ficha.
  const clave = useMemo(
    () => String(data?.metadatos?.archivo_nombre ?? 'ficha'),
    [data]
  )
  const [ficha, setFicha] = useState(() => {
    const guardada = cargarResguardo(clave)
    return guardada ?? fichaInicial
  })
  const [recuperada, setRecuperada] = useState(() => Boolean(cargarResguardo(clave)))
  const [fase, setFase] = useState('edicion') // edicion | esperando | recibido | listo
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [handle, setHandle] = useState('')
  const [tituloRecibido, setTituloRecibido] = useState(null)
  const [timestamp, setTimestamp] = useState('')
  const [filas, setFilas] = useState([])
  const [copiado, setCopiado] = useState(false)
  const timerRef = useRef(null)
  // Reporte ya rechazado por el operador (handle + timestamp). El buzón es
  // "última gana": sin esta marca la app volvería a mostrar el mismo reporte
  // descartado en cada sondeo. Cancelar la espera limpia la marca (el
  // operador puede así volver a ver el estado actual del buzón).
  const rechazadoRef = useRef(null)

  const autores = useMemo(() => autoresDe(ficha), [ficha])
  const plan = useMemo(() => planDeDescargas(ficha), [ficha])
  const faltantes = useMemo(() => faltantesDe(ficha), [ficha])

  // Resguardo de la ficha editada en cada cambio.
  useEffect(() => {
    if (!ficha) return
    guardarResguardo(clave, ficha)
  }, [clave, ficha])

  const editar = useCallback((campo, valor) => {
    setFicha((actual) => establecerValor(actual, campo, valor))
    // Al tomar la-edición el aviso de «ficha recuperada» ya no aporta nada.
    setRecuperada(false)
  }, [])

  // Sondeo del buzón mientras el panel de espera está abierto.
  useEffect(() => {
    if (fase !== 'esperando') return undefined
    let vivo = true
    const sondear = async () => {
      try {
        const resultado = await sondearDeposito(apiUrl)
        if (!vivo) return
        if (resultado.estado === 'esperando') return
        if (resultado.estado === 'error') {
          setError(resultado.mensaje)
          setFase('edicion')
          return
        }
        // Reporte ya rechazado por el operador: seguir esperando en silencio.
        const rechazado = rechazadoRef.current
        if (rechazado && rechazado.handle === resultado.handle && rechazado.timestamp === resultado.timestamp) {
          return
        }
        setHandle(resultado.handle || '')
        setTituloRecibido(resultado.titulo ?? null)
        setTimestamp(resultado.timestamp || '')
        setFase('recibido')
      } catch (e) {
        if (!vivo) return
        setError(`No se pudo consultar el buzón: ${e.message}`)
        setFase('edicion')
      }
    }
    sondear()
    timerRef.current = setInterval(sondear, INTERVALO_SONDEO_MS)
    return () => {
      vivo = false
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [apiUrl, fase])

  const preparar = async () => {
    if (faltantes.length > 0 || ocupado) return
    setOcupado(true)
    setError(null)
    setAviso(null)
    try {
      await publicarFicha(apiUrl, ficha)
      setFase('esperando')
      setAviso('Ficha publicada en el buzón. El userscript ya puede leerla.')
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupado(false)
    }
  }

  const cancelarEspera = () => {
    setFase('edicion')
    rechazadoRef.current = null
    setAviso('Se canceló la espera. La ficha sigue en el buzón (vigencia: 1 hora).')
  }

  // Cotejo del título: si no coincide, el operador decide (nunca a ciegas).
  const tituloCoincideConFicha = useMemo(
    () => tituloCoincide(tituloDe(ficha), tituloRecibido),
    [ficha, tituloRecibido]
  )

  const aceptar = () => {
    setFase('listo')
    setAviso('Depósito aceptado. Ya puede descargar la constancia y la fila del registro.')
  }

  const rechazar = () => {
    setFase('edicion')
    rechazadoRef.current = { handle, timestamp }
    setHandle('')
    setTituloRecibido(null)
    setTimestamp('')
    setError('El título recibido no coincide con la ficha. No se usó el handle: revise la ficha y prepare de nuevo.')
  }

  const descargar = async (indiceAutor, formato) => {
    if (ocupado) return
    setOcupado(true)
    setError(null)
    try {
      const cuerpo = construirCuerpoConstancia(ficha, handle, timestamp, indiceAutor)
      await descargarConstancia(apiUrl, cuerpo, formato)
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupado(false)
    }
  }

  const generarFila = async (formato) => {
    if (ocupado) return
    setOcupado(true)
    setError(null)
    try {
      const cuerpo = construirCuerpoFilaRegistro(ficha, handle, timestamp)
      const resultado = await generarFilaRegistro(apiUrl, cuerpo, formato)
      if (formato === 'json') setFilas(resultado)
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupado(false)
    }
  }

  const copiarFila = async () => {
    if (filas.length === 0) return
    try {
      await navigator.clipboard.writeText(filas.join('\n'))
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2500)
    } catch {
      setError('El navegador no permitió copiar al portapapeles: seleccione el texto de la fila.')
    }
  }

  // Al volver al reporte el resguardo deja de servir: el trámite de esta
  // ficha terminó y no conviene dejar datos personales (DNI, matrícula) en el
  // navegador más tiempo del necesario.
  const volverAlReporte = () => {
    borrarResguardo()
    onBack()
  }

  if (!debeMostrarFicha(data)) {
    return (
      <main>
        <div className="card">
          <h2 className="titulo">Ficha de depósito no disponible</h2>
          <p className="intro">
            La ficha de depósito solo existe cuando el documento cumple el formato (semáforo verde).
          </p>
          <div className="back-action">
            <button type="button" className="btn-validar" onClick={volverAlReporte}>Volver al reporte</button>
          </div>
        </div>
      </main>
    )
  }

  const momento = formatearTimestamp(timestamp)

  return (
    <main>
      <div className="card">
        <h2 className="titulo">Ficha de depósito</h2>
        <p className="intro">
          Revise los datos extraídos del documento y complete los que faltan. La app publica esta
          ficha en el buzón; el userscript rellena el formulario oficial de DSpace con ella. El
          archivo <strong>lo adjunta usted</strong> en el formulario oficial: la app no escribe en
          DSpace.
        </p>
        {recuperada && (
          <div className="aviso info" role="status">
            <span className="ejemplos">Se recuperó la ficha guardada en este navegador.</span>
          </div>
        )}
        {aviso && (
          <div className="aviso ok" role="status">
            <span className="ejemplos">{aviso}</span>
          </div>
        )}
        {error && (
          <div className="aviso error" role="alert">
            <div className="aviso-fila"><strong>No se pudo completar la operación.</strong></div>
            <span className="ejemplos">{error}</span>
          </div>
        )}
      </div>

      {/* ── Datos extraídos del documento ─────────────── */}
      <div className="card">
        <h3 className="subtitulo">Datos extraídos del documento</h3>
        <p className="intro">El motor detectó estos valores: corríjolos si hace falta.</p>
        <div className="ficha-campos">
          {CAMPOS_EXTRAIDOS.map(({ campo, etiqueta, tipo }) => {
            const valor = valorDe(ficha, campo)
            const detectado = ficha?.extraidos?.find((c) => c.campo === campo)?.detectado
            const id = `extraido-${campo}`
            const texto = Array.isArray(valor) ? valor.join('\n') : (valor ?? '')
            return (
              <div className="campo-ficha" key={campo}>
                <label htmlFor={id}>
                  {etiqueta}
                  {detectado === false && <span className="opcional"> (no detectado)</span>}
                </label>
                {tipo === 'area' ? (
                  <textarea
                    id={id}
                    rows={4}
                    value={texto}
                    onChange={(e) => editar(campo, e.target.value)}
                    disabled={fase === 'esperando'}
                  />
                ) : tipo === 'lista' ? (
                  <textarea
                    id={id}
                    rows={3}
                    placeholder="Un valor por línea"
                    value={texto}
                    onChange={(e) => editar(campo, e.target.value.split('\n'))}
                    disabled={fase === 'esperando'}
                  />
                ) : (
                  <input
                    id={id}
                    type="text"
                    value={texto}
                    onChange={(e) => editar(campo, e.target.value)}
                    disabled={fase === 'esperando'}
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Datos que escribe el operador ─────────────── */}
      <div className="card">
        <h3 className="subtitulo">Datos del operador</h3>
        <p className="intro">
          La matrícula y el DNI del autor se alinean por posición con los autores: una entrada por
          estudiante ({autores.length} autor{autores.length === 1 ? '' : 'es'} en la ficha).
        </p>
        <div className="ficha-campos">
          {CAMPOS_MANUALES.map(({ campo, etiqueta, tipo }) => {
            if (tipo === 'lista-autor') {
              const valores = listaDe(ficha, campo)
              return (
                <fieldset className="campo-ficha campo-autor" key={campo}>
                  <legend>{etiqueta}</legend>
                  {autores.length === 0 && (
                    <p className="campo-ayuda">Primero indique los autores en «Datos extraídos».</p>
                  )}
                  {autores.map((autor, indice) => (
                    <div className="campo-ficha-autor" key={`${campo}-${indice}`}>
                      <label htmlFor={`${campo}-${indice}`}>{autor || `Autor ${indice + 1}`}</label>
                      <input
                        id={`${campo}-${indice}`}
                        type="text"
                        value={valores[indice] ?? ''}
                        onChange={(e) => {
                          const copia = [...valores]
                          copia[indice] = e.target.value
                          editar(campo, copia)
                        }}
                        disabled={fase === 'esperando'}
                      />
                    </div>
                  ))}
                </fieldset>
              )
            }
            const id = `manual-${campo}`
            return (
              <div className="campo-ficha" key={campo}>
                <label htmlFor={id}>{etiqueta}</label>
                <input
                  id={id}
                  type="text"
                  value={valorDe(ficha, campo) ?? ''}
                  onChange={(e) => editar(campo, e.target.value)}
                  disabled={fase === 'esperando'}
                />
              </div>
            )
          })}
        </div>
        {faltantes.length > 0 && (
          <div className="aviso warn" role="status">
            <div className="aviso-fila"><strong>Faltan datos para preparar el depósito.</strong></div>
            <span className="ejemplos">{faltantes.join(' ')}</span>
          </div>
        )}
      </div>

      {/* ── Preparar depósito ─────────────────────────── */}
      <div className="card">
        <h3 className="subtitulo">Preparar depósito</h3>
        <p className="intro">
          Publica la ficha en el buzón para que el userscript la lea. El buzón tiene una sola ranura
          con vigencia de 1 hora: preparar de nuevo reemplaza la ficha anterior.
        </p>
        <div className="acciones-form">
          <button
            type="button"
            className="btn-validar"
            onClick={preparar}
            disabled={ocupado || fase === 'esperando' || faltantes.length > 0}
          >
            {fase === 'esperando' ? 'Esperando el depósito…' : 'Preparar depósito'}
          </button>
        </div>
        {fase === 'esperando' && (
          <div className="ficha-espera" role="status" aria-live="polite">
            <span className="spinner" aria-hidden="true"></span>
            <div>
              <strong>Esperando el depósito…</strong>
              <p className="campo-ayuda">
                Abra el formulario oficial de DSpace, adjunte el archivo y pulse «Depositar». El
                userscript rellena los metadatos y avisa por el buzón.
              </p>
            </div>
            <button type="button" className="btn-quitar" onClick={cancelarEspera}>
              Cancelar espera
            </button>
          </div>
        )}
      </div>

      {/* ── Depósito reportado y papeleo ───────────────── */}
      {(fase === 'recibido' || fase === 'listo') && (
        <div className="card">
          <h3 className="subtitulo">Depósito reportado</h3>
          {!tituloCoincideConFicha && fase === 'recibido' && (
            <div className="aviso warn" role="alert">
              <div className="aviso-fila">
                <strong>El título recibido no coincide con la ficha.</strong>
              </div>
              <span className="ejemplos">
                En la ficha: «{tituloDe(ficha) || '(sin título)'}». Recibido: «{tituloRecibido ?? '(sin título)'}».
                No se usará el handle hasta que usted lo acepte.
              </span>
            </div>
          )}
          <dl className="ficha-datos">
            <dt>Handle del ítem</dt>
            <dd><code>{handle || '(sin handle)'}</code></dd>
            <dt>Título recibido</dt>
            <dd>{tituloRecibido ?? '(sin título)'}</dd>
          </dl>
          <div className="ficha-campos">
            <div className="campo-ficha">
              <label htmlFor="ficha-timestamp">Fecha y hora del depósito (ISO 8601)</label>
              <input
                id="ficha-timestamp"
                type="text"
                value={timestamp}
                onChange={(e) => setTimestamp(e.target.value)}
              />
              <p className="campo-ayuda">
                Del clic «Depositar»: {momento.fecha} {momento.hora}. Edítelo si necesita corregirlo.
              </p>
            </div>
          </div>
          {fase === 'recibido' && (
            <div className="acciones-form">
              <button type="button" className="btn-validar" onClick={aceptar}>Aceptar depósito</button>
              <button type="button" className="btn-secundario" onClick={rechazar}>Rechazar y volver</button>
            </div>
          )}
        </div>
      )}

      {fase === 'listo' && (
        <div className="card">
          <h3 className="subtitulo">Papeleo</h3>
          <p className="intro">
            Una constancia y una fila del registro por estudiante ({plan.total} en total). El archivo
            XLSX oficial de la biblioteca no se escribe desde la app: pegue o copie la fila.
          </p>
          <div className="ficha-descargas">
            {plan.constancias.map(({ indice, autor }) => (
              <button
                key={indice}
                type="button"
                className="btn-descarga"
                onClick={() => descargar(indice, 'docx')}
                disabled={ocupado}
              >
                Constancia de {autor || `autor ${indice + 1}`}
              </button>
            ))}
          </div>
          <div className="ficha-descargas">
            {plan.constancias.map(({ indice, autor }) => (
              <button
                key={`zip-${indice}`}
                type="button"
                className="btn-descarga"
                onClick={() => descargar(indice, 'zip')}
                disabled={ocupado}
                title="Constancia del autor + su fila del registro (registro.csv)"
              >
                Paquete de {autor || `autor ${indice + 1}`} (.zip)
              </button>
            ))}
          </div>
          <div className="ficha-descargas">
            <button type="button" className="btn-descarga" onClick={() => generarFila('tsv')} disabled={ocupado}>
              Fila del registro (.tsv)
            </button>
            <button type="button" className="btn-descarga" onClick={() => generarFila('csv')} disabled={ocupado}>
              Fila del registro (.csv)
            </button>
            <button type="button" className="btn-descarga" onClick={() => generarFila('xlsx')} disabled={ocupado}>
              Fila del registro (.xlsx)
            </button>
            <button type="button" className="btn-descarga" onClick={() => generarFila('json')} disabled={ocupado}>
              Ver la fila (texto)
            </button>
          </div>
          {filas.length > 0 && (
            <div className="ficha-filas">
              <div className="ficha-filas-cabecera">
                <strong>Fila del registro</strong>
                <button type="button" className="btn-copiar" onClick={copiarFila}>
                  {copiado ? '¡Copiado!' : 'Copiar fila'}
                </button>
              </div>
              {filas.map((fila, indice) => (
                <pre key={indice}>{fila}</pre>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="back-action">
        <button type="button" className="btn-validar" onClick={volverAlReporte}>Volver al reporte</button>
      </div>
    </main>
  )
}

export default FichaDeposito
