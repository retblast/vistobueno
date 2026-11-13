# Plan Semana 11 — Captura de ficha (Motor/Reglas)

**Fecha:** 2026-11-03  
**Responsable:** IvanSanchezSil (Motor de reglas / Procesamiento)  
**Base:** `upstream/master` `9fdfc57` (PR #73) + merge de `master` en la rama del PR #75  
**Rama:** `semana11-motor-ficha`  
**Fuente:** `docs/HANDOVER_AUDITORIA_2026-10-26.md` §4 (AUD-24 a AUD-27), §6 y §12; handover operativo del PR: `docs/HANDOVER_PENDIENTES_2026-11-11.md` §3

---

## Principio

Documentar y planificar primero. Sin tocar código hasta tener claro el enfoque. Commits atómicos por hallazgo/tarea lógica, sin `Co-Authored-By`. Rama creada desde `master`, no desde `semana10-auditoria-motor`.

---

## Alcance (tareas de AUD-24 a AUD-27)

| ID | Sev | Archivos | Acción |
|----|-----|----------|--------|
| F-1 | Alta | `validator/extractor.py` | ✅ **HECHO**: contexto `caratula_ficha`: incluye el párrafo que porta `w:pPr/w:sectPr` sin tocar `_caratula` ni las 49 reglas normales. `is_caratula_ficha` y soporte `contexto="caratula_ficha"` en `xpath`. |
| F-2 | Alta | `validator/analizadores.py` | ✅ **HECHO**: `AnalizadorExtraccion` con `seleccion: primero \| ultimo \| primero_no_vacio` (tras `filtro`) y `quitar_sufijo` (regex). |
| F-3 | Alta | `reglas_ficha.yaml` | ✅ **HECHO**: `ficha_autores` recorre todos los párrafos de autor (salta ORCID, corta en ASESOR/Línea); `ficha_asesor` prefiere el párrafo siguiente con `seleccion: primero_no_vacio`; `ficha_anio` filtra la línea de portada y toma la última; `ficha_titulo` quita el prefijo; `ficha_palabras_clave` quita la puntuación final. |
| F-4 | Media | `validator/compilador.py` | ✅ **HECHO**: `_valor_utilizable` publica `detectado=false`, `valor=None`, `pagina=None` para cadena vacía, solo espacios, `None` y lista vacía. |
| F-5 | Alta | `tests/_caratula_real.py`, `tests/test_captura_ficha.py`, `tests/test_constancia.py` | ✅ **HECHO**: fixture con `RESUMEN` como Título1 y abstract real; contrato de captura sin `xfail`; constancia de los dos autores. |
| F-6 | Media | `scripts/eval_contra_plantillas.py` | ✅ **HECHO**: `_reglas_de` acepta `reglas` y `rules`; `_total_mecanizadas` cuenta según el formato. Test en `tests/test_eval_contra_plantillas.py`. |
| F-7 | Media | Decisión de dominio | ✅ **DECIDIDO** (2026-11-08): `palabras_clave_minimo` se mantiene en `error`; las 5 plantillas oficiales siguen en rojo a propósito. |

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
- Cada regla declara `contexto: caratula_ficha`, `filtro` (regex), `seleccion` y, opcionalmente, `quitar_prefijo`/`quitar_sufijo`.
- `ficha_anio`: filtro de línea de portada (año suelto o ciudad+año), `seleccion: ultimo`; así 2026 gana sobre el 2024 del título y sobre las referencias.
- `ficha_titulo`: `quitar_prefijo` para «Título del trabajo de investigación:»; el sufijo `, Trujillo 2024` se conserva (decisión 5.2).
- `ficha_autores`: un párrafo = una persona; recorre todos los párrafos tras `AUTORES:`/`AUTORA:`, salta ORCID e instrucciones entre paréntesis y corta en `ASESOR(A):`/`Línea de investigación:`.
- `ficha_asesor`: `seleccion: primero_no_vacio` sobre la etiqueta y el párrafo siguiente; cubre ambos formatos.
- `ficha_palabras_clave`: limpia la puntuación final y las entradas vacías.

### F-4: Compilador — `_ficha`
- El dict `ficha` que se incluye en el reporte debe poner `detectado=true` solo si hay valor no vacío; en caso contrario `detectado=false`, `valor=None`, `pagina=None`.

### F-5: Tests
- `tests/_caratula_real.py`: fixture con estructura real (dos autores, etiqueta `ASESORA:` en párrafo aparte, año 2026, `RESUMEN` como Título1 con abstract y palabras clave).
- `tests/test_captura_ficha.py`: expectativas — título sin prefijo, dos autores, asesora, año 2026, abstract, palabras clave limpias y `detectado=false` para valores inservibles.
- `tests/test_constancia.py`: `xfail(strict=True)` eliminado; una constancia por autor real.
- Regresión explícita: el año 2024 del título no gana sobre 2026 de la portada.

### F-6: `scripts/eval_contra_plantillas.py`
- Antes usaba `rules_data["rules"]`; el DSL usa la clave `reglas`. Ahora `_reglas_de` acepta ambos formatos y `_total_mecanizadas` cuenta según corresponda. Tests en `tests/test_eval_contra_plantillas.py` (helpers y `main()` con ambos formatos).

### F-7: Decisión `palabras_clave_minimo`
- **Decidido el 2026-11-08**: se mantiene en `error`.
- Las 5 plantillas oficiales siguen en rojo a propósito (son plantillas, no tesis).
- No requiere cambio de código ni de reglas.

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

## Decisiones del equipo (resueltas)

1. `palabras_clave_minimo`: se mantiene en `error` (decisión 2026-11-08).
2. Sufijo del título (decisión 5.2): se conserva `, Trujillo 2024` (el handover §3.2 lo fija como valor esperado).

---

*Fin del plan. Se actualiza conforme avance la semana.*