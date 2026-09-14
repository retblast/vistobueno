import { useState, useMemo } from 'react'

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

function Report({ data, onBack }) {
  const [filtro, setFiltro] = useState('todos') // 'todos' | 'error' | 'warning'
  const [vista, setVista] = useState('detallada') // 'detallada' | 'simple'
  const [copiado, setCopiado] = useState(null)

  const resultados = Array.isArray(data?.resultados) ? data.resultados : []
  const prompts = Array.isArray(data?.como_preguntar_a_una_ia) ? data.como_preguntar_a_una_ia : []
  const resumen = data?.resumen || { total: resultados.length, fallidos_error: 0, fallidos_warning: 0 }
  const semaforo = data?.semaforo || 'verde'

  const fallidos = useMemo(() => resultados.filter((r) => !r.passed), [resultados])

  // Agrupa los resultados filtrados por categoría para la vista detallada.
  const grupos = useMemo(() => {
    const lista = resultados.filter((r) => filtro === 'todos' || r.severity === filtro)
    const m = new Map()
    lista.forEach((r) => {
      const cat = categoriaDe(r.rule_id)
      if (!m.has(cat)) m.set(cat, [])
      m.get(cat).push(r)
    })
    return Array.from(m.entries())
  }, [resultados, filtro])

  const copiar = async (ruleId, texto) => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(ruleId)
      setTimeout(() => setCopiado((c) => (c === ruleId ? null : c)), 1500)
    } catch {
      // Sin permisos de clipboard, se ignora silenciosamente.
    }
  }

  return (
    <main>
      {/* ── Semáforo y resumen ──────────────────────── */}
      <div className="card">
        <div className="semaforo">
          <div className={`luz ${semaforo}`}>{semaforo === 'rojo' ? '✕' : '✓'}</div>
          <div>
            <div className="titulo">
              {semaforo === 'rojo' ? 'Revisa antes de entregar' : '¡Puedes entregar!'}
            </div>
            <div className="desc">
              {semaforo === 'rojo'
                ? 'Se detectaron errores de formato que bloquean la entrega conforme a las directivas UNT.'
                : 'Tu documento cumple con las directivas de formato de la UNT.'}
            </div>
          </div>
        </div>

        <div className="resumen">
          <div className="kpi"><div className="num">{resumen.total}</div><div className="lbl">Reglas evaluadas</div></div>
          <div className="kpi rojo"><div className="num">{resumen.fallidos_error}</div><div className="lbl">Errores</div></div>
          <div className="kpi ambar"><div className="num">{resumen.fallidos_warning}</div><div className="lbl">Advertencias</div></div>
        </div>
      </div>

      {/* ── Controles (filtro + vista) ───────────────── */}
      <div className="card">
        <div className="controles">
          <div className="filtro">
            {['todos', 'error', 'warning'].map((f) => (
              <button
                key={f}
                className={`chip ${filtro === f ? 'on' : ''}`}
                onClick={() => setFiltro(f)}
              >
                {f === 'todos' ? 'Todos' : f === 'error' ? 'Errores' : 'Advertencias'}
              </button>
            ))}
          </div>
          <div className="toggle-vista">
            <button
              className={`btn-vista ${vista === 'detallada' ? 'on' : ''}`}
              onClick={() => setVista('detallada')}
            >
              Vista detallada
            </button>
            <button
              className={`btn-vista ${vista === 'simple' ? 'on' : ''}`}
              onClick={() => setVista('simple')}
            >
              Vista simple
            </button>
          </div>
        </div>

        {/* ── Vista simple ───────────────────────────── */}
        {vista === 'simple' && (
          <div className="vista-simple">
            <p className="vista-simple__intro">
              <strong>Resumen de pendientes:</strong> corrige estos puntos para obtener el visto bueno.
            </p>
            <div className="pendientes">
              {fallidos.length === 0 ? (
                <p className="vista-simple__empty">No hay pendientes.</p>
              ) : (
                fallidos.map((r) => (
                  <div key={r.rule_id} className="pendiente">
                    <span className={`dot ${r.severity}`}></span>
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
              <p className="vista-simple__empty">No hay resultados con este filtro.</p>
            ) : (
              grupos.map(([cat, items]) => {
                const e = items.filter((r) => !r.passed && r.severity === 'error').length
                const w = items.filter((r) => !r.passed && r.severity === 'warning').length
                const ok = items.filter((r) => r.passed).length
                return (
                  <details key={cat} className="categoria" open>
                    <summary className="cat-head">
                      <strong>{cat}</strong>
                      <span className="der">
                        {e > 0 && <span className="count err">{e} err</span>}
                        {w > 0 && <span className="count warn">{w} warn</span>}
                        {ok > 0 && <span className="count ok">{ok} ok</span>}
                        <span className="flecha">▶</span>
                      </span>
                    </summary>
                    <div className="cat-body">
                      {items.map((r) => {
                        const icono = !r.passed
                          ? (r.severity === 'error' ? '✕' : '⚠')
                          : '✓'
                        const claseIcono = !r.passed
                          ? (r.severity === 'error' ? 'fail' : 'warn')
                          : 'ok'
                        return (
                          <div key={r.rule_id} className="resultado">
                            <span className={`estado ${claseIcono}`}>{icono}</span>
                            <div className="info">
                              <div className="msg">
                                {r.mensaje || r.message}{' '}
                                <span className={`badge ${r.severity}`}>
                                  {r.severity === 'error' ? 'error' : 'advertencia'}
                                </span>
                                {!r.passed && (
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
          Copia y pega estos prompts en cualquier IA (ChatGPT, Claude, etc.) para corregir cada problema.
        </p>
        <div className="ia-cards">
          {prompts.length === 0 ? (
            <p className="ia-empty">No hay problemas detectados. ¡Felicidades!</p>
          ) : (
            prompts.map((p) => (
              <div key={p.rule_id} className="ia-card">
                <div className="head">
                  <span className="rule">{p.rule_id}</span>
                  <button
                    className="btn-copiar"
                    onClick={() => copiar(p.rule_id, p.prompt)}
                  >
                    {copiado === p.rule_id ? '¡Copiado!' : 'Copiar'}
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
