# Bitácora semanal — Semana 11

## Datos generales

- **Integrante:** IvanSanchezSil
- **Semana:** 11
- **Fechas:** 2026-11-03 a 2026-11-09 (cierre el 2026-11-11)
- **Rol:** Motor de reglas / Procesamiento (Int3)
- **Rama de trabajo:** `semana11-motor-ficha`
- **Estado:** **Completada** (F-1 a F-7). Suite en verde: `857 passed, 4 skipped`, sin `xfail`.

## Objetivos de la semana

Cerrar las tareas pendientes del módulo de captura de ficha según el handover de la auditoría 2026-10-26 (AUD-24 a AUD-27) y el handover operativo `docs/HANDOVER_PENDIENTES_2026-11-11.md` §3:

1. Implementar contexto `caratula_ficha` en `validator/extractor.py`.
2. Implementar `seleccion` y `quitar_sufijo` en `validator/analizadores.py`.
3. Definir las reglas de captura en `reglas_ficha.yaml`.
4. Actualizar `validator/compilador.py` para que `_ficha` marque `detectado` solo con valor utilizable.
5. Crear/actualizar pruebas: `tests/_caratula_real.py`, `tests/test_captura_ficha.py`, `tests/test_constancia.py`.
6. Actualizar `scripts/eval_contra_plantillas.py` para aceptar `reglas` y `rules`.
7. Resolver la decisión de dominio sobre `palabras_clave_minimo`.

## Actividades realizadas

| Fecha | Actividad | Evidencia |
|-------|-----------|-----------|
| 2026-11-03 | Plan de la semana 11 | Commit `73e9445` |
| 2026-11-03 | Contexto `caratula_ficha` en `validator/extractor.py` (F-1) | Commit `0447530` |
| 2026-11-03 | `seleccion` / `quitar_sufijo` en `validator/analizadores.py` (F-2) | Commit `21b08f2` |
| 2026-11-03 | Reglas iniciales de ficha (F-3) | Commit `833ec39` |
| 2026-11-03 | `detectado=false` para valores vacíos (F-4) | Commit `f6d3810` |
| 2026-11-11 | Cierre de AUD-24 a AUD-27: autores, asesor, año, palabras clave y fixture real | Commit `a2c753d` |
| 2026-11-11 | `eval_contra_plantillas.py` acepta `reglas` y `rules` (F-6) | Commit `212d192` |
| 2026-11-11 | Actualización de plan, bitácora y estado de la auditoría | Commit de docs de esta rama |
| 2026-11-12 | Merge de `upstream/master` `9fdfc57` (PR #73) sin retroceder la auditoría | Commit `1569a61` |
| 2026-11-12 | Correcciones de la revisión del PR #75: tildes, autores, asesor, año y valores inservibles | Commit `b060566` |
| 2026-11-12 | Linter de `extraccion`: regex de `quitar_prefijo`/`quitar_sufijo` y `seleccion` | Commit `6602c90` |

## Evidencias producidas

| Archivo | Commit | Descripción |
|---------|--------|-------------|
| `validator/extractor.py` | `0447530` | `_caratula_ficha_paras()`, `is_caratula_ficha()` y `contexto="caratula_ficha"` |
| `validator/analizadores.py` | `21b08f2`, `a2c753d` | `seleccion: primero \| ultimo \| primero_no_vacio` y `quitar_sufijo` |
| `reglas_ficha.yaml` | `833ec39`, `a2c753d` | Autores por párrafo, asesor del párrafo siguiente, año de portada y palabras clave limpias |
| `validator/compilador.py` | `f6d3810`, `a2c753d` | `_valor_utilizable`: cadena vacía, solo espacios y lista vacía → `valor=None`, `pagina=None`, `detectado=false` |
| `tests/_caratula_real.py` | `a2c753d` | Carátula real con `RESUMEN` como Título1, abstract y palabras clave |
| `tests/test_captura_ficha.py` | `a2c753d` | Contrato de AUD-24 a AUD-27 sin `xfail`; título, abstract y valores inservibles |
| `tests/test_constancia.py` | `a2c753d` | Una constancia por autor real, sin `xfail` |
| `scripts/eval_contra_plantillas.py` | `212d192` | `_reglas_de` / `_total_mecanizadas` aceptan `reglas` y `rules` |
| `tests/test_eval_contra_plantillas.py` | `212d192` | Tests de F-6 con ambos formatos |
| `validator/extractor.py` | `b060566` | Sin `sectPr`, `caratula_ficha` corta en el primer encabezado |
| `validator/dsl_check.py` | `6602c90` | Valida regex de `quitar_prefijo`/`quitar_sufijo` y `seleccion` |
| `tests/test_captura_ficha.py` | `b060566` | Casos límite: tilde sin asesor, etiqueta y autor juntos, asesor con párrafo vacío, año frente a referencias |

## Verificación

- `pytest tests/ -q` → `857 passed, 4 skipped` (sin `xfail`).
- Tesis real de la auditoría: dos autores, `Dra. Apellido, Nombre`, año `2026`, abstract completo y `['Educación', 'Cultura', 'Identidad cultural']`.
- `scripts/eval_contra_plantillas.py` → funciona con `reglas_ficha.yaml` (clave `reglas`) y con `unt_format_rules_schema.yaml` (clave `rules`).
- `ruff check`, `ruff format --check` y `mypy validator/ scripts/` → limpios.
- Linter DSL → 0 errores en `reglas_ficha.yaml` y `reglas_unt.yaml`.

## Dificultades y aprendizajes

- El contexto `caratula_ficha` incluye todo el body cuando el DOCX no tiene un `sectPr` que cierre la carátula (el factory no lo tiene). Por eso el filtro del año debe exigir una **línea de portada** (año suelto o ciudad+año), no cualquier año: así no gana el 2024 del título ni los años de las referencias.
- El fixture `_caratula_real.py` tenía `RESUMEN` como párrafo normal; `seccion()` necesita un estilo de encabezado. Corregir el fixture (no el analizador) fue lo correcto.
- El nombre de archivo de la constancia se sanea (sin comas ni acentos); el **contenido** conserva el nombre real del autor. Los tests ahora distinguen ambos.
- El asesor se resuelve con `primero_no_vacio`: sirve tanto si la etiqueta está en un párrafo aparte como si comparte párrafo con el nombre.
- `palabras_clave_minimo` se mantiene en `error` por decisión del 2026-11-08; las 5 plantillas oficiales siguen en rojo a propósito.

## Plan de la semana siguiente

- Cerrar los hallazgos restantes de Int3: AUD-01, AUD-02, AUD-04, AUD-05, AUD-06 y AUD-20.
- Revisar el bloque de aviso de `AGENTS.md` cuando estén cerrados todos los hallazgos de la tabla §11.
- Mantener la verificación contra la tesis real y las 5 plantillas en cada cambio del motor.
