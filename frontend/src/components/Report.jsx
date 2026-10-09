import { useState, useMemo, useEffect, useRef } from 'react'

// Mapeo de IDs de regla a categoría visible en el reporte.
// El backend no agrupa por categoría en su respuesta JSON (solo devuelve
// la lista plana de resultados), así que el frontend hace esta agrupación
// localmente. El campo "tipo" del YAML de reglas es la fuente de verdad.
const CATEGORIA_POR_ID = {
  papel_tamano: 'Papel',
  fuente_principal: 'Fuente y tamaño',
  tamano_cuerpo: 'Fuente y tamaño',
  caratula_universidad_tamano: 'Fuente y tamaño',
  caratula_facultad_escuela_tamano: 'Fuente y tamaño',
  caratula_titulo_trabajo_tamano: 'Fuente y tamaño',
  caratula_optar_grado_tamano: 'Fuente y tamaño',
  caratula_autores_tamano: 'Fuente y tamaño',
  caratula_logotipo_tamano: 'Fuente y tamaño',
  interlineado: 'Interlineado',
  alineacion_cuerpo: 'Alineación',
  alineacion_caratula_todos_elementos: 'Alineación',
  margen_superior: 'Márgenes',
  margen_inferior: 'Márgenes',
  margen_derecho: 'Márgenes',
  margen_izquierdo: 'Márgenes',
  sangria_parrafo: 'Sangría',
  numeracion_posicion: 'Numeración de página',
  numeracion_preliminares_romano: 'Numeración de página',
  numeracion_cuerpo_arabigo: 'Numeración de página',
  caratula_no_se_enumera: 'Numeración de página',
  caratula_universidad_negrita_mayusculas: 'Carátula',
  caratula_facultad_negrita_mayusculas: 'Carátula',
  caratula_titulo_negrita_mixta: 'Carátula',
  caratula_autores_mayusculas_sin_negrita: 'Carátula',
  caratula_asesor_negrita: 'Carátula',
  caratula_ciudad_pais_negrita: 'Carátula',
  caratula_orcid: 'Carátula',
  estructura_tinv_cuantitativo: 'Estructura',
  estructura_tinv_cualitativo: 'Estructura',
  estructura_tinv_revision_literatura: 'Estructura',
  indice_subdivisiones: 'Estructura',
  resumen_longitud: 'Resumen',
  palabras_clave_minimo: 'Resumen',
  sistema_citas: 'Citas',
  referencias_minimo_cuantitativo: 'Referencias',
  referencias_minimo_cualitativo: 'Referencias',
  referencias_minimo_revision: 'Referencias',
  anexos_minimos_cuantitativo: 'Anexos',
  anexos_minimos_cualitativo: 'Anexos',
  proyecto_formato_general: 'Estructura',
  proyecto_caratula_texto: 'Carátula',
  suficiencia_profesional_formato: 'Estructura',
}

function categoriaDe(ruleId) {
  return CATEGORIA_POR_ID[ruleId] || 'Otros'
}

// Mapeo de `notificacion.estado` (v1.3.0) a badge visible para el personal
// del repositorio. Tabla de estados del contrato:
//  - enviado:               informar que el correo salió.
//  - fallo:                 mostrar el detalle técnico (reintento manual).
//  - sin_correo:            pedir el correo en el formulario de carga.
//  - no_solicitado:         ofrecer la casilla de envío (opt-in) en el formulario.
//  - deshabilitado:         nota de configuración para administradores (si el
//                           backend envía `detalle`; ver CONTRATO_API.md).
//  - sin_observaciones:     nada que mostrar.
function badgeNotificacion(notif) {
  if (!notif || typeof notif.estado !== 'string') return null
  const detalle = typeof notif.detalle === 'string' && notif.detalle.trim() ? notif.detalle.trim() : null
  switch (notif.estado) {
    case 'enviado':
      return { clase: 'ok', texto: '📧 Enviamos las observaciones al correo del estudiante.' }
    case 'fallo':
      return {
        clase: 'fail',
        texto: '⚠ No se pudieron enviar las observaciones por correo.',
        detalle: detalle || 'Motivo técnico no disponible; reintente o envíelo manualmente.',
      }
    case 'sin_correo':
      return {
        clase: 'warn',
        texto: 'El correo no fue enviado: falta el correo del estudiante. Agréguelo en el formulario de carga.',
      }
    case 'no_solicitado':
      return {
        clase: 'info',
        texto: 'No se solicitó el envío por correo. Active “Enviar observaciones por correo al estudiante” al validar.',
      }
    case 'deshabilitado':
      // El backend (contrato v1.4) adjunta `detalle` con la nota de
      // configuración para administradores. Sin `detalle` (backend anterior
      // o respuesta incompleta) no se muestra nada, como hasta ahora.
      if (!detalle) return null
      return {
        clase: 'info',
        texto: 'El envío de correos no está habilitado en el servidor.',
        detalle,
      }
    default:
      // sin_observaciones → nada relevante
      return null
  }
}

