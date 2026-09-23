# VistoBueno

Web app de la **Facultad de Educación y Ciencias de la Comunicación (FECyC), Universidad Nacional de Trujillo (UNT)** para que estudiantes suban su tesis (DOCX o PDF) y reciban validación automática contra las directivas de formato de la universidad, antes de la entrega formal.

El nombre viene directo del corazón del producto: el semáforo verde ("visto bueno") que le dice al estudiante que puede entregar, sin depender de que un asesor revise el formato a mano.

## Objetivo

- El usuario sube un archivo DOCX o PDF.
- El backend analiza el archivo contra un conjunto de reglas de formato (márgenes, tipografía, interlineado, estructura, numeración, etc.).
- Si todo pasa: luz verde, el usuario puede entregar.
- Si algo falla: se muestra un cartel simple (si es poco) o un reporte detallado (si hay varios problemas).
- El reporte incluye una sección **"Cómo preguntar a una IA"**: por cada problema detectado, un prompt ya armado que el estudiante puede copiar y pegar en cualquier LLM externo (ChatGPT, Claude, etc.) para corregirlo, incluyendo el fragmento de la directiva relevante como contexto.

## Restricción de diseño clave

**No se puede correr un LLM en tiempo de ejecución** (por ahora). Esto significa:

- Todas las reglas de validación deben ser **deterministas**: medibles directamente desde el archivo (número, booleano, string exacto), sin requerir "juicio" de un modelo.
- Un LLM externo **sí se usa en tiempo de diseño**, una sola vez (o cada vez que cambie el reglamento de la universidad), para ayudar a convertir el manual de formato oficial (PDF/DOCX del reglamento de tesis) en el esquema de reglas estructurado que consume el backend. Este paso es semi-automático: el LLM propone un borrador de reglas, un humano lo revisa y ajusta.
- La sección "Cómo preguntar a una IA" del reporte es **generada por template**, no por un LLM en el momento — se arma a partir de los resultados de las reglas que fallaron. Esto garantiza que el prompt sugerido sea siempre consistente y no dependa de que un modelo "recuerde" bien qué falló.

Si en el futuro se decide correr un LLM local en tiempo de ejecución (para checks semánticos que las reglas deterministas no pueden capturar, como "¿el resumen realmente resume el contenido?"), la arquitectura ya está pensada para agregar esa capa sin romper lo demás — ver sección "Extensiones futuras".

## Arquitectura

```
┌─────────────┐     ┌────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Archivo   │ --> │   Extractor     │ --> │  Motor de reglas  │ --> │  Agregador de     │
│  DOCX/PDF   │     │ (normaliza el   │     │  (determinista,   │     │  reporte + prompts │
│             │     │  documento)     │     │  YAML/JSON)       │     │  "cómo preguntar"  │
└─────────────┘     └────────────────┘     └──────────────────┘     └──────────────────┘
```

### 1. Extractor

Convierte el archivo subido en una representación normalizada e independiente del formato de entrada (DOCX o PDF), con datos como: fuente y tamaño por párrafo, interlineado, márgenes de página, alineación, estructura de secciones/capítulos, presencia de portada/índice/numeración.

- **DOCX**: `python-docx` para estilos y estructura semántica; XML crudo (`lxml`) para detalles que `python-docx` no expone directamente (ej. numeración de página).
- **PDF**: `PyMuPDF` (fitz) para posición, fuente y tamaño de cada span de texto, y cálculo de márgenes reales a partir del bounding box del contenido contra el tamaño de página.

### 2. Esquema de reglas (YAML/JSON)

Las directivas de formato viven en un archivo de configuración separado del código (no hardcodeadas). Ver `unt_format_rules_schema.yaml` para el esquema real y completo (44 reglas, 32 con mecanismo verificable ejecutable).

### 3. Motor de reglas

Cada regla es una función pura: recibe el documento normalizado y el parámetro de la regla, devuelve un resultado estructurado (`RuleResult`: rule_id, passed, severity, message, expected, found, location).

### 4. Agregador de reporte

