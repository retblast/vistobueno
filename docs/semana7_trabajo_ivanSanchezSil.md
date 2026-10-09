# Bitácora Semana 7 — ivanSanchezSil

- **Integrante**: Iván Sánchez Silva (Integrante 3 — Motor de reglas)
- **Semana**: 7
- **Fechas**: 2026-10-01 → 2026-10-09
- **Rol**: Motor de reglas / Procesamiento (DSL, extractor, checks)

---

## Objetivos de la semana

1. **Resolver la revisión del PR #45** ("fix(reglas): correcciones de revisión
   en las tres reglas de estructura") sobre la inferencia de tipo documental:
   las firmas se comparaban sobre toda la prosa, no solo sobre títulos, con
   dos salidas peligrosas (falso rojo por prosa inocente, o verde sin
   validación estructural).
2. **Preparar la medición** que pedía el revisor contra documentos reales, no
   solo contra plantillas.
3. **Documentar** la resolución (DSL, diseño, README, conteos, bitácora).
4. **Issue #1 del handover**: corregir `_cuerpo_paras()` (el "cuerpo" del DOCX
   se definía por la última sección, no por la estructura real, generando
   falsos positivos de interlineado/alineación en tesis reales).

---

## Actividades realizadas

### 2026-10-01 → 2026-10-08 — Lectura y verificación de los insumos

- Leídos y contrastados contra el código los dos documentos de transferencia
  (`INFORME_diagnostico_conversion_pdf.md` y `HANDOVER_MOTOR_TODOS_LOS_ISSUES.md`).
- Verificado que el PR #36 (aplicabilidad por `aplicar_si`) ya estaba
  mergeado y resuelve el "semáforo jamás verde" del informe PDF.
- Verificada la línea base en una plantilla oficial: 3 errores / 10 warnings,
  `reglas_no_aplicables=2`.

### 2026-10-09 — Resolución de la revisión del PR #45

- **Q1 (firmas solo sobre títulos)**: `DeteccionTipo._tipo_inferido` ahora
  recibe los textos de los párrafos con estilo de título (tokenizer), no toda
  la prosa. Medido en la tesis real de Linares: el "1/2" de
  `proyecto_cuantitativo` que la carátula regalaba por prosa desaparece y la
  TINV se sigue detectando (`inferido=tinv_cuantitativo`).
- **Q2 (Anexo 10 en tabla / content-control)**: la declaración ahora recorre
  todos los párrafos del cuerpo (incluye `w:tbl` y `w:sdt`), lee el estado de
  una casilla `w14:checkbox` y, si el Anexo 10 es una tabla, busca la etiqueta
  en la misma fila que la casilla.
- **Salida B (tipo sin estructura cargada)**: se generalizó el mecanismo de
  centinelas del compilador para emitir un **warning** `tipo_documento_sin_estructura`
  cuando el tipo detectado es proyecto/informe/TSP (sus estructuras siguen en
  `reglas_unt_pendientes.yaml`, fuera de producción). Así el semáforo no vende
  un verde que no validó el capítulo de metodología.
- **Solape retirado**: `OPERACIONALIZACIÓN DE LAS VARIABLES` en la firma de
  `informe_cuantitativo` sí aparece como título real en una TINV, pero solo
  aporta 1/2 (el umbral es 2), así que no vira la clasificación. Se documentó
  y no se modificó.

### 2026-10-09 — Evidence y tests

- Medición sobre la tesis real (Linares, DOCX): tabla de puntaje por tipo en
  prosa vs títulos (proyecto 1/2 → 0/2; TINV se mantiene 2/2).
- 13 tests nuevos:
  - `TestInferenciaSoloTitulos` (prosa no cuenta; tesis TINV que menciona
    proyecto en prosa no vira; un proyecto real sí se detecta).
  - `TestDeclaracionEnTablaYSdt` (declaración en tabla con etiqueta en otra
    celda, casilla vacía, content-control `w14` marcado y desmarcado).
  - `TestAvisoSinEstructura` (los 5 tipos sin estructura emiten warning; una
    TINV no lo emite).
- Suite completa: **381 tests pasan** (+13).

### 2026-10-09 — Issue #1 del handover: `_cuerpo_paras` semántico

- **Diagnóstico**: `_cuerpo_paras()` tomaba todos los párrafos desde la última
  sección (`sectPr`), lo que en tesis reales (Linares) incluía títulos de
  capítulo centrados, párrafos vacíos con `line=278` (artefactos de Word) y
  notas APA de tabla ("Nota."). Por eso `interlineado` y `alineacion_cuerpo`
  daban falsos rojos.