const ETIQUETA_FILTRO = { todos: 'Todos', error: 'Errores', warning: 'Advertencias' }

function Report({ data, onBack }) {
  const [filtro, setFiltro] = useState('todos') // 'todos' | 'error' | 'warning'
  const [vista, setVista] = useState('detallada') // 'detallada' | 'simple'
  const [busqueda, setBusqueda] = useState('')
  const [copiado, setCopiado] = useState(null) // rule_id | `error:${rule_id}` | null
  const [anuncio, setAnuncio] = useState('')
  const semaforoRef = useRef(null)
  const anuncioTimer = useRef(null)

  // Anuncia con retardo: sin esto, cada pulsación de tecla en la búsqueda
  // re-llena la región viva y el lector de pantalla no deja de hablar.
  const anunciar = (texto) => {
    if (anuncioTimer.current) clearTimeout(anuncioTimer.current)
    anuncioTimer.current = setTimeout(() => setAnuncio(texto), 350)
  }

  // useMemo: sin esto, el `[]` del fallback sería un array nuevo en cada render
  // y las memorias que dependen de él se recalcularían siempre (aviso exhaustive-deps).
  const resultados = useMemo(
    () => (Array.isArray(data?.resultados) ? data.resultados : []),
    [data]
  )
  const prompts = useMemo(
    () => (Array.isArray(data?.como_preguntar_a_una_ia) ? data.como_preguntar_a_una_ia : []),
    [data]
  )
  const resumen = data?.resumen || { total: resultados.length, fallidos_error: 0, fallidos_warning: 0 }
  // Fail-safe: solo "verde" explícito muestra "listo para entregar".
  // Un payload incompleto/inesperado NUNCA debe decir que la tesis está lista.
  const semaforo = data?.semaforo === 'verde' ? 'verde' : 'rojo'
  const notif = badgeNotificacion(data?.notificacion)

  // Al montar el reporte: mover scroll Y foco al semáforo.
  // El foco real (no solo scroll) es lo que un lector de pantalla percibe.
  useEffect(() => {
    semaforoRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    semaforoRef.current?.focus({ preventScroll: true })
    const e = resumen.fallidos_error || 0
    const w = resumen.fallidos_warning || 0
    setAnuncio(
      `Reporte de validación cargado. Semáforo: ${semaforo}. ` +
      `${resumen.total} reglas evaluadas, ${e} errores, ${w} advertencias.`
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Liberar el temporizador de anuncios al desmontar.
  useEffect(() => () => clearTimeout(anuncioTimer.current), [])

  const q = busqueda.trim().toLowerCase()
  const coincide = (r) =>
    !q ||
    [r.mensaje, r.message, r.esperado, r.expected, r.encontrado, r.found, r.rule_id]
      .some((v) => typeof v === 'string' && v.toLowerCase().includes(q))

  const visibles = useMemo(
    () => resultados.filter((r) => (filtro === 'todos' || r.severidad === filtro) && coincide(r)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resultados, filtro, q]
  )
  const fallidos = useMemo(() => visibles.filter((r) => !r.paso), [visibles])

  // Prompts de IA con el MISMO filtro de búsqueda que la lista de resultados
  // (si no, la sección "Cómo preguntar a una IA" queda desconectada).
  const promptsVisibles = useMemo(
    () =>
      prompts.filter(
        (p) =>
          !q ||
          [p.prompt, p.rule_id, categoriaDe(p.rule_id)].some(
            (v) => typeof v === 'string' && v.toLowerCase().includes(q)
          )
      ),
    [prompts, q]
  )

  // Cuenta lo que REALMENTE se pinta en la vista actual: la vista simple solo
  // lista pendientes, así que anunciar el total de coincidencias sería mentira.
  const cuentaVisible = (f, qq) => {
    const base = resultados.filter(
      (r) =>
        (f === 'todos' || r.severidad === f) &&
        (!qq ||
          [r.mensaje, r.message, r.esperado, r.expected, r.encontrado, r.found, r.rule_id]
            .some((x) => typeof x === 'string' && x.toLowerCase().includes(qq)))
    )
    return vista === 'simple' ? base.filter((r) => !r.paso).length : base.length
  }

  // Agrupa los resultados filtrados por categoría para la vista detallada.
  const grupos = useMemo(() => {
    const m = new Map()
    visibles.forEach((r) => {
      const cat = categoriaDe(r.rule_id)
      if (!m.has(cat)) m.set(cat, [])
      m.get(cat).push(r)
    })
    return Array.from(m.entries())
  }, [visibles])

  // Barra de progreso de cumplimiento (wireframe: "Ej: 76%").
  const total = resumen.total || 0
  const errN = resumen.fallidos_error || 0
  const warnN = resumen.fallidos_warning || 0
  const okN = Math.max(total - errN - warnN, 0)
  const pct = (n) => (total > 0 ? (n / total) * 100 : 0)
  const pctOk = Math.round(pct(okN))

  const cambiarFiltro = (f) => {
    setFiltro(f)
    const n = cuentaVisible(f, q)
    anunciar(
      `Filtro «${ETIQUETA_FILTRO[f]}»: ${n} de ${resultados.length} ` +
        `${vista === 'simple' ? 'pendientes' : 'reglas'} visibles.`
    )
  }

  const cambiarVista = (v) => {
    setVista(v)
    setAnuncio(v === 'simple' ? 'Vista simple: solo pendientes.' : 'Vista detallada: checklist por categoría.')
  }

  const onBusqueda = (e) => {
    const v = e.target.value
    setBusqueda(v)
    const qq = v.trim().toLowerCase()
    const n = cuentaVisible(filtro, qq)
    anunciar(
      !qq
        ? `Búsqueda borrada: ${resultados.length} reglas.`
        : n === 0
          ? `Ninguna regla coincide con «${v.trim()}».`
          : `${n} ${vista === 'simple' ? 'pendientes coinciden' : 'reglas coinciden'} con «${v.trim()}».`
    )
  }

  const copiar = async (ruleId, texto) => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(ruleId)
      setAnuncio('Prompt copiado al portapapeles.')
      setTimeout(() => setCopiado((c) => (c === ruleId ? null : c)), 1500)
    } catch {
      // Sin permisos de clipboard: avisar en lugar de fallar en silencio.
      setCopiado(`error:${ruleId}`)
      setAnuncio('No se pudo copiar automáticamente. Seleccione el texto del prompt y cópielo manualmente.')
      setTimeout(() => setCopiado((c) => (c === `error:${ruleId}` ? null : c)), 3000)
    }
  }

  const textoBusqueda = busqueda.trim()

  return (
    <main>
      {/* Región viva: anuncia carga, filtros, búsqueda y copiado (aria-live). */}
      <div className="sr-only" role="status" aria-live="polite">{anuncio}</div>

      {/* ── Semáforo y resumen ──────────────────────── */}
      <div className="card" ref={semaforoRef} tabIndex={-1}>
        {data?.__mock && (
          <div className="aviso warn" role="status" style={{ marginBottom: '.8rem' }}>
            <div className="aviso-fila">
              <strong>Reporte de ejemplo.</strong>
            </div>
            <span className="ejemplos">{data.__mockMotivo}</span>
          </div>
        )}
        <div className="semaforo">
          <div className={`luz ${semaforo}`}>{semaforo === 'rojo' ? '✕' : '✓'}</div>
          <div>
            <h2 className="titulo">
              {semaforo === 'rojo' ? 'Requiere correcciones antes de entregar' : 'Documento listo para entregar'}
            </h2>
            <div className="desc">
              {semaforo === 'rojo'
                ? 'Se detectaron errores de formato que bloquean la entrega conforme a las directivas UNT.'
                : 'El documento cumple con las directivas de formato de la UNT.'}
            </div>
            {notif && (
              <div className={`badge-notif ${notif.clase}`} role="status">
                {notif.texto}
                {notif.detalle && <span className="badge-notif-detalle">{notif.detalle}</span>}
              </div>
            )}
          </div>
        </div>

        <div className="resumen">
          <div className="kpi"><div className="num">{resumen.total}</div><div className="lbl">Reglas evaluadas</div></div>
          <div className="kpi rojo"><div className="num">{errN}</div><div className="lbl">Errores</div></div>
          <div className="kpi ambar"><div className="num">{warnN}</div><div className="lbl">Advertencias</div></div>
        </div>

        {/* Barra de progreso de cumplimiento (3 segmentos: ok / warn / error).
            Oculta si no hay total: un "0%" con datos vacío solo confunde. */}
        {total > 0 && (
          <div
            className="progreso"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pctOk}
            aria-label={`Cumplimiento del formato: ${pctOk}% de reglas cumplidas`}
          >
            <div className="progreso-track" aria-hidden="true">
              <span className="seg ok" style={{ width: `${pct(okN)}%` }} />
              <span className="seg warn" style={{ width: `${pct(warnN)}%` }} />
              <span className="seg err" style={{ width: `${pct(errN)}%` }} />
            </div>
            <div className="progreso-txt">
              {pctOk}% de reglas cumplidas · {errN + warnN} pendiente{errN + warnN === 1 ? '' : 's'} de entregar
            </div>
          </div>
        )}
      </div>

      {/* ── Controles (filtro + búsqueda + vista) ───── */}
      <div className="card">
        <div className="controles">
          <div className="filtro" role="group" aria-label="Filtrar por severidad">
            {['todos', 'error', 'warning'].map((f) => (
              <button
                key={f}
                className={`chip ${filtro === f ? 'on' : ''}`}
                onClick={() => cambiarFiltro(f)}
                aria-pressed={filtro === f}
              >
                {ETIQUETA_FILTRO[f]}
              </button>
            ))}
          </div>

          <label className="buscador">
            <span className="sr-only">Buscar regla o mensaje</span>
            <input
              type="search"
              value={busqueda}
              onChange={onBusqueda}
              placeholder="Buscar regla o mensaje..."
              aria-label="Buscar regla o mensaje"
            />
          </label>

          <div className="toggle-vista" role="group" aria-label="Cambiar vista de resultados">
            <button
              className={`btn-vista ${vista === 'detallada' ? 'on' : ''}`}
              onClick={() => cambiarVista('detallada')}
              aria-pressed={vista === 'detallada'}
            >
              Vista detallada
            </button>
            <button
              className={`btn-vista ${vista === 'simple' ? 'on' : ''}`}
              onClick={() => cambiarVista('simple')}
              aria-pressed={vista === 'simple'}
            >
              Vista simple
            </button>
          </div>
        </div>

        {/* ── Vista simple ───────────────────────────── */}
        {vista === 'simple' && (
          <div className="vista-simple">
            <p className="vista-simple__intro">
              <strong>Resumen de pendientes:</strong> corregir los siguientes puntos para obtener el visto bueno.
            </p>
            <div className="pendientes">
              {fallidos.length === 0 ? (
                <p className="vista-simple__empty">
                  {textoBusqueda
                    ? `No hay pendientes que coincidan con «${textoBusqueda}».`
                    : 'No hay pendientes.'}
                </p>
              ) : (
                fallidos.map((r) => (
                  <div key={r.rule_id} className="pendiente">
                    <span className={`dot ${r.severidad}`}></span>
                    <span>{r.mensaje || r.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* ── Vista detallada: checklist por categoría ─ */}
        {vista === 'detallada' && (
          <div>
            {grupos.length === 0 ? (
              <p className="vista-simple__empty">
                {textoBusqueda
                  ? `No se encontraron reglas que coincidan con «${textoBusqueda}».`
                  : 'No hay resultados con este filtro.'}
              </p>
            ) : (
              grupos.map(([cat, items]) => {
                const e = items.filter((r) => !r.paso && r.severidad === 'error').length
                const w = items.filter((r) => !r.paso && r.severidad === 'warning').length
                const ok = items.filter((r) => r.paso).length
                return (
                  <details key={cat} className="categoria">
                    <summary className="cat-head">
                      <strong>{cat}</strong>
                      <span className="der">
                        {e > 0 && <span className="count err">{e} err</span>}
                        {w > 0 && <span className="count warn">{w} warn</span>}
                        {ok > 0 && <span className="count ok">{ok} ok</span>}
                        <span className="flecha" aria-hidden="true">▶</span>
                      </span>
                    </summary>
                    <div className="cat-body">
                      {items.map((r) => {
                        const icono = !r.paso
                          ? (r.severidad === 'error' ? '✕' : '⚠')
                          : '✓'
                        const claseIcono = !r.paso
                          ? (r.severidad === 'error' ? 'fail' : 'warn')
                          : 'ok'
                        const etiquetaEstado = !r.paso
                          ? (r.severidad === 'error' ? 'Error' : 'Advertencia')
                          : 'Cumple'
                        return (
                          <div key={r.rule_id} className="resultado">
                            <span
                              className={`estado ${claseIcono}`}
                              role="img"
                              aria-label={etiquetaEstado}
                              title={etiquetaEstado}
                            >
                              {icono}
                            </span>
                            <div className="info">
                              <div className="msg">
                                {r.mensaje || r.message}
                                {!r.paso && (
                                  <div className="esperado">
                                    <span className="etq">Esperado:</span> {r.esperado ?? r.expected}<br />
                                    <span className="etq">Encontrado:</span> {r.encontrado ?? r.found}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </details>
                )
              })
            )}
          </div>
        )}
      </div>

      {/* ── Cómo preguntar a una IA ─────────────────── */}
      <div className="card">
        <h2 className="ia-titulo">🤖 Cómo preguntar a una IA</h2>
        <p className="ia-desc">
          Copie y pegue estos prompts en cualquier IA (ChatGPT, Claude, etc.) para corregir cada problema.
        </p>
        <div className="ia-cards">
          {promptsVisibles.length === 0 ? (
            <p className="ia-empty">
              {textoBusqueda
                ? `Ningún prompt coincide con «${textoBusqueda}».`
                : 'No hay problemas detectados. ¡Felicidades!'}
            </p>
          ) : (
            promptsVisibles.map((p) => (
              <div key={p.rule_id} className="ia-card">
                <div className="head">
                  <span className="rule">{categoriaDe(p.rule_id)}</span>
                  <button
                    className={`btn-copiar ${copiado === `error:${p.rule_id}` ? 'fail' : ''}`}
                    onClick={() => copiar(p.rule_id, p.prompt)}
                  >
                    {copiado === p.rule_id
                      ? '¡Copiado!'
                      : copiado === `error:${p.rule_id}`
                        ? 'No se pudo copiar'
                        : 'Copiar'}
                  </button>
                </div>
                <pre>{p.prompt}</pre>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="back-action">
        <button className="btn-validar" onClick={onBack}>Validar otro archivo</button>
      </div>
    </main>
  )
}

export default Report