- Si todos los `RuleResult` con `severity="error"` pasan → luz verde.
- Si no → reporte agrupado por categoría (márgenes, tipografía, estructura, citas, etc.), con opción de vista simple (cartel) o detallada.
- Por cada `RuleResult` fallido, genera un bloque "cómo preguntar a la IA" con el prompt armado y referencia textual a la directiva del reglamento correspondiente.

## Generación del esquema de reglas a partir del reglamento oficial (tiempo de diseño)

Proceso puntual, no parte del flujo de producción:

1. Se le pasa el PDF/DOCX del reglamento oficial de formato de tesis de la universidad a un LLM externo.
2. Se le pide que proponga un borrador de reglas en el formato YAML de este proyecto, citando de qué parte del reglamento sale cada una.
3. Un humano revisa, corrige y confirma el YAML final.
4. Ese YAML pasa a ser la fuente de verdad que consume el motor de reglas.

Este proceso se puede repetir cada vez que cambie el reglamento, sin tocar el código del backend.

## Reglas generadas a partir del reglamento real (UNT — FECyC)

Se generó `unt_format_rules_schema.yaml` a partir de: `MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx` y las 5 plantillas oficiales por programa. La comparación entre plantillas confirmó que **el formato es idéntico entre todos los programas** (mismos márgenes, fuente, interlineado, estructura de secciones); solo varía texto de carátula dependiente del programa (nombre de escuela/programa, mención, texto de "optar título"). Esto significa que el validador puede usar un **esquema de reglas único**, no uno por programa.

Cubre: papel/márgenes, fuente y tamaños (cuerpo y carátula), interlineado, alineación, numeración de página (romanos en preliminares, arábigos desde Introducción), sangría, estructura obligatoria de secciones para los tres tipos de trabajo (Cuantitativo, Cualitativo, Revisión de la Literatura) más Proyecto de Investigación y Suficiencia Profesional, y la validación de la línea de investigación de la carátula contra el catálogo oficial del RCU-N°220-2022/UNT.

Las 32 reglas con mecanismo verificable fueron evaluadas end-to-end contra las 5 plantillas oficiales: **25/32 PASS**. Los 7 FAIL restantes son desvíos reales documentados (no bugs del evaluador): tamaños de fuente en carátula, sangría, aplicabilidad de estructura por tipo de trabajo (cuantitativo/cualitativo/revisión), y los 3 índices separados que el manual exige pero ninguna plantilla implementa.

### Fuera de alcance del MVP (decisión explícita, no olvido)

- **Mínimo de referencias bibliográficas según tipo de investigación** (20 para Cuantitativo/Revisión, 30 para Cualitativo): requiere saber el tipo de trabajo, y aún no se definió cómo determinarlo (¿lo declara el usuario al subir?, ¿se detecta por encabezados únicos de sección?). Queda pendiente para después del MVP.
- **Anexos obligatorios por tipo de trabajo** (matriz de consistencia, consentimiento informado, declaración jurada, etc.): depende de la misma decisión de tipo de investigación que el punto anterior. Fuera del MVP por ahora.
- **Validación de texto de carátula dependiente del programa** (ej. "AUTORA" vs "AUTOR(A)", línea de "Mención" solo en Tecnología Educativa): detectado en la comparación de plantillas pero sin regla formal aún — necesitaría una tabla programa → texto esperado, no una regla genérica.
- **Sangría de primera línea (1.27 cm)**: el manual la exige; las plantillas usan 708/709 twips (~1.25 cm), no 720. Ver decisión de severidad abajo.

### Decisión tomada (2026-09-01): 3 reglas bajadas de `error` a `warning`

`caratula_titulo_trabajo_tamano` (14pt manual vs 13pt plantillas), `caratula_optar_grado_tamano` (13pt manual vs 12pt plantillas) y `sangria_parrafo` (720 twips manual vs 708/709 twips plantillas): las 5 plantillas oficiales de la universidad se desvían del texto del manual de forma unánime en estos tres puntos. Hasta que la universidad confirme cuál valor es el correcto, el validador no bloquea la entrega por esto — el reporte lo sigue mostrando como advertencia. Cambio aplicado en `unt_format_rules_schema.yaml`.

