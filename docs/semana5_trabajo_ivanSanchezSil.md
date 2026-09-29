# Bitácora Semana 5 — ivanSanchezSil

- **Integrante**: Iván Sánchez Silva (Integrante 3 — Motor de reglas)
- **Semana**: 5
- **Fechas**: 2026-09-15 → 2026-09-22
- **Rol**: Motor de reglas / Procesamiento (DSL, extractor, checks)

---

## Objetivos de la semana

1. Cerrar la fase **F2 (mecanización del territorio no validado)** del motor DSL:
   - Ítem 1: ubicación por página física (`location` enriquecido).
   - Ítem 2: encabezados y pies de página.
   - Ítem 3: notas al pie.
2. Mantener los invariantes de calidad (property tests, sincronización factory↔YAML).
3. Evaluar los ítems 11 y 12 (TOC y numeración jerárquica) contra la realidad de las plantillas antes de mecanizar.

## Actividades realizadas

### 2026-09-21 (planificación)

- Reunión de planificación de la F2; plan consolidado presentado y aprobado ("arranca").

### 2026-09-22 (implementación)

- **Ítem 1 — paginación + `location`** (commit `28b2c57`):
  - `Analizador.ultimo_nodo` setea el nodo objetivo en `_nodos()` y en `AnalizadorPaginacion`.
  - `ReglaCompilada.ejecutar()` anexa `"; página N"` a `ubicacion` cuando la regla FALLA y el nodo tiene página en el mapa.
  - Cita manual: párr. 139 "…la carátula no se enumera, pero se cuenta…" y párr. 184.
  - Verificado que `caratula_no_se_enumera` ya estaba mecanizada en el YAML (no se duplicó).
- **Ítem 2 — encabezados y pies** (commit `1cacd14`):
  - `ExtractedDocx` lee **todas** las partes `header*.xml`/`footer*.xml`; `xpath()` combinado con caché por (parte, contexto, xpath).
  - Reglas `encabezado_membrete` (logo/`w:drawing`) y `encabezado_formato` (Times New Roman), ambas `warning`, con nota `EVALUADO:` (el manual no las define; es estándar institucional UNT).
  - Factory: `header1.xml` con membrete, mutaciones `header_logo=False` y `header_fuente="Arial"`.
  - Evidencia LFA: defecto de la **automatización**
- **Ítem 3 — notas al pie** (commit `e38969a`):
  - Sección DSL `nota_pie` + `AnalizadorNotaPie` (numeración `1..N` consecutiva, sin duplicados, existencias en `footnotes.xml`; sin notas → n/a).
  - `ExtractedDocx.footnotes` (parte opcional `word/footnotes.xml`).
  - Factory: `notas_pie_ids` y mutación `[1,2,4]` (salto).
  - Evidencia LFA: diagramas de estados/transiciones del contador.
- Conteos sincronizados: **45 reglas**, doc bueno **43/45**, 45 mutaciones, suite **187 tests**.
- **Ítems 11-12 (TOC/numeración jerárquica)**: revisados a fondo → **diferidos**. La plantilla oficial usa "1.3. EL PROBLEMA" → "1.5 VARIABLE(S)…" (saltos) e índices con puntillado y números de página; las reglas aprobadas generarían falsos positivos contra la plantilla. Se documentó en `docs/PLAN_BACKLOG_FUTURO.md` con el criterio a definir.

### 2026-09-22 (TOC — cierre del diferido, commits `(Bloque D)`)

- **Ítem 11 — `indice_apunta_secciones`** (warning, `toc_apunta`):
  - `AnalizadorTocApunta` + helpers (`_entradas_indice`, `_norm_indice`,
    `_sigpalabra`, `_sin_acentos`, `_parse_numero_indice`). Cada entrada del
    índice se normaliza y su token significativo debe ser subcadena de un
    título real del cuerpo; "Anexo N" → "ANEXOS"; sin región → n/a.
  - **Corrección clave**: `re` no iguala "Í" con "I" → la regex de la región
    es ASCII (`^indice(\s+de\s+contenidos)?$`) y se normalizan acentos.
  - **Corrección de diseño**: el manual NO prohíbe números de página en el
    índice (el de TABLAS los exige, párr. 195). El criterio es de estructura,
    no de falta de páginas → el diferido se basaba en un malentendido.
