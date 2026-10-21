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
  // Reglas de la suite DSL ampliada (PRs #45/#46) + la regla sintética del motor.
  indice_paginas_separadas: 'Índice',
  indice_apunta_secciones: 'Índice',
  indice_numeracion_jerarquica: 'Índice',
  encabezado_membrete: 'Encabezados y pies',
  encabezado_formato: 'Encabezados y pies',
  notas_al_pie_consistencia: 'Notas al pie',
  caratula_linea_investigacion: 'Carátula',
  deteccion_tipo_documento: 'Tipo de documento',
  tipo_documento_no_determinado: 'Tipo de documento',
  track_changes_sin_resolver: 'Control de cambios',
}

function categoriaDe(ruleId) {
  return CATEGORIA_POR_ID[ruleId] || 'Otros'
}

// Contrato v1.5: las reglas que no aplican al tipo de documento detectado
// llegan con aplicable=false (y paso=true, porque no fallaron: no se
// evaluaron). Mostrarlas como "cumplidas" es justo lo que la decisión 5 de
// docs/diseno/15_tipo_documento_grupos.md evita ("listarlas haría creer que
// se cumplieron"): el reporte trabaja solo con las reglas evaluadas.
// Tolerante a respuestas sin el campo (contrato v1.4, mocks viejos).
// Exportada para su unit test (vitest): ver Report.aplicabilidad.test.js.
export function filtrarAplicables(resultados) {
  return (Array.isArray(resultados) ? resultados : []).filter(
    (r) => r && r.aplicable !== false
  )
}

// Une TODOS los prompts de la sección en UNO solo, listo para copiar y pegar
// en una sola interacción con la IA. Cada prompt individual se conserva íntegro
// (son autónomos y ya vienen probados): aquí solo se añade el marco general y
// un separador numerado con la categoría de cada problema.
// Exportada para su unit test (vitest): ver Report.promptUnico.test.js.
export function construirPromptUnico(prompts) {
  const lista = (Array.isArray(prompts) ? prompts : []).filter(
    (p) => p && typeof p.prompt === 'string' && p.prompt.trim()
  )
  if (lista.length === 0) return ''
  const n = lista.length
  const encabezado =
    `Tengo un documento de tesis en Word (Universidad Nacional de Trujillo) con ` +
    `${n === 1 ? 'un problema de formato' : `${n} problemas de formato`}. ` +
    `Corrige ${n === 1 ? 'este problema' : 'todos los siguientes problemas'} en Microsoft Word, ` +
    `sin afectar el resto del formato del documento, y dame instrucciones paso a paso ` +
    `para cada uno, en el orden indicado:`
  const bloques = lista.map(
    (p, i) => `════ Problema ${i + 1} de ${n} · ${categoriaDe(p.rule_id)} ════\n${p.prompt.trim()}`
  )
  return [encabezado, ...bloques].join('\n\n')
}

// Mapeo de `notificacion.estado` a badge visible para el personal
// del repositorio (estados v1.3.0 + `deshabilitado` con detalle v1.4).
// Tabla de estados del contrato:
//  - enviado:               informar que el correo salió.
//  - fallo:                 mostrar el detalle técnico (reintento manual).
//  - sin_correo:            pedir el correo en el formulario de carga.
//  - no_solicitado:         ofrecer la casilla de envío (opt-in) en el formulario.
//  - deshabilitado:         nota de configuración para administradores (si el
//                           backend envía `detalle`; ver CONTRATO_API.md).
//  - sin_observaciones:     nada que mostrar.
// Exportada para su unit test (vitest): ver Report.badgeNotificacion.test.js.
export function badgeNotificacion(notif) {
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
      // configuración completa (variables de entorno): aquí solo se enmarca
      // como nota para administradores, sin repetir lo que ya dice el detalle.
      // Sin `detalle` (backend anterior) no se muestra nada, como hasta ahora.
      if (!detalle) return null
      return {
        clase: 'info',
        texto: 'Nota para administradores:',
        detalle,
      }
    default:
      // sin_observaciones → nada relevante
      return null
  }
}

