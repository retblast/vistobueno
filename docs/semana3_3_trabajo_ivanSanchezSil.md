# Semana 3.3 — Trabajo realizado (F4 del plan DSL)

**Integrante**: IvanSanchezSil
**Rol**: Integrante 3 — Motor de reglas / Procesamiento
**Semana**: 3.3 de 14 (09/09/2026, dentro de la Semana 3 07/09–11/09)
**Proyecto**: VistoBueno — Validador automático de formato de tesis (UNT FECyC)
**Rama de trabajo**: `semana4-f4` (PR desde `fork/semana4-f4` hacia master de retblast)

---

## Objetivos del día

1. **F4** del plan `docs/PLAN_DSL.md`: mejoras de ingeniería —
   - **linter del DSL** (`validator/dsl_check.py`): errores de configuración
     en TIEMPO DE CARGA (no en runtime);
   - **cache de consultas XPath** por documento;
   - **traza del autómata** (estados recorridos).
2. Mantener el contrato intacto y la suite existente verde.

---

## Actividades realizadas

### Tarea 1 (F4): Linter del DSL

**Fecha**: 09/09/2026

Nuevo módulo `validator/dsl_check.py` con `linter(rules_data) -> List[str]` y
`linter_o_alzar()` (levanta `DSLValidationError`). Detecta:

- **regex inválida** en cualquier `patron`/`filtro` (incluye los `patron` de
  estados/transiciones de autómatas);
- **`comparacion` sin `esperado`** o sin `atributo` (eq/all_eq/contains) en
  `atributo_xml`/`presencia_xml`;
- **estados inalcanzables** y **aceptación inalcanzable** en `automata_pila`;
- **ciclos épsilon** (transiciones que no consumen y forman un ciclo) — el
  reconocedor greedy iteraría sin avanzar la entrada;
- estados **duplicados** o esquema **"todo opcional"** en `automata_secuencia`
  (sin estado de aceptación).

Se conectó al compilador: `CompilerDSL.compilar(rules_data, linter=True)`
valida antes de construir los analizadores (se puede desactivar con
`linter=False`). `reglas_unt.yaml` y `reglas_dsl_ejemplo.yaml` pasan sin
hallazgos (guard de tests).

### Tarea 2 (F4): Cache de XPath en `ExtractedDocx`

**Fecha**: 09/09/2026

`ExtractedDocx` ganó el método `xpath(parte, expr, contexto)` con cache por
`(parte, contexto, xpath)` y un campo `_cache`. `Analizador._nodos` delega en
él: dos secciones de una regla con el mismo XPath evalúan la consulta **una
sola vez** por documento (aunque una filtre por `contexto == "cuerpo"`).

### Tarea 3 (F4): Traza del autómata

**Fecha**: 09/09/2026

- `DFA.ruta_estados` y `PDA.ruta_estados` registran la ruta de estados del
  último `reconocer()`. En modo `backtracking` el `_dfs` ahora devuelve el
  camino ganador en lugar de solo un booleano.
- El DSL lo expone como `AutomataSecuencia.ultima_ruta` y
  `AutomataPila.ultima_ruta` (materia prima para F5, donde la traza entra al
  reporte coordinando el contrato con Integrante 1).

### Tarea 4 (F4): Decisión 3 — evaluación paralela NO incluida

**Fecha**: 09/09/2026

La paralelización del engine se omitió por decisión propia (decisión 3 del
plan): agrega complejidad a cambio de velocidad en documentos grandes y se
documenta como mejora futura opcional. Se actualizó `docs/PLAN_DSL.md`.

### Tarea 5 (F4): Tests y verificación

**Fecha**: 09/09/2026

`tests/test_f4_ingenieria.py` (21 tests): linter (reglas reales pasan,
regex inválida, comparaciones incompletas, estados inalcanzables, ciclo
épsilon, esquema todo-opcional, `DSLValidationError` al compilar, `linter=False`),
cache (misma consulta → mismo objeto; claves por contexto/xpath; parte
inexistente → error), y traza (DFA greedy/backtracking, PDA, secuencia y
pila vía analizadores).

**Resultado**: suite completa **138 tests verdes** (117 + 21) y
`PARIDAD: OK` en las 6 plantillas reales, dentro de `nix develop`.

---

## Evidencias producidas

| Evidencia | Archivo | Competencia curricular |
|-----------|---------|------------------------|
| Linter del DSL | `validator/dsl_check.py` | Ingeniería de Software II (validación en carga) |
| Cache de XPath | `validator/extractor.py` (`ExtractedDocx.xpath`), `validator/analizadores.py` | Estructura de Datos |
| Traza del autómata | `validator/automata.py` (`ruta_estados`), `validator/compilador.py` (`ultima_ruta`) | Lenguajes Formales y Autómatas |
| Tests F4 | `tests/test_f4_ingenieria.py` (21 tests) | Ingeniería de Software II |
| Documentación (cambios, decisiones) | `docs/CAMBIOS_MOTOR_DSL.md` (Paso 13), `docs/PLAN_DSL.md` (F4 ✅, decisión 3) | Ingeniería de Software I |
| Bitácora | `docs/semana3_3_trabajo_ivanSanchezSil.md` | — |

---

## Relación con competencias

| Competencia | Actividad |
|-------------|-----------|
| **Lenguajes Formales y Autómatas** | Traza de estados de DFA/PDA; detección estática de ciclos épsilon (riesgo de bucle infinito) |
| **Estructura de Datos** | Cache por clave `(parte, contexto, xpath)`; BFS de alcanzabilidad para estados inalcanzables |
| **Ingeniería de Software II** | Validación de configuración en carga (fail-fast), refactor aditivo sin romper contrato, 138 tests verdes |
| **Ingeniería de Software I** | Documentación técnica (CAMBIOS Paso 13, PLAN_DSL) |

---

## Dificultades y aprendizajes

- **El orden del linter vs. el compilador**: como `compilador.py` importa
  `dsl_check.py` para llamar a `linter_o_alzar`, el linter define sus propias
  secciones (no importa `SECCIONES_ANALIZADOR` del compilador) para evitar
  una dependencia circular.
- **Ciclos épsilon**: revisando el reconocedor greedy del PDA me di cuenta de
  una autotransición épsilon (`desde == hacia`, `consumir: False`) mantiene
  `progreso=True` y **no consume entrada** — bucle infinito garantizado. El
  linter lo detecta estáticamente antes de llegar a runtime.
- **`comparacion` sin esperado**: es un error silencioso en runtime (la
  comparación de atributo devuelve `False` con detalle), por eso F4 lo sube a
  error de carga.

---

## Pendiente / Plan semana siguiente

- [x] F4 completa: linter (`dsl_check.py`) + cache XPath + traza del autómata
- [x] Tests F4 (21) y suite completa **138 verdes** + `PARIDAD: OK`
- [x] Docs: `CAMBIOS_MOTOR_DSL.md` Paso 13, `PLAN_DSL.md` (F4 ✅, decisión 3),
      `README.md`, bitácora
- [x] Commit atómico y push a `fork/semana4-f4` (PR desde `semana4-f4`)
- [ ] **F5** (última del plan, decisión 1): traza en el reporte —
      `RuleResult.detalle_traza` **o** embeber en `encontrado`. Coordinar con
      Integrante 1 el contrato (subiría `CONTRATO_API.md` a v1.1)