- **Ítem 12 — `indice_numeracion_jerarquica`** (warning, `toc_numeracion`):
  - `AnalizadorTocNumeracion`: capítulos romanos I..VI consecutivos; primera
    subsección de cada capítulo `K.1`; preorder estricto por tuplas; **sin**
    exigir contigüidad de hermanos (variante débil, nota `EVALUADO:`).
  - Los saltos "1.3→1.5" que motivaron el diferido eran del factory de tests,
    no de las plantillas; la regla débil los acepta.
- Factory: `TDC_ENTRADAS_BASE` (índice válido de 20 entradas), helper
  `_tdc_para`; mutaciones `_insertar_tdc` (11) y `_renumerar_tdc` (12).
- `REGLAS_ACOPLADAS`: se verificó que renombrar "SITUACIÓN PROBLEMÁTICA"
  (mutación `estructura_tinv_cuantitativo`) rompe `indice_apunta_secciones`;
  el acople de `indice_subdivisiones` **no** se tocó porque en éxito el motor
  reporta `found="cumple"` (el paso a n/a no es observable).
- Conteos sincronizados: **47 reglas**, doc bueno **45/47**, 47 mutaciones,
  suite **206 tests**.

### 2026-09-23 (cierre de la revisión técnica del PR #28)

- **Bloqueante 1 — NS["r"] corrupto** (`validator/extractor.py:20`): la URI de
  relaciones venía rota; corregida a `officeDocument/2006/relationships`
  (commit `6e0775f`).
- **Bloqueante 2 — `ruff format`**: formateado todo el árbol (38-39 archivos);
  gate `ruff format --check` verde.
- **Bloqueante 3 — falsos positivos de las categorías F2 contra `recursos/`**
  (commit `ba4f560`):
  - `AnalizadorXML` soporta `n_a_si_ausente` → `encabezado_membrete` y
    `encabezado_formato` pasan **n/a** cuando la tesis no trae `header*.xml`
    (antes: `ValueError: parte 'header' no disponible` expuesto al usuario).
  - `AnalizadorPaginacion`: si alguna sección objetivo no es identificable
    pasa como n/a — la regla **solo juzga paginación, no presencia de
    secciones**. `indice_paginas_separadas` ya no da `no_encontrado`/`paginas_repetidas`
    en las plantillas (su "Índice" vive dentro de `sdtContent` y el xpath no
    lo localiza).
  - Verificado: los **6 documentos de `recursos/`** pasan las 4 categorías
    (`indice_paginas_separadas`, `encabezado_membrete`, `encabezado_formato`,
    `notas_al_pie_consistencia`).
  - `EXCLUIDAS_BASE` vuelve a 2 reglas (el doc base **sí** cumple
    `indice_paginas_separadas`); el "doc bueno 45/47" se mantiene.
- **Avísos** (commit `df7a832`): import lazzy de `weasyprint` dentro de
  `reporte_a_pdf` (los flujos json/markdown ya no arrastran la dependencia) y
  `tests/test_cli_integracion.py` que cubre `--formato json/markdown/pdf`,
  `--salida`, el atajo `--json` y el filtro `--severity`.
- `docs/CONTRATO_API.md` actualizado: "41 reglas" → "47 reglas" (la entrada
  quedó etiquetada v1.1.0; falta reetiquetarla como v1.2.0 — ver backlog).
- Conteos sincronizados: **47 reglas**, doc bueno **45/47**, suite **206 tests**.

### 2026-09-23 (Semana 5.2 — sincronización de docs post-merge, rama `semana52-docs-sync`)

- El PR #28 quedó **mergeado por retblast** (`9ac1cdf`, 2026-09-23): la rama
  `semana5-motor-calidad-paginacion` cerró su ciclo y **no se borra**; el
  trabajo de este bloque va en rama aparte.
- **Regenerado `docs/ejemplo_respuesta_motor.json`** (CLI `--json` contra el
  MANUAL): `encabezado_membrete`, `encabezado_formato` e
  `indice_paginas_separadas` ahora pasan (`found: "cumple"`) — desaparece el
  `ValueError: parte 'header'...` que citó la revisión y sus prompts en
  `como_preguntar_a_una_ia`. `resultados` 45→47 (faltaban las de la F2) y
  `resumen` ahora refleja las 47 reglas del DSL sobre el MANUAL
  (27 error + 10 warning).
- Conteos sincronizados: **47 reglas**, doc bueno **45/47**, suite **206 tests**
  (el nit `d75c535` sumó 2 tests de paginación).
