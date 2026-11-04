# Semana 10 — Bitácora de trabajo

**Integrante**: IvanSanchezSil ( — Motor de reglas / Procesamiento)  
**Fecha**: 2026-10-27  
**Rama**: `semana10-auditoria-motor`  
**Base**: `origin/semana8-deposito-ficha` (PR #56 ya mergeado)  
**Estado**: En progreso  
**Contexto**: Auditoría `AUDIT_COMPORTAMIENTO_VISTOBUENO_2026-10-26.md`

## Objetivo de la semana

Corregir los hallazgos de la auditoría que corresponden a  (Motor/Reglas), documentando y planificando primero, sin tocar código hasta tenerlo claro. Priorizar correctitud del motor (falsos positivos / hallazgos erróneos).

## Hallazgos asignados a 

| ID | Severidad | Archivos | Acción prevista | Estado |
|----|-----|----------|-----------------|--------|
| AUD-01 | Alta | `validator/analizadores.py` (`_norm_indice`) | Separar normalización entre títulos del cuerpo (sin recorte romano falso) e ítems del índice (mantener lógica actual). Falso positivo con "General" y títulos acabados en i/l/v/x/c. | Hecho (b947a27) |
| AUD-02 | Alta | `validator/tokenizer.py`, `validator/analizadores.py`, `reglas_unt.yaml` | Arreglar `anexos_minimos_*`: permitir `seccion()` hasta final (`hasta_final: true`), incluir títulos `Anexo N.` en `_texto()`, mostrar **todos** los faltantes (eliminar `[:8]`). Sincronizar `tests/_mutations.py`. | Hecho (707960d) |
| AUD-03 | Media | `validator/analizadores.py`, `validator/checks.py`, `tests/test_auditoria_motor.py` | `encontrado` legible: culpables primero, valores sin repr crudo, página del nodo infractor. Formato replicado en el motor legacy (paridad literal). | Hecho (166553f) |
| AUD-04 | Media | `reglas_unt.yaml` | Añadir notas `EVALUADO:` a `caratula_titulo_trabajo_tamano` y `caratula_optar_grado_tamano` (plantilla usa 13pt/12pt). | Hecho (feafa82) |
| AUD-05 | Media | `reglas_unt.yaml` / analizadores | Decisión: endurecer selectores frágiles (`/w:r[1]`, `following-sibling::w:p[1]`) o documentar. | Hecho: documentado y diferido (nota EVALUADO en el bloque de carátula) |
| AUD-06 | Baja | `validator/analizadores.py` (`_sigpalabra`) | Decisión: revisar umbral `>= 4` auto-pasa entradas cortas. | Hecho: umbral mantenido y documentado en el docstring + test |
| AUD-07 | Baja | `reglas_unt.yaml` | Decisión: restringir `caratula_optar_grado_tamano` al "grado de Bachiller" o añadir `EVALUADO:`. | Hecho: XPath acotado a "bachiller" + `n_a_si_sin_nodos` |
| AUD-20 | Media | `tests/_docx_builder.py`, `tests/docx_factory.py`, `tests/test_auditoria_motor.py` | Fixtures con estructura real (anexos Título1 "Anexo N.", título "GENERAL" con entrada de índice paginada) y tests de regresión para AUD-01/AUD-02. | Hecho (b892478) |
| AUD-15 | Media | `validator/exportador.py` | Escape HTML en `message`/`found`/`expected`/`prompt` al inyectarlos en el Markdown/PDF (previene rotura de tablas y XSS). | Hecho (AUD-15) |

**Coordinar:** AUD-21 (paridad) con AUD-03.

## Plan de trabajo

Orden propuesto:

1. **Documentación y planificación** (hecho) — crear bitácora semana 10 + plan detallado.
2. **AUD-01** — Separar normalización de títulos del cuerpo e ítems del índice. (Hecho)
3. **AUD-02** — `seccion(hasta_final)`, incluir TITULO en búsqueda y quitar el truncado. (Hecho)
4. **AUD-20** — Blindar AUD-01/AUD-02 con fixtures de estructura real y tests de regresión. (Hecho)
5. **AUD-03** — Culpables primero, valores legibles y página del nodo infractor; paridad legacy↔DSL verificada. (Hecho)
6. **AUD-04** — Notas `EVALUADO:` en los tamaños de carátula, verificadas contra la plantilla oficial. (Hecho)
7. **AUD-05/AUD-06/AUD-07** — Decisiones tomadas: documentar y diferir los selectores frágiles (AUD-05), mantener el umbral `>= 4` documentado (AUD-06) y acotar la regla de "optar" a "bachiller" (AUD-07). (Hecho)
8. **AUD-15** — Escape HTML en `message`/`found`/`expected`/`prompt` en `validator/exportador.py` para prevenir rotura de tablas Markdown y XSS en PDF. (Hecho)

## Criterios de aceptación

- [x] AUD-01 corregido con test que falle antes y pase después
- [x] AUD-02 corregido: detecta anexos con estructura Título1 "Anexos" + "Anexo N.", muestra todos los faltantes
- [x] AUD-20: fixtures de estructura real y tests de regresión para AUD-01/AUD-02
- [x] AUD-03: `encontrado` legible, culpables primero, página correcta
- [x] AUD-04: notas `EVALUADO:` añadidas
- [x] AUD-05: selectores frágiles documentados (endurecimiento diferido)
- [x] AUD-06: umbral `>= 4` mantenido y documentado
- [x] AUD-07: `caratula_optar_grado_tamano` acotada a "bachiller" (n/a en otras titulaciones)
- [x] AUD-15: `message`/`found`/`expected`/`prompt` escapados con `html.escape()` en `validator/exportador.py`
- [x] `tests/_mutations.py` sin cambios: no se agregaron reglas nuevas
- [x] `pytest tests/ -v` sin regresiones (**676 passed, 1 skipped**)
- [x] linter DSL limpio en `reglas_unt.yaml`, `reglas_unt_pendientes.yaml` y `reglas_ficha.yaml`
- [x] `tests/test_paridad_formatos.py` OK
- [x] `nix flake check` OK
- [x] `ruff check`, `ruff format --check`, `mypy validator/ scripts/` OK

## Riesgos

- Cambiar `found` puede romper paridad → revisar `test_paridad_formatos.py` siguiendo el patrón de `7ff5cd3`
- Añadir `hasta_final` a `seccion()` puede afectar otras reglas → opcional, por defecto mantener comportamiento actual
- Incluir `TITULO` en búsqueda de anexos → limitar al contexto de esa regla, no global

## Evidencia

Plan detallado en `docs/PLAN_SEMANA10_AUDITORIA_MOTOR.md`

Fixtures y regresiones: `tests/test_auditoria_motor.py` (AUD-20, commit `b892478`; AUD-03, commit `166553f`). Suite completa: **632 passed, 1 skipped**. Verificado que los tests nuevos fallan con el comportamiento anterior (AUD-01: `indice_apunta_secciones=False`; AUD-02: `anexos_minimos_cuantitativo=False`; AUD-03: la página era la del primer nodo, no la del culpable). `docs/ejemplo_respuesta_motor.json` regenerado con el CLI contra el MANUAL. AUD-04: tamaños de la plantilla oficial verificados (`Título` sz 26 = 13 pt; `Para Optar` sz 24 = 12 pt). AUD-05/AUD-06/AUD-07: decisiones tomadas y documentadas; AUD-07 añade `n_a_si_sin_nodos` al analizador XML para que la regla acotada a "bachiller" no genere un falso "no encontrado" en otras titulaciones (tests `test_aud07_*`). Suite final de la rama: **676 passed, 1 skipped**. AUD-15: `validator/exportador.py` ahora escapa `message`/`found`/`expected`/`prompt` con `html.escape()` antes de inyectarlos en Markdown/PDF (tests `test_exportador.py` verdes). Tras actualizar con `origin/master` (merges `3370062` y `e91ca2b`): **674 passed, 3 skipped, 6 xfailed**; `ruff`, `ruff format --check`, `mypy` y `nix flake check` OK.
