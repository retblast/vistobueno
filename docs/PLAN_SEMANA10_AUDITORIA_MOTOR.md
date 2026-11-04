# Plan Semana 10 — Auditoría  (Motor/Reglas)

**Fecha:** 2026-10-27  
**Responsable:** IvanSanchezSil ()  
**Base:** `origin/semana8-deposito-ficha`  
**Rama:** `semana10-auditoria-motor`  
**Fuente:** `AUDIT_COMPORTAMIENTO_VISTOBUENO_2026-10-26.md`

## Principio
Documentar y planificar primero. Sin tocar código hasta tener claro el enfoque. Commits atómicos por hallazgo, sin `Co-Authored-By`.

## Alcance

| ID | Sev | Archivos | Acción |
|----|-----|----------|--------|
| AUD-01 | Alta | `validator/analizadores.py` (`_norm_indice`) | Separar normalización: títulos del cuerpo sin borrar último carácter por falso número romano. |
| AUD-02 | Alta | `validator/tokenizer.py`, `validator/analizadores.py`, `reglas_unt.yaml`, `tests/_mutations.py` | `seccion(inicio=anexo)` hasta final; incluir `TITULO` en `_texto()` de lista_obligatoria para anexos; mostrar todos los faltantes (quitar `[:8]`). |
| AUD-03 | Media | `validator/analizadores.py`, `validator/compilador.py`, `tests/test_paridad_formatos.py` | `encontrado` legible: culpables primero, página del nodo infractor. Revisar paridad. |
| AUD-04 | Media | `reglas_unt.yaml` | Notas `EVALUADO:` en tamaños de carátula. |
| AUD-05 | Media | decisión | Endurecer selectores frágiles o documentar. |
| AUD-06 | Baja | decisión | Revisar `_sigpalabra` >= 4. |
| AUD-07 | Baja | decisión | Alcance `caratula_optar_grado_tamano`. |
| AUD-20 | Media | `tests/_docx_builder.py`, `tests/_mutations.py` | Fixtures estructura real. |
| AUD-15 | Media | `validator/exportador.py` | Escape HTML en `message`/`found`/`expected`/`prompt` al inyectarlos en Markdown/PDF. |

## Diagnóstico

### AUD-01
`_norm_indice` borra `[ivxlc]{1,5}` del final. Títulos del cuerpo sin página pierden su última letra. Hay que diferenciar normalización por origen (cuerpo vs índice).

### AUD-02
Tres causas: (1) `seccion()` corta en primer título siguiente sin `fin`/`hasta_final`; (2) `_texto()` solo `PARRAFO`; (3) truncado `[:8]`. Solución acotada al caso de anexos para minimizar riesgo.

### AUD-03
Muestra valores conformes primero, página del primer nodo, formato crudo. Cambiar a culpables primero + página del nodo infractor. Coordinar con paridad.

### AUD-15
El exportador `validator/exportador.py` interpolaba `message/found/expected` en Markdown y PDF sin escapar HTML. Esto podía romper la sintaxis de tablado o generar marcado no válido. Se soluciona escapando con `html.escape()` antes de inyectar.

## Orden de ejecución
1. AUD-01 + test
2. AUD-02 + fixture + mutations
3. AUD-20 completar
4. AUD-03 + revisión paridad
5. AUD-04
6. Decisiones AUD-05/06/07 si procede
7. AUD-15: Escape HTML en `validator/exportador.py` (hecho en semana 10).

## Verificación
- `nix develop -c pytest tests/ -v`
- `nix flake check`
- `nix develop -c bash -c "ruff check validator/ scripts/ tests/ && ruff format --check validator/ scripts/ tests/ && mypy validator/ scripts/"`
- Si hay copia: `python -m validator.cli /tmp/opencode/tesis_linares.docx reglas_unt.yaml --json`

## Notas
Sin `Co-Authored-By`. Commits atómicos. Base `semana8-deposito-ficha`. No tocar archivos fuera de mi alcance sin coordinación.