# Semana 9.2 — Bitácora de trabajo

**Integrante**: IvanSanchezSil (Int3 — Motor de reglas / Procesamiento)
**Fecha**: 2026-10-21
**Rama**: `linter-config-invalida` (antes `semana9.2`; creada desde
`origin/semana8-deposito-ficha` en `cccd7a3`)
**Estado**: En progreso

---

## Objetivo de la semana

Arreglar falsos verdes y errores de configuración disfrazados de fallos del
estudiante en `validator/analizadores.py`. Mejorar la confianza del semáforo
evitando que reglas con configuración inválida pasen como éxitos o fallen
por error del motor.

## Tareas planificadas

### T3 — Falsos verdes en `analizadores.py` (prioridad 1, pequeña) — **hecho**

**Problema detectado:**

1. `AnalizadorListaObligatoria` con `items: []` → devuelve
   `(True, "items_obligatorios=0 completo")`. No comprueba nada y pasa como
   éxito.

2. `AnalizadorPaginacion` sin `xpaths` (o con menos de 2) → falla con
   `(False, "paginacion requiere xpaths (>=2)")`. El estudiante recibe un
   error de formato que no es suyo.

**Diagnóstico:**

- `lista_obligatoria` vacía: el analizador no detecta que la regla está
  vacía. Debería **invalidar la regla** (config error), no pasar como éxito.
- `paginacion` sin xpaths: el error de configuración se muestra como **fallo
  del documento**, no del motor. El estudiante se confunde.

**Plan de implementación (realizado):**

1. **`validator/dsl_check.py` (linter)**: nuevas funciones `_lint_lista_obligatoria`
   y `_lint_paginacion` que detectan la configuración inválida **al cargar el
   DSL**. El linter corre antes de construir los analizadores, así que el error
   sale como `DSLValidationError` y la API lo traduce a **500 "configuración de
   reglas inválida"** (no a un 422 que culpa al documento del estudiante).

2. **`validator/analizadores.py` (red de seguridad)**: nueva excepción
   `ConfigurationError` y validación en el `__init__` de
   `AnalizadorListaObligatoria` (exige `items` no vacío) y
   `AnalizadorPaginacion` (exige ≥ 2 `xpaths`). Así, aunque se compile con
   `linter=False`, la configuración inválida se rechaza al construir el
   analizador y no llega a "evaluar" un documento.

3. **Tests** (`tests/test_f4_ingenieria.py`): 8 tests nuevos que cubren los dos
   caminos (con y sin linter) y las variantes (`items: []`, `items` ausente,
   `xpaths: []`, un solo `xpath`).

**Por qué el linter y no solo el `__init__`:**

`ConfigurationError` hereda de `ValueError`, y en `api.py` el `except ValueError`
(para partes faltantes del DOCX) responde **422** culpando al archivo del
estudiante. Con la detección en el linter, el error sale antes como
`DSLValidationError`, que la API maneja como **500 de configuración del
servidor**. Es la diferencia entre "tu tesis está mal" y "el motor está mal".

**Archivos tocados:**

- `validator/dsl_check.py` (linter: `_lint_lista_obligatoria`, `_lint_paginacion`)
- `validator/analizadores.py` (`ConfigurationError`, validación en `__init__`)
- `tests/test_f4_ingenieria.py` (8 tests nuevos)
- `docs/semana9.2_trabajo_ivanSanchezSil.md` (esta bitácora)

**Criterios de aceptación (cumplidos):**

- [x] `lista_obligatoria` con `items: []` no puede pasar como verde: el linter
      lo detecta y el `__init__` lo rechaza.
- [x] `paginacion` sin `xpaths` (o con < 2) no se muestra como fallo del
      documento: es error de carga del DSL.
- [x] Tests existentes siguen pasando.
- [x] Suite: `pytest tests/ -v` → **499 passed, 1 skipped**.
- [x] `ruff check`, `ruff format --check`, `mypy validator/ scripts/` limpios.

---

### T2 — Endurecer el linter del DSL (prioridad 2) — **hecho**

**Problema detectado:**

El linter (`validator/dsl_check.py`) validaba el DSL al cargar, pero dejaba
es pasar cinco clases de configuración inválida. Cada una se manifestaba en
runtime, y dos de ellas **sin aviso**:

