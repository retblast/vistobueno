import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CAMPOS_EXTRAIDOS,
  CAMPOS_MANUALES,
  ESTADO_PAPELEO,
  autoresDe,
  borrarResguardo,
  construirCuerpoConstancia,
  construirCuerpoFilaRegistro,
  debeMostrarFicha,
  descargarConstancia,
  establecerValor,
  faltantesDe,
  formatearTimestamp,
  generarFilaRegistro,
  guardarNombreResponsable,
  guardarResguardo,
  identidadDeArchivo,
  listaDe,
  mensajeDeDescarte,
  planDeDescargas,
  publicarFicha,
  consultarPapeleo,
  leerResguardo,
  sondearDeposito,
  subirPlantillaPapeleo,
  tituloCoincide,
  tituloDe,
  valorDe,
} from '../ficha'

// Frecuencia del sondeo del buzón (handover S8 §2.3: ~3 s).
const INTERVALO_SONDEO_MS = 3000

function FichaDeposito({ data, apiUrl, onBack, archivo }) {
  // Token compartido del buzón (opcional): el backend lo exige solo si está
  // definido (VISTOBUENO_API_TOKEN). En el loopback no hace falta, así que
  // sin VITE_API_TOKEN la SPA sigue hablando sin header.
  const tokenBuzon = import.meta.env.VITE_API_TOKEN || ''
  const fichaInicial = data?.ficha_deposito
  // Identidad del documento por CONTENIDO (hash): dos archivos con el mismo
  // nombre no pueden compartir el resguardo de la ficha (F1).
  const identidad = useMemo(() => identidadDeArchivo(archivo), [archivo])
  // Resguardo: versión, identidad y caducidad se verifican al restaurar
  // (F5). Un resguardo de otra versión, de otro documento o caducado no se
  // restaura y el operador recibe el motivo.
  const [resguardoInicial] = useState(() => leerResguardo(window.localStorage, identidad))
  const [ficha, setFicha] = useState(() => resguardoInicial.ficha ?? fichaInicial)
  const [recuperada, setRecuperada] = useState(() => Boolean(resguardoInicial.ficha))
  const [descarte, setDescarte] = useState(() => resguardoInicial.motivo ?? null)
  const [fase, setFase] = useState('edicion') // edicion | esperando | recibido | listo
  const [error, setError] = useState(null)
  const [aviso, setAviso] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [handle, setHandle] = useState('')
  const [tituloRecibido, setTituloRecibido] = useState(null)
  const [timestamp, setTimestamp] = useState('')
  const [filas, setFilas] = useState([])
  const [copiado, setCopiado] = useState(false)
  const [tramiteId, setTramiteId] = useState('')
  const [venceEn, setVenceEn] = useState('')
  // Configuración de papeleo: nombre del responsable (columna FIRMA) y
  // plantilla oficial Modelo B que usa la API para las constancias.
  const [papeleo, setPapeleo] = useState(null)
  const [nombreResponsable, setNombreResponsable] = useState('')
  const [papeleoError, setPapeleoError] = useState(null)
  const [papeleoAviso, setPapeleoAviso] = useState(null)
  const [ocupadoPapeleo, setOcupadoPapeleo] = useState(false)
  const plantillaRef = useRef(null)
  const timerRef = useRef(null)
  // Reporte ya rechazado por el operador (handle + timestamp). El buzón es
  // "última gana": sin esta marca la app volvería a mostrar el mismo reporte
  // descartado en cada sondeo. Cancelar la espera limpia la marca (el
  // operador puede así volver a ver el estado actual del buzón).
  const rechazadoRef = useRef(null)

  const limpiarEstadoDeposito = useCallback(() => {
    setHandle('')
    setTituloRecibido(null)
    setTimestamp('')
    setFilas([])
    setCopiado(false)
    rechazadoRef.current = null
  }, [])

  const autores = useMemo(() => autoresDe(ficha), [ficha])
  const plan = useMemo(() => planDeDescargas(ficha), [ficha])
  const faltantes = useMemo(() => faltantesDe(ficha), [ficha])

  // Resguardo de la ficha editada en cada cambio.
  useEffect(() => {
    if (!ficha) return
    guardarResguardo(window.localStorage, identidad, ficha)
  }, [identidad, ficha])

  const editar = useCallback((campo, valor) => {
    setFicha((actual) => establecerValor(actual, campo, valor))
    // Al tomar la-edición el aviso de «ficha recuperada» ya no aporta nada.
    setRecuperada(false)
    setDescarte(null)
  }, [])


  // Sondeo del buzón mientras el panel de espera está abierto.
  useEffect(() => {
    if (fase !== 'esperando') return undefined
    if (!tramiteId || !venceEn) {
      setError('El trámite publicado no tiene identidad válida. Vuelve a preparar el depósito.')
      setFase('edicion')
      return undefined
    }
    let vivo = true
    let sondeando = false
    const esperado = tramiteId
    const limite = venceEn
    const sondear = async () => {
      if (sondeando) return
      sondeando = true
      try {
        const resultado = await sondearDeposito(apiUrl, tokenBuzon, {
          tramiteId: esperado,
          venceEn: limite,
        })
        if (!vivo) return
        if (resultado.estado === 'esperando' || resultado.estado === 'ajeno') return
        if (resultado.estado === 'error' || resultado.estado === 'expirado' || resultado.estado === 'invalido') {
          setError(resultado.mensaje)
          limpiarEstadoDeposito()
          setTramiteId('')
          setVenceEn('')
          setFase('edicion')
          return
        }
        // Reporte ya rechazado por el operador: seguir esperando en silencio.
        const rechazado = rechazadoRef.current
        if (
          rechazado &&
          rechazado.tramiteId === resultado.tramiteId &&
          rechazado.handle === resultado.handle &&
          rechazado.timestamp === resultado.timestamp
        ) {
          return
        }
        setHandle(resultado.handle || '')
        setTituloRecibido(resultado.titulo ?? null)
        setTimestamp(resultado.timestamp || '')
        setFase('recibido')
      } catch (e) {
        if (!vivo) return
        setError(`No se pudo consultar el buzón: ${e.message}`)
        limpiarEstadoDeposito()
        setTramiteId('')
        setVenceEn('')
        setFase('edicion')
      } finally {
        sondeando = false
      }
    }
    sondear()
    timerRef.current = setInterval(sondear, INTERVALO_SONDEO_MS)
    return () => {
      vivo = false
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [apiUrl, fase, limpiarEstadoDeposito, tokenBuzon, tramiteId, venceEn])

  const preparar = async () => {
    if (faltantes.length > 0 || ocupado) return
    setOcupado(true)
    setError(null)
    setAviso(null)
    try {
      const publicado = await publicarFicha(apiUrl, ficha, tokenBuzon)
      limpiarEstadoDeposito()
      setTramiteId(publicado.tramite_id)
      setVenceEn(publicado.vence_en)
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
    limpiarEstadoDeposito()
    setTramiteId('')
    setVenceEn('')
    setAviso('Se canceló la espera. La ficha sigue en el buzón (vigencia: 1 hora).')
  }

  // Cotejo del título: si no coincide, el operador decide (nunca a ciegas).
  const tituloCoincideConFicha = useMemo(
    () => tituloCoincide(tituloDe(ficha), tituloRecibido),
    [ficha, tituloRecibido]
  )

  const aceptar = () => {
    if (fase !== 'recibido' || !tramiteId) return
    setFase('listo')
    setAviso('Depósito aceptado. Ya puede descargar la constancia y la fila del registro.')
  }

  const rechazar = () => {
    setFase('edicion')
    rechazadoRef.current = { tramiteId, handle, timestamp }
    setHandle('')
    setTituloRecibido(null)
    setTimestamp('')
    setFilas([])
    setError('El título recibido no coincide con la ficha. No se usó el handle: revise la ficha y prepare de nuevo.')
  }

  const descargar = async (indiceAutor, formato) => {
    if (ocupado) return
    if (!tramiteId) {
      setError('No hay un trámite vigente para generar la constancia.')
      return
    }
    setOcupado(true)
    setError(null)
    try {
      const cuerpo = construirCuerpoConstancia(ficha, handle, timestamp, indiceAutor, tramiteId)
      await descargarConstancia(apiUrl, cuerpo, formato, tokenBuzon)
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupado(false)
    }
  }

  const generarFila = async (formato) => {
    if (ocupado) return
    if (!tramiteId) {
      setError('No hay un trámite vigente para generar la fila del registro.')
      return
    }
    setOcupado(true)
    setError(null)
    try {
      const cuerpo = construirCuerpoFilaRegistro(ficha, handle, timestamp, tramiteId)
      const resultado = await generarFilaRegistro(apiUrl, cuerpo, formato, tokenBuzon)
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
    borrarResguardo(window.localStorage)
    onBack()
  }

  // ── Configuración de papeleo ───────────────────────────────────────
  // Estado inicial: el servidor informa si el nombre del responsable y la
  // plantilla Modelo B ya están configurados. Si falta alguno o la carga
  // falla, se dice exactamente qué corregir (antes de que la constancia
  // devuelva un 500).
  useEffect(() => {
    let vivo = true
    const consultar = async () => {
      try {
        const estado = await consultarPapeleo(apiUrl, tokenBuzon)
        if (!vivo) return
        setPapeleo(estado)
        if (estado.nombre) setNombreResponsable(estado.nombre)
      } catch (e) {
        if (!vivo) return
        setPapeleo({ estado: ESTADO_PAPELEO.desconocido, problemas: [] })
        setPapeleoError(e.message)
      }
    }
    consultar()
    return () => {
      vivo = false
    }
  }, [apiUrl, tokenBuzon])

  const guardarNombre = async () => {
    if (ocupadoPapeleo) return
    setOcupadoPapeleo(true)
    setPapeleoError(null)
    setPapeleoAviso(null)
    try {
      const estado = await guardarNombreResponsable(apiUrl, nombreResponsable.trim(), tokenBuzon)
      setPapeleo(estado)
      setPapeleoAviso('Se guardó el nombre del responsable.')
    } catch (e) {
      setPapeleoError(e.message)
    } finally {
      setOcupadoPapeleo(false)
    }
  }

  const cargarPlantilla = async (evento) => {
    const archivo = evento.target.files?.[0]
    if (!archivo || ocupadoPapeleo) return
    setOcupadoPapeleo(true)
    setPapeleoError(null)
    setPapeleoAviso(null)
    try {
      const estado = await subirPlantillaPapeleo(apiUrl, archivo, tokenBuzon)
      setPapeleo(estado)
      setPapeleoAviso(`Se cargó la plantilla «${archivo.name}».`)
    } catch (e) {
      setPapeleoError(`La plantilla no se pudo cargar: ${e.message}`)
    } finally {
      setOcupadoPapeleo(false)
      if (plantillaRef.current) plantillaRef.current.value = ''
    }
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
        {descarte && (
          <div className="aviso warn" role="status">
            <span className="ejemplos">{mensajeDeDescarte(descarte)}</span>
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
          {CAMPOS_EXTRAIDOS.map(({ campo, etiqueta, tipo, aviso, avisoSinDetectar }) => {
            const valor = valorDe(ficha, campo)
            const entrada = ficha?.extraidos?.find((c) => c.campo === campo)
            const detectado = entrada?.detectado
            const id = `extraido-${campo}`
            const texto = Array.isArray(valor) ? valor.join('\n') : (valor ?? '')
            // Aviso de revisión (ORCID del asesor): el valor viene del
            // documento, así que el operador tiene que verificarlo.
            const sinDetectar = !entrada || detectado === false
            const mensajeCampo = aviso
              ? (sinDetectar ? (avisoSinDetectar ?? aviso) : aviso)
              : null
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
                {mensajeCampo && (
                  <p className="campo-ayuda">{mensajeCampo}</p>
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

      {/* ── Configuración de papeleo ─────────────────────── */}
      <div className="card">
        <h3 className="subtitulo">Configuración de papeleo</h3>
        <p className="intro">
          El nombre del responsable se usa en la columna FIRMA del registro y la plantilla oficial
          Modelo B la usa el servidor para generar las constancias. Configurelos aquí: si falta
          alguno, la generación de constancias falla.
        </p>
        <div className="ficha-campos">
          <div className="campo-ficha">
            <label htmlFor="papeleo-nombre">Nombre del responsable</label>
            <input
              id="papeleo-nombre"
              type="text"
              value={nombreResponsable}
              onChange={(e) => setNombreResponsable(e.target.value)}
              disabled={ocupadoPapeleo || fase === 'esperando'}
            />
            <p className="campo-ayuda">Aparece en la columna FIRMA del registro de la biblioteca.</p>
            <div className="acciones-form">
              <button
                type="button"
                className="btn-descarga"
                onClick={guardarNombre}
                disabled={ocupadoPapeleo || fase === 'esperando' || !nombreResponsable.trim()}
              >
                Guardar nombre
              </button>
            </div>
          </div>
          <div className="campo-ficha">
            <label htmlFor="papeleo-plantilla">Plantilla oficial Modelo B (.docx)</label>
            <input
              id="papeleo-plantilla"
              type="file"
              accept=".docx"
              ref={plantillaRef}
              onChange={cargarPlantilla}
              disabled={ocupadoPapeleo || fase === 'esperando'}
            />
            <p className="campo-ayuda">
              Se envía al servidor, que la usa para generar la constancia de cada estudiante.
            </p>
          </div>
        </div>
        {papeleoAviso && (
          <div className="aviso ok" role="status">
            <span className="ejemplos">{papeleoAviso}</span>
          </div>
        )}
        {papeleoError && (
          <div className="aviso error" role="alert">
            <span className="ejemplos">{papeleoError}</span>
          </div>
        )}
        {papeleo?.estado === ESTADO_PAPELEO.listo && (
          <div className="aviso ok" role="status">
            <span className="ejemplos">
              Configuración completa: el nombre del responsable y la plantilla ya están en el servidor.
            </span>
          </div>
        )}
        {papeleo?.estado === ESTADO_PAPELEO.incompleto && (
          <div className="aviso warn" role="status">
            <div className="aviso-fila"><strong>Falta configuración de papeleo.</strong></div>
            <span className="ejemplos">{papeleo.problemas.join(' ')}</span>
          </div>
        )}
        {papeleo?.estado === ESTADO_PAPELEO.noSoportado && (
          <div className="aviso warn" role="status">
            <span className="ejemplos">{papeleo.detalle}</span>
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
                readOnly
              />
              <p className="campo-ayuda">
                Del clic «Depositar»: {momento.fecha} {momento.hora}. El servidor conserva esta hora
                como parte del depósito vigente.
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