// Mapeo de `deposito.estado` (contrato v1.6, depósito en DSpace) a badge para
// el personal del repositorio. Misma mecánica que badgeNotificacion:
// opt-in del operador (`depositar`), best-effort (un fallo de DSpace nunca
// rompe la respuesta) y solo procede con semáforo verde; el ítem queda en la
// cola de aprobación de la sede, nunca se publica directo.
// Tabla de estados del contrato (CONTRATO_API.md §"Depósito en DSpace"):
//  - enviado:       quedó en la cola de aprobación de la sede.
//  - fallo:         mostrar el detalle técnico para corregir y reintentar.
//  - sin_solicitud: no se pidió; con semáforo verde se ofrece la casilla.
//  - no_apto:       se pidió pero el semáforo no es verde.
//  - deshabilitado: nota de configuración para administradores (si el backend
//                   envía `detalle`).
// Exportada para su unit test (vitest): ver Report.badgeDeposito.test.js.
export function badgeDeposito(deposito, semaforo) {
  if (!deposito || typeof deposito.estado !== 'string') return null
  const detalle =
    typeof deposito.detalle === 'string' && deposito.detalle.trim() ? deposito.detalle.trim() : null
  switch (deposito.estado) {
    case 'enviado':
      return {
        clase: 'ok',
        texto: 'El documento quedó en la cola de aprobación del repositorio.',
      }
    case 'fallo':
      return {
        clase: 'fail',
        texto: 'No se pudo depositar el documento en el repositorio.',
        detalle: detalle || 'Motivo técnico no disponible; reintente o deposite manualmente.',
      }
    case 'no_apto':
      return {
        clase: 'warn',
        texto: 'No se depositó: el documento aún tiene observaciones (solo se depositan documentos con semáforo verde).',
      }
    case 'deshabilitado':
      // Igual que la notificación (hallazgo B3): sin `detalle` no se muestra nada.
      if (!detalle) return null
      return {
        clase: 'info',
        texto: 'Nota para administradores:',
        detalle,
      }
    case 'sin_solicitud':
      // Solo se ofrece la casilla cuando el documento ya es apto: con
      // semáforo rojo no hay nada que depositar y el aviso sería ruido.
      if (semaforo !== 'verde') return null
      return {
        clase: 'info',
        texto: 'No se solicitó el depósito. Active «Depositar en el repositorio» al validar para enviarlo a DSpace.',
      }
    default:
      return null
  }
}

const ETIQUETA_FILTRO = { todos: 'Todos', error: 'Errores', warning: 'Advertencias' }

// Metadatos del contrato v1.5 (archivo + tipo de documento detectado).
const humanizaTipo = (t) => (typeof t === 'string' && t ? t.replaceAll('_', ' ') : null)