### Reglamentos RCU leídos vía OCR (2026-09-02)

Ambos reglamentos en PDF escaneado estaban pendientes de OCR (ver README anterior y anotaciones obsoletas del YAML). Ya se les extrajo texto con el script `scripts/ocr_pdfs.py` (motor híbrido PyMuPDF + tesseract), y el resultado quedó en `recursos/ocr/*.txt`:

- `RCU-N-274-2022-UNT.txt` — Reglamento N° 007-2022-UNT/URA (Reglamento General de Otorgamiento de Grados Académicos y Títulos Profesionales). Es un reglamento de **procedimientos administrativos** de graduación/titulación, no de formato DOCX. Su único aporte a la validación es el **Anexo 5** (esquemas de proyecto/informe de investigación y de artículo científico), que se registró como **no determinista** (ver `unt_format_rules_schema.yaml` → `no_deterministas`).
- `RCU-N-220-2022-UNT-LINEAS DE INVESTIGACION.txt` — catálogo de líneas de investigación (Tablas 1, 2 y 3: consolidadas, por consolidar y emergentes). La hipótesis previa de estructura **"código - nombre" quedó descartada**: las líneas van por número correlativo + nombre, sin código alfanumérico. La lista oficial alimenta la nueva regla `caratula_linea_investigacion`, que valida que la línea declarada en la carátula sea una de las aprobadas por el RCU-220.

## Motor de reglas (re-arquitecturado — reemplaza al prototipo `eval_checks2.py`)

> **Dos formatos de reglas coexisten (ver [`docs/DSL.md`](docs/DSL.md)):**
> - `unt_format_rules_schema.yaml` — formato **legacy** (checks con
>   `mecanismo_verificable`). Es la fuente histórica (Semana 2); la API ya no lo
>   carga.
> - `reglas_unt.yaml` — formato **DSL** (autómatas/analizadores), **47 reglas**:
>   las 32 legacy migradas (F1) + 9 reglas antes no-deterministas mecanizadas
>   a mano en la F3 (tokenizer + analizadores de conteo/lista/hipervínculo)
>   + `indice_paginas_separadas` (paginación real por `w:lastRenderedPageBreak`)
>   + encabezados/pies, notas al pie (F2 ítems 1-3) + `indice_apunta_secciones`
>   e `indice_numeracion_jerarquica` (F2 ítems 11-12, índice de contenidos).
>   **Es el que carga la API** (`validator/api.py`, desde la **F5**, Semana 4).
>   Para las 32 reglas compartidas, ambos motores dan resultados idénticos
>   (paridad verificada con `scripts/evaluar_paridad_plantillas.py` contra
>   `recursos/`).

```
validator/
  __init__.py         # Docstring del paquete
  models.py           # RuleResult (dataclass), Severity (Enum)
  extractor.py        # Abre .docx, extrae XML (ExtractedDocx)
  checks.py           # Checks individuales (xpath, atributos, regex)
  engine.py           # Carga YAML, corre reglas, arma reporte
  prompts.py          # Generador de prompts "cómo preguntar a una IA"
  cli.py              # CLI de referencia
  exportador.py       # Exporta el reporte a Markdown y PDF
  api.py              # FastAPI endpoint POST /validar
  api_models.py       # Pydantic DTOs (ValidarResponse, etc.)
  tokenizer.py        # Análisis léxico DSL (TITULO, PARRAFO, etc.)
  analizadores.py     # Analizadores de hoja (XML, regex, lista, imagen)
  automata.py         # DFA, GramaticaEstructura, PDA
  compilador.py       # CompilerDSL: YAML → analizadores → RuleResult
  dsl_check.py        # Linter del DSL (valida config al cargar)

tests/
  test_api_contract.py      # Tests de contrato para la API
  test_dsl.py               # Tests del DSL (DFA, gramática, compilador)
  test_f2_automatas.py      # Tests F2: tokenizer, PDA, automata_pila
  test_f3_mecanizacion.py   # Tests F3: reglas no deterministas
  test_f4_ingenieria.py     # Tests F4: linter, cache, traza
  test_paridad_formatos.py  # Paridad legacy vs DSL
  test_propiedad.py         # Tests de propiedad (factory + mutaciones)
  test_exportador.py        # Tests de exportación a Markdown/PDF
  docx_factory.py           # Factory determinista de DOCX
  _docx_builder.py          # Builder interno de DOCX
  _mutations.py             # Mutaciones sincronizadas con reglas_unt.yaml
  _xml_constants.py         # Constantes XML para el builder

scripts/
  eval_contra_plantillas.py       # Evaluación batch contra plantillas
  evaluar_paridad_plantillas.py   # Paridad legacy vs DSL (recursos/)
  migrar_legacy_a_dsl.py          # Migra YAML legacy → DSL
  ocr_pdfs.py                     # OCR de reglamentos escaneados

reglas_unt.yaml            # Reglas en formato DSL (47 reglas)
reglas_dsl_ejemplo.yaml    # Ejemplo de reglas DSL
```

