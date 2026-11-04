# Bitácora semanal — Semana 11

## Datos generales

- **Integrante:** IvanSanchezSil
- **Semana:** 11
- **Fechas:** 2026-11-03 a 2026-11-09
- **Rol:** Motor de reglas / Procesamiento (Int3)
- **Rama de trabajo:** `semana11-motor-ficha` (por crear desde `master`)
- **Estado:** Implementación y pruebas completadas (F-1). Pruebas pendientes: F-2, F-3, F-4, F-5, F-6, F-7.

## Objetivos de la semana

Cerrar las tareas pendientes del módulo de captura de ficha según el handover §6.3, sobre la base de la auditoría 2026-10-26:

1. Implementar contexto `caratula_ficha` en `validator/extractor.py`.
2. Implementar `seleccion` y `quitar_sufijo` en `validator/analizadores.py`.
3. Definir reglas `ficha_anio`, `ficha_titulo`, `ficha_autores`, `ficha_asesor`, `ficha_palabras_clave` en `reglas_ficha.yaml`.
4. Actualizar `validator/compilador.py` para que `_ficha` marque `detectado` solo con valor no vacío.
5. Crear/actualizar pruebas: `tests/_caratula_real.py`, `tests/test_captura_ficha.py`, `tests/test_constancia.py`.
6. Actualizar `scripts/eval_contra_plantillas.py` para aceptar `reglas` y `rules`.
7. Resolver decisión de dominio sobre `palabras_clave_minimo` (error vs warning vs exención).

## Actividades realizadas

| Fecha | Actividad | Evidencia |
|-------|-----------|-----------|
| 2026-11-03 | Implementación de contexto `caratula_ficha` en `validator/extractor.py` | Commit `c6f7ed3` (F-1) |
| 2026-11-03 | Definición de reglas en `reglas_ficha.yaml` (F-3) | Commit `c6f7ed3` (F-3) |
| 2026-11-03 | Actualización de pruebas en `tests/` (F-5) | Commit `c6f7ed3` (F-5) |
| 2026-11-03 | Actualización de compilador (`validator/compilador.py`) (F-4) | Commit `c6f7ed3` (F-4) |
| 2026-11-03 | Actualización de scripts (`scripts/eval_contra_plantillas.py`) (F-6) | Commit `c6f7ed3` (F-6) |
| 2026-11-03 | Actualización de plan (`PLAN_SEMANA11_MOTOR_FICHA.md`) | Commit `c6f7ed3` (F-1) |

## Evidencias producidas

| Archivo | Commit | Descripción |
|---------|--------|-------------|
| `validator/extractor.py` | `c6f7ed3` | Añadido `_caratula_ficha_paras()`, `is_caratula_ficha()` y soporte `contexto="caratula_ficha"` |
| `reglas_ficha.yaml` | `c6f7ed3` | Definición de `ficha_anio`, `ficha_titulo`, `ficha_autores`, `ficha_asesor`, `ficha_palabras_clave` |
| `tests/_caratula_real.py` | `c6f7ed3` | Fixture con dos autores, año con `sectPr`, prefijo/sufijo, palabras clave con punto |
| `tests/test_captura_ficha.py` | `c6f7ed3` | Pruebas de captura de ficha |
| `tests/test_constancia.py` | `c6f7ed3` | Pruebas de constancia |
| `validator/compilador.py` | `c6f7ed3` | Ajuste de `_ficha` para marcar `detectado` solo con valor no vacío |
| `scripts/eval_contra_plantillas.py` | `c6f7ed3` | Soporte para `reglas`/`rules`

## Relación con competencias curriculares

| Competencia | Evidencia esperada |
|-------------|-------------------|
| Ingeniería de Software II | Arquitectura del extractor, análisis de contexto, manejo de casos borde |
| Estructura de Datos | Modelado de contexto de extracción, mapeo nodo → página |
| Redes de Computadoras I | (No aplica directamente; motor puro) |
| Ingeniería de Software I | Bitácora semanal, documentación de planificación |

## Dificultades y aprendizajes

(Por completar durante la semana)

## Plan de la semana siguiente

- Verificar que las pruebas de captura de ficha pasen contra documentos reales.
- Revisar paridad con el motor legacy si es necesario.
- Documentar decisiones tomadas en `docs/HANDOVER_AUDITORIA_2026-10-26.md` o bitácora correspondiente.