- **Pendiente intencional (decisión de alcance)**: el CI de master quedó en
  rojo por el paso `cachix-action` (caché `vistobueno` sin token). Se dejó SIN
  tocar el `.github/workflows/ci.yml`; coordinar con retblast (crear caché
  pública `vistobueno` + secreto `CACHIX_AUTH_TOKEN`, o quitar el paso).
- **Nit del review (`d75c535`)**: `_paginacion_para()` ahora también avanza el
  mapa con `w:pPr/w:pageBreakBefore` (además de `lastRenderedPageBreak` y
  `w:br w:type="page"`); tests `test_mapa_de_salto_con_page_break_before` y
  `test_paginas_distintas_solo_con_page_break_before`. Es lo que deja la suite
  en 206 tests.

## Evidencias producidas

| Tipo | Archivo / referencia |
|------|----------------------|
| Diseño | `docs/diseno/11_ubicacion_pagina.md`, `12_encabezados_pies.md`, `13_notas_al_pie.md`, `14_indice_toc.md` |
| Reglas | `reglas_unt.yaml` (44→47; encabezado_membrete, encabezado_formato, notas_al_pie_consistencia, indice_apunta_secciones, indice_numeracion_jerarquica) |
| Motor | `validator/analizadores.py` (ultimo_nodo, AnalizadorNotaPie, AnalizadorTocApunta, AnalizadorTocNumeracion), `compilador.py`, `dsl_check.py`, `extractor.py` |
| Tests | `tests/test_f2_paginacion.py`, `tests/test_f2_encabezados.py`, `tests/test_f2_notaspie.py`, `tests/test_toc_indice.py` |
| Factory | `tests/_docx_builder.py`, `tests/_xml_constants.py`, `tests/_mutations.py`, `tests/docx_factory.py` |
| Backlog | `docs/PLAN_BACKLOG_FUTURO.md` (ítems 1-3 y 11-12 ✅) |
| Commits | `28b2c57`, `1cacd14`, `e38969a`, `(Bloque D)`, `6e0775f` (NS URI), `ba4f560` (n/a F2), `df7a832` (CLI + weasyprint lazy), `7ea6998` (conteos 204), `d75c535` (pageBreakBefore) · Semana 5.2: `semana52-docs-sync` (docs, este commit) |
| Gates | `pytest` 206 passed; `ruff` y `mypy` limpios |

## Relación con competencias curriculares

- **Estructura de Datos**: mapa párrafo→página, estructura de árboles XML multiparte, contador de notas.
- **Ingeniería de Software II**: property tests (invariante: toda regla con mutación), factory determinista, documentación de decisiones.
- **Redes de Computadoras I**: sin cambios de contrato HTTP; la API consume las 47 reglas (verificación con la suite de contrato del backend).

## Dificultades y aprendizajes

- El rango del manual es **manual normativo**, no descriptivo de Word: encabezados y notas no están regulados → reglas como `warning` con nota `EVALUADO:` y pase n/a cuando no aplican.
- **Lección clave**: validar las reglas propuestas contra las plantillas OFICIALES ANTES de mecanizar. El diferido de los ítems 11-12 se cerró al revisar con evidencia: los saltos "1.3/1.5" eran del factory de tests (no de las plantillas) y el puntillado con páginas del índice está permitido (de hecho el de TABLAS lo exige) — el diseño malinterpretó ambos.
- **Diseño conociendo el compilador**: en éxito el motor reporta `found="cumple"` (descartando el detalle del analizador). Un cambio que solo altera el detalle en éxito o pasa a n/a NO es observable por los property tests → no debe acoplarse en `REGLAS_ACOPLADAS`.
- Los cambios en la parte `footnotes.xml` deben manipularse con namespace (`{WNS}id`), no con prefijo "w:id".

## Plan de la semana siguiente

1. Coordinar el **CI de master** (rojo por `cachix-action` sin `CACHIX_AUTH_TOKEN`)
   con retblast: crear caché pública `vistobueno` + secreto, o quitar el paso
   `cachix` del workflow para dejarlo verde.
2. Contar con el Backend para el ítem 16 (`formato` en `POST /validar`) y para
   reetiquetar el changelog de `docs/CONTRATO_API.md` (v1.1.0 → v1.2.0 con las 47
   reglas; quedó anotado en `docs/PLAN_BACKLOG_FUTURO.md`).
3. Evaluar las dos reglas de TOC con `scripts/eval_contra_plantillas.py`
   (ítem 13 del backlog) contra las plantillas oficiales; ajustar la variante
   débil si alguna plantilla las hace fallar.