**Filtro de severidad**: `engine.build_report(resultados, severities=["error"])` filtra el reporte detallado por severidad, pero el semáforo SIEMPRE se calcula sobre todos los `error` sin filtrar — un filtro de visualización nunca puede ocultar un bloqueo real de la entrega.

### Cómo correrlo

```bash
nix develop   # entorno con todas las dependencias

# tests (vía nix run — recomendado)
nix run .#test -- tests/ -v

# tests (directo, requiere nix develop activo)
pytest tests/ -v

# API en desarrollo
nix run .#serve -- validator.api:app --reload
# Swagger UI: http://localhost:8000/docs

# API (directo)
uvicorn validator.api:app --reload

# validar un DOCX desde CLI
python -m validator.cli tesis.docx unt_format_rules_schema.yaml

# solo errores bloqueantes
python -m validator.cli tesis.docx unt_format_rules_schema.yaml --severity error

# reporte completo en JSON (incluye "como_preguntar_a_una_ia")
python -m validator.cli tesis.docx unt_format_rules_schema.yaml --json

# exportar el reporte a Markdown o PDF (para la bitácora/entrega)
python -m validator.cli tesis.docx reglas_unt.yaml --formato markdown --salida reporte.md
python -m validator.cli tesis.docx reglas_unt.yaml --formato pdf --salida reporte.pdf

# exportar un reporte JSON preexistente
python -m validator.exportador reporte.json reporte.md
python -m validator.exportador reporte.json reporte.pdf

# evaluar un lote de plantillas/tesis de prueba
python scripts/eval_contra_plantillas.py unt_format_rules_schema.yaml ruta/a/plantillas/

# calidad de ingeniería (lint, tipos y medición de cobertura)
ruff check validator/ scripts/ tests/
ruff format --check validator/ scripts/ tests/
mypy validator/ scripts/
pytest tests/ --cov=validator --cov-report=term-missing

# verificación completa (tests + lint del flake + tipos + cobertura)
nix flake check
```