function textoTipoDocumento(meta) {
  const estado = meta?.tipo_documento_estado
  if (!estado) return null
  if (estado === 'vigente') {
    const t = humanizaTipo(meta.tipo_documento_inferido || meta.tipo_documento_declarado)
    return t ? `Tipo de documento: ${t}` : null
  }
  if (estado === 'sin_determinar') return 'No se pudo determinar el tipo de documento.'
  if (estado === 'contradictorio') {
    const dec = humanizaTipo(meta.tipo_documento_declarado) || '?'
    const inf = humanizaTipo(meta.tipo_documento_inferido) || '?'
    return `Aviso: el tipo declarado (${dec}) no coincide con el detectado (${inf}).`
  }
  return null
}

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
  // Contrato v1.5 (aplicabilidad): el resto del reporte (checklist, KPIs,
  // barra, anuncios) trabaja SOLO con las reglas realmente evaluadas. Los
  // números vienen del backend (total_evaluadas/reglas_no_aplicables) con
  // fallback computado para respuestas que no los traigan.
  const evaluadas = useMemo(() => filtrarAplicables(resultados), [resultados])
  const nEvaluadas = resumen.total_evaluadas ?? evaluadas.length
  const nNoAplicables = resumen.reglas_no_aplicables ?? resultados.length - evaluadas.length
  // Fail-safe: solo "verde" explícito muestra "listo para entregar".
  // Un payload incompleto/inesperado NUNCA debe decir que la tesis está lista.
  const semaforo = data?.semaforo === 'verde' ? 'verde' : 'rojo'
  const notif = badgeNotificacion(data?.notificacion)
  const dep = badgeDeposito(data?.deposito, semaforo)
  // Metadatos (archivo y tipo de documento detectado): nunca bloquean nada,
  // solo informan. El estado "contradictorio" se destaca por su clase.
  const meta = data?.metadatos
  const archivoTexto = meta?.archivo_nombre
    ? `Archivo: ${meta.archivo_nombre}` +
      (typeof meta.archivo_tamano_bytes === 'number'
        ? ` · ${
            meta.archivo_tamano_bytes >= 1048576
              ? `${(meta.archivo_tamano_bytes / 1048576).toFixed(1)} MB`
              : `${Math.max(1, Math.round(meta.archivo_tamano_bytes / 1024))} KB`
          }`
        : '')
    : null
  const tipoDocumentoTexto = textoTipoDocumento(meta)
  const tipoContradictorio = meta?.tipo_documento_estado === 'contradictorio'

  // Al montar el reporte: mover scroll Y foco al semáforo.
  // El foco real (no solo scroll) es lo que un lector de pantalla percibe.
  useEffect(() => {
    // prefers-reduced-motion también aplica al scroll en JS (el CSS reducido
    // no cubre la API scrollIntoView).
    const comportamiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ? 'auto'
      : 'smooth'
    semaforoRef.current?.scrollIntoView({ behavior: comportamiento, block: 'start' })
    semaforoRef.current?.focus({ preventScroll: true })
    const e = resumen.fallidos_error || 0
    const w = resumen.fallidos_warning || 0
    setAnuncio(
      `Reporte de validación cargado. Semáforo: ${semaforo}. ` +
      `${nEvaluadas} reglas evaluadas, ${e} errores, ${w} advertencias.` +
      (nNoAplicables > 0 ? ` ${nNoAplicables} reglas no aplican a este tipo de documento.` : '')
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
    () => evaluadas.filter((r) => (filtro === 'todos' || r.severidad === filtro) && coincide(r)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [evaluadas, filtro, q]
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

  // Prompt único: los prompts visibles reunidos en uno solo (memorizado para
  // que cada pulsación de tecla en la búsqueda no lo reconstruya).
  const promptUnico = useMemo(() => construirPromptUnico(promptsVisibles), [promptsVisibles])

  // Cuenta lo que REALMENTE se pinta en la vista actual: la vista simple solo
  // lista pendientes, así que anunciar el total de coincidencias sería mentira.
  const cuentaVisible = (f, qq) => {
    const base = evaluadas.filter(
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
  // Contrato v1.5: el % es sobre las reglas EVALUADAS (las no aplicables
  // no cuentan como cumplidas; antes inflaban el porcentaje).
  const errN = resumen.fallidos_error || 0
  const warnN = resumen.fallidos_warning || 0
  const okN = Math.max(nEvaluadas - errN - warnN, 0)
  const pct = (n) => (nEvaluadas > 0 ? (n / nEvaluadas) * 100 : 0)
  const pctOk = Math.round(pct(okN))

  const cambiarFiltro = (f) => {
    setFiltro(f)
    const n = cuentaVisible(f, q)
    anunciar(
      `Filtro «${ETIQUETA_FILTRO[f]}»: ${n} de ${evaluadas.length} ` +
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
        ? `Búsqueda borrada: ${evaluadas.length} reglas.`
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
            {dep && (
              <div className={`badge-notif badge-deposito ${dep.clase}`} role="status">
                {dep.texto}
                {dep.detalle && <span className="badge-notif-detalle">{dep.detalle}</span>}
              </div>
            )}
          </div>
        </div>

        {(archivoTexto || tipoDocumentoTexto) && (
          <div className="meta-linea">
            {archivoTexto && <span>{archivoTexto}</span>}
            {tipoDocumentoTexto && (
              <span className={tipoContradictorio ? 'meta-aviso' : undefined}>{tipoDocumentoTexto}</span>
            )}
          </div>
        )}

        <div className="resumen">
          <div className="kpi"><div className="num">{nEvaluadas}</div><div className="lbl">Reglas evaluadas</div></div>
          <div className="kpi rojo"><div className="num">{errN}</div><div className="lbl">Errores</div></div>
          <div className="kpi ambar"><div className="num">{warnN}</div><div className="lbl">Advertencias</div></div>
        </div>
        {nNoAplicables > 0 && (
          <p className="resumen-nota" role="status">
            {nNoAplicables} regla{nNoAplicables === 1 ? '' : 's'} no aplica{nNoAplicables === 1 ? '' : 'n'} a este
            tipo de documento y no se evalu{nNoAplicables === 1 ? 'ó' : 'aron'}.
          </p>
        )}

        {/* Barra de progreso de cumplimiento (3 segmentos: ok / warn / error).
            Oculta si no hay evaluadas: un "0%" con datos vacío solo confunde. */}
        {nEvaluadas > 0 && (
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
                                {!r.paso && r.ubicacion && (
                                  <div className="regla-ref">Ref.: {r.ubicacion}</div>
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
        {promptsVisibles.length > 0 && (
          <section className="ia-unico" aria-labelledby="ia-unico-titulo">
            <div className="ia-unico-head">
              <h3 className="ia-unico-titulo" id="ia-unico-titulo">
                Prompt único: todos los problemas en una sola instrucción
              </h3>
              <button
                className={`btn-copiar ${copiado === 'error:__unico__' ? 'fail' : ''}`}
                onClick={() => copiar('__unico__', promptUnico)}
              >
                {copiado === '__unico__'
                  ? '¡Copiado!'
                  : copiado === 'error:__unico__'
                    ? 'No se pudo copiar'
                    : 'Copiar todo junto'}
              </button>
            </div>
            <p className="ia-unico-desc">
              Una sola instrucción con {promptsVisibles.length}{' '}
              {promptsVisibles.length === 1 ? 'prompt' : 'prompts'}{' '}
              {textoBusqueda
                ? promptsVisibles.length === 1
                  ? 'visible con la búsqueda actual'
                  : 'visibles con la búsqueda actual'
                : 'de esta lista'}
              , para pegarla de una vez en cualquier IA.
            </p>
            <details className="ia-unico-detalle">
              <summary>Ver el prompt completo</summary>
              <pre>{promptUnico}</pre>
            </details>
          </section>
        )}
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
