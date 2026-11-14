# Bitácora Semana 12 — ivanSanchezSil

- **Integrante**: ivanSanchezSil (Integrante 3 — Motor de reglas / Procesamiento)
- **Semana**: 12
- **Fechas**: 2026-11-12 → 2026-11-18 (semana en curso)
- **Rol**: extractor, motor, analizadores, reglas YAML, exportador/CLI y
  pruebas/factory del motor
- **Rama de trabajo**: `semana12-m11-factory-opc`
- **Base**: `upstream/master` `bf6be5e` (PR #94)
- **Plan**: [`PLAN_SEMANA12_MOTOR_CORRECTITUD.md`](PLAN_SEMANA12_MOTOR_CORRECTITUD.md)

---

## Objetivos de la semana

1. Ejecutar las tareas de correctitud del motor (`M1a`, `M1`–`M12`) en PRs
   pequeños, con regresión previa al arreglo.
2. Empezar por `M11` (paquete OPC del factory) y `M1a` (validación del
   extractor) porque desbloquean B6 y B5 de Int1.
3. Mantener intactos la API, la SPA, el userscript y `AGENTS.md`.

---

## Actividades realizadas

### 2026-11-12 — Plan de la Semana 12 (PR #97)

Se documentó el desglose de hallazgos `VA`/`NM` en tareas y PRs, con orden,
dependencias, criterios de aceptación, decisiones pendientes del encargado y
calendario de las semanas 12 y 13. El plan no declara corregido ningún
hallazgo.

### 2026-11-12 — M11 / VA-17: paquete OPC del factory (PR 12.1)

**Reproducción previa al arreglo**

```bash
PYTHONPATH=/home/ivan/pylibs:.:tests python3 - <<'PY'
import docx
from _docx_builder import compilar_docx, configuracion_base
docx.Document(compilar_docx(configuracion_base()))
PY
```

Resultado: `KeyError: "There is no item named 'media/logo.png' in the archive"`.
El ZIP solo tenía `[Content_Types].xml`, `_rels/.rels`, `word/document.xml`,
`word/header1.xml` y `word/footer1.xml`. Las relaciones de cabecera, pie,
imagen e hipervínculo estaban en `_rels/.rels` (raíz), no existía
`word/_rels/document.xml.rels` ni `word/_rels/header1.xml.rels`, y el PNG
nunca se escribía.

**Arreglo**

- `_rels/.rels` declara solo el documento principal.
- `word/_rels/document.xml.rels` declara cabecera, pie, imagen de portada e
  hipervínculo ORCID.
- `word/_rels/header1.xml.rels` declara el logo del membrete.
- Se escribe un PNG válido de 1×1 en `word/media/logo.png`.
- Si hay notas al pie, se agregan su relación y su `Override` en
  `[Content_Types].xml`; si no hay, no se declaran partes inexistentes.
- Regresión nueva en `tests/test_docx_factory_opc.py`: abre con
  `python-docx`, resuelve todos los destinos internos, comprueba que cada
  `r:id`/`r:embed` esté declarado en su parte, valida el PNG y exige tipo de
  contenido para cada parte.

**Verificación**

```bash
PYTHONPATH=/home/ivan/pylibs:.:tests python3 -m pytest tests/ -q
# 836 passed, 4 skipped, 6 xfailed

~/.local/bin/ruff check validator/ scripts/ tests/
~/.local/bin/ruff format --check validator/ scripts/ tests/
PYTHONPATH=/home/ivan/pylibs python3 -m mypy validator/ scripts/
# All checks passed / 81 files already formatted / Success
```

**Límites**

- No se regeneraron `docs/ejemplos/doc_bueno.docx` ni `doc_malo.docx`: B6 de
  Int1 es quien los regenera y refuerza la guardia. El comando es
  `python scripts/ejemplo_bueno_malo.py`.
- El PNG es un marcador de 1×1: las reglas solo cuentan nodos `a:blip`, no
  inspeccionan dimensiones ni píxeles.
- La medición real del logo sigue siendo M7 (VA-15), pendiente de decisión.

**Entrega a Int1**

- Commit `85690c5` (rama `semana12-m11-factory-opc`, PR 12.1).
- Comando de regeneración: `python scripts/ejemplo_bueno_malo.py`.

---

## Evidencias

| Evidencia | Archivo / comando |
|---|---|
| Plan de la semana | `docs/PLAN_SEMANA12_MOTOR_CORRECTITUD.md` (PR #97) |
| Reproducción de M11 | `KeyError: media/logo.png` con `python-docx` |
| Regresión | `tests/test_docx_factory_opc.py` (12 casos) |
| Arreglo | `tests/_xml_constants.py`, `tests/_docx_builder.py` |
| Suite | 836 passed, 4 skipped, 6 xfailed |
| Estado del hallazgo | §2 de `HANDOVER_CORRECTITUD_2026-11-12.md` |

---

## Dificultades y aprendizajes

- El extractor propio toleraba el paquete roto, así que la suite no lo
  detectaba; hizo falta abrir el DOCX con `python-docx` para reproducir el
  fallo que ve Int1.
- OPC exige que cada parte declare sus propias relaciones: un `Id` de
  `document.xml` no es visible desde `header1.xml`, aunque el nombre coincida.
- Declarar relaciones o tipos de contenido de partes ausentes también rompe
  el paquete; por eso las notas al pie se agregan solo cuando existen.

---

## Plan de la semana siguiente

1. Abrir y revisar el PR 12.1 (M11).
2. Implementar M1a: validar la entrada del extractor y documentar las partes
   OPC mínimas admitidas (desbloquea B5 de Int1).
3. Continuar con M1 (formato efectivo y revisión de todo el texto).
