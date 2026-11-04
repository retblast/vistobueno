# Plan Semana 11 — Captura de ficha (Motor/Reglas)

**Fecha:** 2026-11-03  
**Responsable:** IvanSanchezSil (Motor de reglas / Procesamiento)  
**Base:** `origin/master` (después de mergear PR #73)  
**Rama:** `semana11-motor-ficha` (a crear desde `master`)  
**Fuente:** `docs/HANDOVER_AUDITORIA_2026-10-26.md` §6.3 y §12

---

## Principio

Documentar y planificar primero. Sin tocar código hasta tener claro el enfoque. Commits atómicos por hallazgo/tarea lógica, sin `Co-Authored-By`. Rama creada desde `master`, no desde `semana10-auditoria-motor`.

---

## Alcance (tareas del handover §6.3)

| ID | Sev | Archivos | Acción |
|----|-----|----------|--------|
| F-1 | Alta | `validator/extractor.py` | ✅ **HECHO**: Añadir contexto `caratula_ficha`: incluye el párrafo que porta `w:pPr/w:sectPr` sin tocar `_caratula` ni las 49 reglas normales. Añadir `is_caratula_ficha` y soporte `contexto="caratula_ficha"` en `xpath`. |
| F-2 | Alta | `validator/analizadores.py` | ✅ **HECHO**: `AnalizadorExtraccion` con `seleccion: primero | ultimo` (tras `filtro`) y `quitar_sufijo` (regex). |
| F-3 | Alta | `reglas_ficha.yaml` | ✅ **HECHO**: `ficha_anio` (`seleccion: ultimo`), `ficha_titulo` (`quitar_prefijo`), `ficha_autores` (`etiqueta: autores`, modo lista), `ficha_asesor` (sin cambios), `ficha_palabras_clave` (`quitar_sufijo: \s*\.\s*$`). |
| F-4 | Media | `validator/compilador.py` | Pendiente |
| F-5 | Alta | `tests/_caratula_real.py`, `tests/test_captura_ficha.py`, `tests/test_constancia.py` | Pendiente |
| F-6 | Media | `scripts/eval_contra_plantillas.py` | Pendiente |
| F-7 | Media | Decisión de dominio | Pendiente |

---

## Diagnóstico por tarea

### F-1: Extractor — `caratula_ficha`
- **Problema actual:** `_caratula` usa el salto de sección (`w:pPr/w:sectPr`) como límite; el párrafo que *contiene* el `sectPr` queda excluido. La línea de año (`Trujillo - Perú, 2026`) suele estar en ese párrafo.
- **Solución:** crear conjunto `_caratula_ficha` que incluya el párrafo con `sectPr` (solo ese). Exponer `is_caratula_ficha(nodo)` y aceptar `contexto="caratula_ficha"` en `xpath(...)`. No alterar `_caratula` ni las 49 reglas existentes.

### F-2: Analizadores — `seleccion` y `quitar_sufijo`
- **Necesidad:** varias capturas de ficha requieren el *último* match (año) o el *primero* (título). El analizador genérico (`AnalizadorExtraccion` o similar) debe aceptar `seleccion: primero | ultimo` y aplicar tras `filtro`.
- `quitar_sufijo`: patrón opcional para recortar sufijo tipo `, Trujillo 2026` del título; **no activar** hasta que la decisión 5.2 se cierre (conservar sufijo por defecto).
- Limpieza de palabras clave: quitar punto final y entradas vacías tras normalización.

### F-3: Reglas de ficha en `reglas_ficha.yaml`
- Cada regla declara `contexto: caratula_ficha`, `filtro` (regex), `seleccion` y, opcionalmente, `quitar_sufijo`.
- `ficha_anio`: filtro `\b(19|20)\d{2}\b`, `seleccion: ultimo`.
- `ficha_titulo`: `quitar_sufijo` opcional (desactivado por ahora).
- `ficha_autores`: un párrafo = una persona; normalizar quitando etiqueta "Autores:".
- `ficha_asesor`: si el nodo extraído es vacío, `detectado=false`.
- `ficha_palabras_clave`: limpiar punto final y entradas vacías.

### F-4: Compilador — `_ficha`
- El dict `ficha` que se incluye en el reporte debe poner `detectado=true` solo si hay valor no vacío; en caso contrario `detectado=false`, `valor=None`, `pagina=None`.

### F-5: Tests
- `tests/_caratula_real.py`: fixture con estructura real (dos autores, `sectPr` con año, prefijo/sufijo, palabras clave con punto, sin asesor).
- `tests/test_captura_ficha.py`: expectativas — año 2026, dos autores, título sin prefijo, palabras clave limpias, asesor vacío `detectado=false`.
- `tests/test_constancia.py`: quitar `xfail(strict=True)` tras corrección.
- Regresión explícita: el año 2024 del título no debe ganar sobre 2026 de la portada.

### F-6: `scripts/eval_contra_plantillas.py`
- Actualmente usa `rules_data["rules"]`; el DSL usa clave `reglas`. Hacer que acepte ambos (`rules_data.get("reglas") or rules_data.get("rules")`). Mantener `carpeta` obligatorio. Añadir test de integración con `reglas_unt.yaml`.

### F-7: Decisión `palabras_clave_minimo`
- Hoy es `error` y falla las 5 plantillas oficiales.
- AGENTS.md: decisión de dominio abierta.
- Handover §4: mantener `error` (las plantillas pueden fallar porque son plantillas).
- **Reunir al equipo** o decidir antes de cerrar las pruebas de ficha.

---

## Orden de ejecución sugerido

1. **F-1** — Extractor `caratula_ficha` (base para el resto).
2. **F-2** — Analizadores `seleccion` / `quitar_sufijo` / limpieza.
3. **F-3** — `reglas_ficha.yaml` con las 5 reglas usando `contexto: caratula_ficha` y `seleccion`.
4. **F-4** — `validator/compilador.py` ajuste de `_ficha`.
5. **F-5** — Tests: fixture, tests de captura, constancia (quitar xfails).
6. **F-6** — `eval_contra_plantillas.py` soporte `reglas`/`rules`.
7. **F-7** — Decisión `palabras_clave_minimo` (reunión/consenso).

---

## Verificación

- `pytest tests/ -q` → verde, sin regresiones, xfails eliminados.
- `nix flake check` → all checks passed.
- `ruff check`, `ruff format --check`, `mypy validator/ scripts/` → limpios.
- Linter DSL limpio en `reglas_ficha.yaml`, `reglas_unt.yaml`, `reglas_unt_pendientes.yaml`.
- Regenerar `docs/ejemplo_respuesta_motor.json` si cambia el formato de salida.

---

## Notas y riesgos

- **No tocar** `_caratula` ni las 49 reglas normales; `caratula_ficha` es solo para la captura de ficha.
- `quitar_sufijo` **no activado** hasta decisión 5.2; implementar la infraestructura pero dejar desactivado.
- Si el PR #73 aún no está mergeado, la rama se crea desde `origin/master` (commit `2d2f0ac` o posterior). No heredar commits de `semana10-auditoria-motor`.
- Commits atómicos, mensajes en español, prefijo convencional (`feat(motor): ...`, `test(motor): ...`, `docs: ...`).
- Sin `Co-Authored-By`.
- Actualizar `docs/semana11_trabajo_ivanSanchezSil.md` diariamente.

---

## Decisiones pendientes del equipo

1. `palabras_clave_minimo`: ¿`error` / `warning` / exención plantillas?
2. Sufijo del título (decisión 5.2): ¿quitar siempre / conservar / solo si es última línea de portada?

---

*Fin del plan. Se actualiza conforme avance la semana.*