| Caso | Efecto con el linter anterior |
|------|-------------------------------|
| Sección mal escrita (`atributo_xmls`) | El compilador no la reconoce: la regla **desaparece del reporte** en silencio. El estudiante ve un semáforo verde sobre una comprobación que nunca se hizo. |
| XPath con prefijo desconocido (`//wp:ind`) | Compila bien y revienta al **evaluar** el documento, con un `XPathEvalError` que la API muestra al estudiante como si fuera un defecto de su tesis. |
| Severidad inventada (`aviso`) | `Severity(...)` se construye al evaluar: `ValueError` en runtime, con el estudiante esperando el resultado. |
| `aplicar_si` con valor mal escrito (`tinv_cuantiativo`) | El linter ya detectaba la **clave** mal escrita, pero no el **valor**: la condición no casa con nada, la regla nunca aplica y el semáforo queda verde sin comprobar. |
| `id` de regla duplicado | Doble conteo en el resumen y dos observaciones indistinguibles con el mismo identificador. |

**Plan de implementación (realizado):**

1. **`validator/dsl_check.py`**: nuevas funciones `_lint_secciones_desconocidas`
   (compara cada clave de regla contra las secciones y claves conocidas, y
   sugiere la correcta por similitud difusa), `_lint_xpath` (valida los
   prefijos de namespace de cada XPath contra los que declara el extractor,
   ignorando los ejes como `following-sibling::`), `_lint_severidad` (comprueba
   el valor contra el catálogo `error`/`warning`), `_lint_ids_duplicados`
   (cuenta ids repetidos) y `_lintar_valor_tipo_documento` (contrasta el valor
   de `aplicar_si` contra los tipos que declara la sección `deteccion_tipo`).

2. **Tests** (`tests/test_t2_linter.py`): 28 tests nuevos. Cada caso se cubre
   dos veces: por el hallazgo del linter y por el control de que **antes**
   pasaba inadvertido (la regla se perdía al compilar, el XPath reventaba al
   evaluar). Se incluyen los falsos positivos a evitar: los ejes de XPath
   (`following-sibling::w:p`), los prefijos válidos (`w:`, `a:`, `r:`) y los
   campos propios de cada analizador.

3. **Guard de producción**: un test verifica que `reglas_unt.yaml`,
   `reglas_unt_pendientes.yaml` y `reglas_ficha.yaml` siguen pasando el linter
   sin hallazgos.

**Por qué el linter y no solo el runtime:**

Igual que en T3, el error de configuración debe salir **al cargar** las
reglas, no al validar un documento. Un error del motor que se descubre
mientras el estudiante espera su reporte se presenta como si fuera culpa de
su tesis; un error de carga se presenta como 500 de configuración.

**Archivos tocados:**

- `validator/dsl_check.py` (5 funciones de lint nuevas)
- `tests/test_t2_linter.py` (28 tests nuevos)
- `docs/semana9.2_trabajo_ivanSanchezSil.md` (esta bitácora)

**Criterios de aceptación (cumplidos):**

- [x] Los 5 casos se detectan al cargar el DSL, no al evaluar un documento.
- [x] Ningún YAML de producción produce hallazgos nuevos.
- [x] Sin falsos positivos: ejes de XPath, prefijos válidos y campos propios
      de los analizadores no se reportan.
- [x] Suite: `pytest tests/ -v` → **527 passed, 1 skipped** (499 + 28).
- [x] `ruff check`, `ruff format --check`, `mypy validator/ scripts/` limpios.

---

## Notas

- No se toca `api.py`, `api_models.py`, `frontend/`, `notificacion.py`,
  `dspace.py`.
- La rama `linter-config-invalida` parte de `origin/semana8-deposito-ficha`
  (que ya tiene el PR #56 mergeado). El PR es el **#59**, con base en esa
  rama de integración: así el diff muestra solo los commits de esta semana
  y no mezcla el trabajo de ficha/buzón/constancias de otros integrantes.

---

## Historial de cambios

| Fecha | Commit | Qué |
|-------|--------|-----|
| 2026-10-21 | `a89f2d7` | T3: `ConfigurationError` + validación en `__init__` de los dos analizadores |
| 2026-10-21 | `199ab3b` | T3: tests de configuración inválida (8 casos) |
| 2026-10-21 | `56bf51f` | T3: detección en el linter (`_lint_lista_obligatoria`, `_lint_paginacion`) |
| 2026-10-21 | `2b25586` | T3: bitácora de la semana |
| 2026-10-21 | (T2) | T2: endurecer el linter (secciones, XPath, severidad, ids, `aplicar_si`) |
| 2026-10-21 | (T2) | T2: tests de los 5 casos (28 tests) |
| 2026-10-21 | (T2) | T2: bitácora de la semana |
