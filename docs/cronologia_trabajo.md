# Cronología real del trabajo — IvanSanchezSil

> Documento: `docs/cronologia_trabajo.md`
> Fuente de verdad de la asignación de trabajo por semana del plan y su
> reflejo en los Pull Requests del repositorio retblast/vistobueno.

## Convención del plan

El plan del equipo numeró las semanas del proyecto (Semana 1, 2, 3, 4…).
Este integrante **no tuvo aportes en la Semana 1** del plan; su trabajo
comienza en la **Semana 2**.

## Cronología

| Semana del plan | Contenido real | PR (repo retblast/vistobueno) | Rama (fork) | Estado |
|---|---|---|---|---|
| **Semana 2** | Reglas de formato en YAML legacy (`unt_format_rules_schema.yaml`, 32 mecanizadas/44 totales) + flujo de OCR (PyMuPDF + Tesseract spa+eng) | PR [#3](https://github.com/retblast/vistobueno/pull/3) `feat(reglas): formato legacy UNT en YAML + flujo OCR` | `semana2-Reglas,-OCR` | Fusionado |
| **Semana 3 — 1ª parte** | Motor DSL completo: DFA, analizadores, compilador, F1 migración legacy→DSL, F2 tokenizer/PDA, paridad exacta | PR [#6](https://github.com/retblast/vistobueno/pull/6) `feat(motor): motor de validación DSL — DFA, analizadores y compilador` | `semana3-DSL` | Fusionado |
| **Semana 3 — 2ª parte** | F3 mecanización manual (+9 reglas, 32→41), F4 linter/cache XPath/traza, F6 tests de propiedad con factory | PR [#11](https://github.com/retblast/vistobueno/pull/11) `feat(DSL): consolidación final F1–F4 + F6, paridad OK` | `semana4-f4` | Fusionado |
| **Semana 4** | Documentación de diseño a posteriori (10 docs, 38 diagramas Mermaid) + F5: API conectada al DSL + traza de autómatas | PR [#22](https://github.com/retblast/vistobueno/pull/22) `feat(F5): API conectada al DSL + traza de autómatas · docs de diseño` | `semana4` | Abierto |

### PRs cerrados (no fusionados, ramas suprimidas)

| PR | Motivo de cierre |
|----|-----------------|
| [#2](https://github.com/retblast/vistobueno/pull/2) `feat: integración motor de validación y OCR` | Intento inicial de Semana 2; fue reemplazado por #3 (se dividió el trabajo) |
| [#7](https://github.com/retblast/vistobueno/pull/7) `feat(DSL): F3 — mecanización de 9 reglas` | Trabajo parcial; fue consolidado dentro de #11 |
| [#9](https://github.com/retblast/vistobueno/pull/9) `F6: tests de propiedad` | Trabajo parcial; fue consolidado dentro de #11 |

## Bitácoras del integrante (reclasificadas por cronología real)

| Bitácora | Contenido | Semana real |
|---|---|---|
| `docs/semana3_trabajo_ivanSanchezSil.md` | F1 (migración al DSL) | **3** (07/09) |
| `docs/semana3_1_trabajo_ivanSanchezSil.md` | F2 + F3 (tokenizer/PDA, mecanización 32→41) | **3** (09/09) |
| `docs/semana3_2_trabajo_ivanSanchezSil.md` | F6 (tests de propiedad, factory) | **3** (09/09) |
| `docs/semana3_3_trabajo_ivanSanchezSil.md` | F4 (linter, cache XPath, traza) — **renombrada desde `semana4_trabajo_ivanSanchezSil.md`** | **3** (09/09) |
| (semana 4, en curso) | Documentación de diseño + F5 | **4** (14–18/09) |

> El trabajo de las fases F1–F4 y F6 se realizó íntegramente en la **Semana 3**;
> se reclasificó `docs/semana4_trabajo_ivanSanchezSil.md` → `docs/semana3_3_…md`
> porque su contenido (F4) pertenece a la Semana 3. La bitácora de la Semana 4
> real (docs de diseño + F5) no existe como `semana4_…` aún; está en este PR #22.

## Nota sobre los merge commits de master

Los títulos de los commits de merge en `master` ("Merge pull request #N
from …") conservan el título con el que se fusionaron originalmente (p. ej.
"Semana2 reglas, ocr" en PR #3). Esto es estándar de GitHub: renombrar el
título del PR **no** reescribe los merge commits ya fusionados. La fuente
de verdad de la cronología es este documento y los títulos actuales de los
PRs en la pestaña "Pull requests" de GitHub.