La suite (**204 tests**) incluye los **tests de propiedad** (F6): un factory
determinista de DOCX (`tests/docx_factory.py`, descompuesto en
`tests/_xml_constants.py`, `tests/_docx_builder.py` y `tests/_mutations.py`;
este último **sincroniza sus mutaciones con `reglas_unt.yaml` al importar`)
genera un documento "bueno" (45/47) y 47 mutaciones de una sola propiedad
(`tests/test_propiedad.py`), verificando que un desvío mínimo invalida solo
su regla. Sobre eso, las **mejoras de ingeniería F4** agregaron: un **linter
del DSL** (`validator/dsl_check.py`) que valida la configuración al cargar
(regex inválida, comparaciones sin `esperado`, estados inalcanzables,
ciclos épsilon), **cache de consultas XPath** por documento y la
**traza del autómata** (`ruta_estados` / `ultima_ruta`).

## Stack técnico

- **Backend**: Python, FastAPI (validación de tipos vía Pydantic, encaja bien porque el trabajo es CPU-bound, no I/O-bound).
- **Frontend**: React.
- **Parsing DOCX**: `python-docx`, `lxml` para casos borde.
- **Parsing PDF**: `PyMuPDF` (fitz).
- **Config de reglas**: YAML (`pyyaml`).
- **Hosting**: on-premise en infraestructura de la universidad. Sin dependencias de servicios externos en tiempo de ejecución (sin llamadas a APIs de LLM en producción, bajo la restricción actual).
- **Frontend tooling**: Vite + React (`frontend/`).
- **Entorno de desarrollo**: Nix flake (`flake.nix`) — Python 3.14 + dependencias del motor + toolchain de OCR (`ocrmypdf`, `tesseract` con español, `poppler_utils`) + tooling de calidad (ruff, mypy, pre-commit) y de exportación (markdown, WeasyPrint). Incluye `nix run .#test` (pytest), `nix run .#serve` (uvicorn) y `nix flake check` para verificación completa (tests + ruff + mypy + cobertura).

### Despliegue del frontend (`VITE_API_URL` y proxy)

El frontend llama a `POST /validar` con `API_BASE_URL = import.meta.env.VITE_API_URL || ''` (`frontend/src/App.jsx`).

| Entorno | Cómo llega al backend |
|---------|----------------------|
| **`npm run dev`** (desarrollo) | Proxy de Vite en `vite.config.js` enruta `/validar` → `http://localhost:8000`. El default `VITE_API_URL=''` (mismo origen) funciona sin configurar nada. |
| **`npm run preview` / build estático** | **No existe el proxy de Vite.** Hay que: (1) definir `VITE_API_URL` en tiempo de build hacia el origen de la API, o (2) servir el build detrás de un **reverse proxy** (nginx, Caddy, etc.) que enroute `/validar` al backend FastAPI. |
| **Build con API en otro origen** | `VITE_API_URL=https://api.tudominio.com npm run build` (o variable en CI). Ver `frontend/.env.example`. |

Mientras `VITE_API_URL` quede vacío en un despliegue **sin** proxy/reverse proxy, las llamadas a `/validar` fallarán con error de red y el UI entrará en modo demo (reporte mock avisado). Errores HTTP del backend **con** cuerpo JSON (`detail`) se muestran al usuario y **no** se sustituyen por mocks.

## Extensiones futuras (fuera de alcance por ahora)

- Capa de checks semánticos con un LLM local (vía Ollama o llama.cpp server, API compatible OpenAI) para validaciones que las reglas deterministas no pueden capturar: coherencia del resumen, consistencia del estilo de citas, correspondencia entre índice y títulos de capítulo reales.
- Si se agrega, correría *después* de que el documento pase las reglas deterministas (para no gastar cómputo en documentos que ya van a fallar por formato), y solo recibiría el fragmento relevante + la regla textual específica, no el reglamento completo.

## Estado actual

Motor de reglas de producción implementado y probado end-to-end (extractor + checks + engine + filtro de severidad + generador de prompts), validado contra un DOCX de prueba y contra las 5 plantillas oficiales (25/32 mecanizadas PASS). Los dos RCU escaneados fueron leídos vía OCR (2026-09-02) y quedaron reflejados en el YAML: la lista de líneas de investigación del RCU-220 alimenta la regla `caratula_linea_investigacion` y el aporte del RCU-274 (Anexo 5) se registró como no determinista.

**API FastAPI** implementada (`POST /validar`) con validación de entrada, manejo de errores, DTOs Pydantic y suite de tests de contrato (ver `docs/CONTRATO_API.md`). **Frontend React** inicializado con Vite (`frontend/`), con mockups de las pantallas de carga y reporte (`mockups/`). **Motor DSL** consolidado (F1–F6): 47 reglas mecanizadas (incluye paginación real `indice_paginas_separadas`, ubicación por página, encabezados/pies, notas al pie, e índice de contenidos con `indice_apunta_secciones`/`indice_numeracion_jerarquica`), linter, cache XPath, traza de autómata y tests de propiedad con factory determinista de DOCX. **Calidad de ingeniería** (ruff, mypy, coverage, pre-commit, CI con Nix) y **exportación del reporte a Markdown/PDF** implementadas (tareas 15 y 16 del `docs/PLAN_BACKLOG_FUTURO.md`).