- **Decisión (en conjunto con el equipo)**: el cuerpo se define por el **rango
  semántico** entre el primer heading "Introducción" y el primer heading
  "Referencias"/"Bibliografía"/"Anexos"; se excluyen headings, párrafos vacíos
  y captions `Nota.`/`Fuente.`; fallback a todo el documento si no hay
  "Introducción"; solo `w:body/w:p` de nivel superior (los párrafos de tabla
  quedan fuera por construcción).
- **Implementación**: reescrito `_cuerpo_paras()` en `validator/extractor.py`
  (regex `HEADING_RE` para estilos `Heading*`/`Título*`/`Ttulo*` y
  `_texto_normalizado`); docstring del módulo y de `xpath()` actualizados.
- **Ajuste de fixtures**: tanto `tests/_docx_builder.py` (factory) como
  `tests/test_paridad_formatos.py` construían la prosa del cuerpo DESPUÉS del
  marcador de sección / de ANEXOS; se movió a justo después del heading
  "INTRODUCCIÓN" para que coincidan con un cuerpo real.
- **Verificación**: suite completa **381 tests pasan**; plantillas oficiales
  sin regresión (3 errores / 10 warnings, como está documentado); en la tesis
  real de Linares `interlineado` y `alineacion_cuerpo` pasan (8 → 6 errores;
  quedan márgenes landscape, XPaths de carátula y `sangria_parrafo`, issues
  #2/#4/#7 del handover).

### 2026-10-09 — Issue #2 del handover: márgenes en secciones landscape

- **Diagnóstico**: las reglas `margen_*` validaban `all_eq` sobre **todas** las
  secciones del documento. La tesis de Linares tiene una sección **landscape
  DENTRO del cuerpo** (una tabla de OPERACIONALIZACIÓN de 3 párrafos), y Word
  rota los márgenes en landscape (bottom<->left, top<->right) para que el
  empaste siga en el mismo borde físico. Por eso `margen_inferior` (1701 vs
  1418) y `margen_izquierdo` (1418 vs 1701) daban falsos rojos.
- **Decisión (en conjunto con el equipo)**: validar SOLO las secciones que
  rigen el cuerpo real (`contexto: seccion_cuerpo`) **y normalizar la
  rotación** que Word aplica en landscape. Se acepta la rotación estándar; no
  se exige uniformidad fuera del cuerpo.
- **Implementación**:
  - `validator/extractor.py`: `_rango_cuerpo()` (helper del rango semántico),
    `_secciones_cuerpo()` (sectPr que gobiernan el cuerpo, con orden por rango
    de documento y fallback a todos si vacío), campo `_secciones_cuerpo` en
    `ExtractedDocx`, métodos `_nodo_seccion()` / `es_seccion_cuerpo()` /
    `es_seccion_landscape()`, y rama `contexto == "seccion_cuerpo"` en `xpath()`.
  - `validator/analizadores.py`: en `AnalizadorXML`, `_valor_margen()` devuelve
    el atributo rotado (top<->right, bottom<->left) cuando el `w:pgMar` está en
    una sección landscape (`_ROTACION_MARGEN`).
  - `reglas_unt.yaml`: las 4 reglas `margen_*` pasan a `contexto: seccion_cuerpo`
    con comentario de la política.
- **Tests**: `tests/test_margenes_landscape.py` (3 tests) — una sección
  landscape legítima dentro del cuerpo no falla; una sección del cuerpo con
  margen mal sigue fallando; evidencia de la rotación (bottom=1701/left=1418)
  y de que el contexto incluye la landscape. Los 4 ids de márgenes entran a
  `solo_passed` en `tests/test_paridad_formatos.py` (el `found` del DSL, que
  cuenta menos nodos, difiere del legacy, que valida todos).
- **Verificación**: suite completa **384 tests pasan** (+3); `ruff` + `mypy`
  limpios; `nix flake check` verde; plantillas oficiales sin regresión
  (3 errores / 10 warnings); en Linares los 4 márgenes ya pasan (6 → 4
  errores; quedan solo los issues de carátula #3/#4/#7).

### 2026-10-09 — Issues #3/#4 del handover: XPaths de carátula

- **Diagnóstico**: las reglas de la carátula se evaluaban sobre **todo** el
  documento. El título se localizaba por el **placeholder** del manual
  (`contains 'título del trabajo'`), lo que daba falsos rojos en documentos
  reales (el título de Linares es "Taller de dramatización…", sin esa frase) y
  en las plantillas oficiales. Además `alineacion_caratula_todos_elementos`
  marcaba roja una tesis correcta por párrafos del cuerpo.
- **Decisión (en conjunto con el equipo)**: introducir `contexto: caratula`
  (párrafos top-level anteriores al primer `w:pPr/w:sectPr` del cuerpo) y
  localizar el título **posicionalmente**, no por texto. Como el título no es
  el mismo en todos los formatos, se ancla en la línea "para optar" y se toma
  el párrafo no vacío inmediatamente anterior (saltando etiquetas cortas como
  "TESIS"/"PROYECTO", sin descartar títulos largos que contengan esas palabras).
- **Implementación**:
  - `validator/extractor.py`: `_caratula_paras()` (párrafos top-level antes del
    primer `w:pPr/w:sectPr`, fallback a todo el cuerpo), campo `_caratula`,
    método `is_caratula()` y rama `contexto == "caratula"` en `xpath()`.
  - `reglas_unt.yaml`: `contexto: caratula` en las reglas de párrafos de
    carátula; nuevo XPath posicional del título (anclado en "para optar") en
    `caratula_titulo_trabajo_tamano` y `caratula_titulo_negrita_mixta`; la
    comprobación de "mayúsculas y minúsculas" pasa a `coincidencia: alguno`
    (el título se parte en runs y algunos son solo espacios).
  - `caratula_no_se_enumera`, `caratula_logotipo_tamano`,
    `caratula_linea_investigacion`, `caratula_orcid` y `proyecto_caratula_texto`
    se mantienen en `contexto: todos` (no son párrafos de carátula o dependen
    de otros issues).
- **Tests**: `tests/test_caratula.py` (4 tests) — un párrafo del cuerpo que
  contiene una palabra clave de la carátula no rompe la localización del
  título; una carátula desalineada sigue fallando; el título real de Linares
  (sin placeholder) se detecta; la negrita-mixta pasa con runs de espacios.
- **Verificación**: suite completa **388 tests pasan** (+4); plantillas
  oficiales sin regresión (3 errores / 10 warnings); en Linares caen
  `alineacion_caratula_todos_elementos` y `caratula_titulo_negrita_mixta`
  (**6 → 2 errores**; quedan `caratula_autores_mayusculas_sin_negrita`, un
  hallazgo real del estudiante, y `proyecto_caratula_texto`, issue #5).
  `ruff` + `mypy` limpios; `nix flake check` verde.

### 2026-10-09 — Issue #5 del handover: `aplicar_si` en reglas tipo-específicas

- **Diagnóstico**: 6 reglas solo tienen sentido en un tipo de documento, pero
  se evaluaban SIEMPRE: los mínimos de referencias/anexos de cualitativo y
  revisión fallaban en tesis cuantitativas (8/8 anexos faltantes,
  `nodos=0 minimo=30`), y `proyecto_caratula_texto` buscaba "Proyecto de
  Investigación" en tesis TINV. Falsos positivos imposibles de corregir.
- **Fix**: `aplicar_si: {tipo_documento: ...}` en las 6 reglas, el mismo
  mecanismo que ya usaban los 3 esquemas de estructura:
  `referencias_minimo_cuantitativo` (tinv_cuantitativo),
  `referencias_minimo_cualitativo` (tinv_cualitativo),
  `referencias_minimo_revision` (tinv_revision_literatura),
  `anexos_minimos_cuantitativo` (tinv_cuantitativo),
  `anexos_minimos_cualitativo` (tinv_cualitativo) y
  `proyecto_caratula_texto` (proyecto_cuantitativo/proyecto_cualitativo).
- **Mutaciones**: en el doc base (cuantitativo) esas reglas ya no se evalúan,
  así que sus mutaciones quedaban inefectivas. Ahora componen un **volteo de
  tipo** (los headings que ya usaban las mutaciones de estructura; para
  proyecto, 2 firmas de título que ganan por orden de especificidad) con el
  desvío propio. El volteo mueve de paso a todas las reglas condicionadas:
  `REGLAS_ACOPLADAS` documenta esos acoples, y
  `tipo_documento_sin_estructura` entra a `CENTINELAS` (aparece solo en el
  doc mutado a proyecto).
- **Tests actualizados**: 42 de 48 evaluadas en el doc bueno (6 no aplicables),
  plantilla oficial con 2 errores reales (3 antes), la detección contradictoria
  retira también los mínimos del tipo cuantitativo, y el caso sin marcadores
  no inventa errores de ningún tipo. Suite completa: **388 tests pasan**.
- **Verificación**: Linares queda en **1 error** (solo
  `caratula_autores_mayusculas_sin_negrita`, un hallazgo real del estudiante)
  y 5 warnings; plantillas oficiales en **2 errores / 7 warnings** (antes
  3/10). Los falsos positivos tipo-específicos desaparecen como N/A.
  `ruff` + `mypy` limpios; `nix flake check` verde.

---

## Evidencias producidas

- Cambios en `validator/analizadores.py` (inferencia por títulos, declaración
  en tabla/sdt/w14), `validator/compilador.py` (centinelas con severidad por
  estado y warning de tipo sin estructura), `tests/test_tipo_documento.py`,
  `reglas_unt.yaml` (comentarios), `docs/DSL.md`, `docs/diseno/15_tipo_documento_grupos.md`,
  `README.md`, `AGENTS.md`, `docs/diseno/00_indice_diseno.md` y esta bitácora.
- Issue #1: `validator/extractor.py` (cuerpo semántico) y los fixtures
  `tests/_docx_builder.py` + `tests/test_paridad_formatos.py`.
- Issue #2: `validator/extractor.py` (`seccion_cuerpo`, `es_seccion_landscape`),
  `validator/analizadores.py` (rotación de márgenes en landscape),
  `reglas_unt.yaml` (contexto), `tests/test_margenes_landscape.py`, `docs/DSL.md`
  (documentado `contexto: seccion_cuerpo`).
- Issue #3/#4: `validator/extractor.py` (`contexto: caratula`,
  `_caratula_paras`), `reglas_unt.yaml` (XPath posicional del título + contexto),
  `tests/test_caratula.py`, `docs/DSL.md` (documentado `contexto: caratula`).
- Issue #5: `reglas_unt.yaml` (`aplicar_si` en 6 reglas tipo-específicas),
  `tests/_mutations.py` (volteos de tipo + acoples + `NO_APLICABLES_BASE`),
  `tests/test_propiedad.py` (centinela `tipo_documento_sin_estructura`),
  `tests/test_tipo_documento.py` (expectativas 42/48 y 6 no aplicables),
  `README.md` + `AGENTS.md` + `docs/diseno/00_indice_diseno.md` (conteos).
- Todo se agrupa en el **PR #45** (rama `semana7-fix-reglas-estructura`).
- Medición con documento real (no versionada; los DOCX/PDF de estudiantes
  quedan fuera del repo, en la raíz local y en `docs/pruebas/`).

---

## Relación con competencias curriculares

- **Ingeniería de Software II**: manejo de la revisión de un PR (respuesta a
  los tres puntos del revisor), ajuste del diseño y validación con tests.
- **Estructura de Datos**: recorridos del árbol XML del DOCX (títulos, tablas,
  content-control) y normalización de texto para el conteo de firmas.
- **Ingeniería de Software I**: documentación precisa del cambio (DSL, diseño
  de decisiones, conteos sincronizados).

---

## Dificultades y aprendizajes

- **La "estructura real" no es la última sección**: el doc de paridad y el
  factory construían el cuerpo DESPUÉS de los anexos; el enfoque semántico los
  dejaba vacíos y rompía 15 tests. Ajustar los fixtures (prosa tras
  "Introducción") los realineó sin tocar la lógica del motor.
- **`find()` de lxml no baja a los nietos**: el `w14:checked` vive dentro de
  `w:sdtPr`, y la primera versión no lo encontraba (solo los tests de
  content-control lo delataron).
- **La medición no miente**: el "1/2 de proyecto" que la carátula regalaba por
  prosa se descartó como riesgo hasta que la medición sobre una tesis real lo
  confirmó. Con la tesis de Linares quedó claro que una TINV real está a un
  título ruidoso de virar.
- **Scope control**: la revisión pedía tres cosas puntuales; se resolvieron y
  se dejó explícito qué NO se tocó (el solape de informe, las 5 estructuras
  pendientes, los demás issues del handover).

---

## Plan de la semana siguiente

1. Revisar el último issue del handover/INFORME: `vals[:3]` (#7 — el
   reporting de `all_eq` esconde los valores no conformes). El `aplicar_si`
   (#5) y los de carátula (#3/#4) ya quedaron.
2. Convertir la tesis de Carrión (PDF) para poder validarla y medir la
   detección con un segundo documento real.
3. Incorporar las 5 estructuras pendientes (`reglas_unt_pendientes.yaml`) a
   producción cuando haya plantillas reales de proyecto/informe/TSP.