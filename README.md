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

### 5. API HTTP (FastAPI)

Endpoint `POST /validar` que recibe un `.docx` y devuelve el reporte en JSON. Ver [`docs/CONTRATO_API.md`](docs/CONTRATO_API.md) para el contrato completo y [`docs/FLUJO_API.md`](docs/FLUJO_API.md) para el diagrama de flujo.

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
>   `mecanismo_verificable`). **Es el que carga la API** (`validator/api.py`).
> - `reglas_unt.yaml` — formato **DSL** (autómatas/analizadores), generado por
>   `scripts/migrar_legacy_a_dsl.py` (F1 del plan en [`docs/PLAN_DSL.md`](docs/PLAN_DSL.md)).
>   **La API todavía NO lo carga**: cambiarla es una fase coordinada. Ambos
>   motores dan resultados idénticos (paridad verificada con
>   `scripts/evaluar_paridad_plantillas.py` contra `recursos/`).

```
validator/
  __init__.py
  models.py     — RuleResult, Severity (error|warning)
  extractor.py  — abre el .docx (zip OPC), expone document.xml/footer1.xml/header1.xml
                  y el contexto "cuerpo" (párrafos de la última sección)
  checks.py     — ejecuta cada tipo de check (xml_atributo, xml_presencia,
                  texto_regex, texto_en_lista, secuencia_titulos, imagen_presencia)
  engine.py     — carga el YAML, corre las reglas mecanizadas, arma el reporte
  prompts.py    — genera el bloque "cómo preguntar a una IA" por cada regla
                  fallida (template-based, sin LLM en runtime)
  cli.py        — CLI de referencia para correr el validador contra un DOCX

scripts/
  eval_contra_plantillas.py  — corre el motor contra un directorio de .docx
                                (reemplaza el batch-eval de eval_checks2.py)
```

**Filtro de severidad**: `engine.build_report(resultados, severities=["error"])` filtra el reporte detallado por severidad, pero el semáforo SIEMPRE se calcula sobre todos los `error` sin filtrar — un filtro de visualización nunca puede ocultar un bloqueo real de la entrega.

### Cómo correrlo

```bash
nix develop   # entorno con python, pyyaml, lxml, etc.

# validar un DOCX
python -m validator.cli tesis.docx unt_format_rules_schema.yaml

# solo errores bloqueantes
python -m validator.cli tesis.docx unt_format_rules_schema.yaml --severity error

# reporte completo en JSON (incluye "como_preguntar_a_una_ia")
python -m validator.cli tesis.docx unt_format_rules_schema.yaml --json

# evaluar un lote de plantillas/tesis de prueba
python scripts/eval_contra_plantillas.py unt_format_rules_schema.yaml ruta/a/plantillas/
```

## Stack técnico

- **Backend**: Python, FastAPI (validación de tipos vía Pydantic, encaja bien porque el trabajo es CPU-bound, no I/O-bound).
- **Frontend**: React.
- **Parsing DOCX**: `python-docx`, `lxml` para casos borde.
- **Parsing PDF**: `PyMuPDF` (fitz).
- **Config de reglas**: YAML (`pyyaml`).
- **Hosting**: on-premise en infraestructura de la universidad. Sin dependencias de servicios externos en tiempo de ejecución (sin llamadas a APIs de LLM en producción, bajo la restricción actual).
- **Entorno de desarrollo**: Nix flake (`flake.nix`) — Python 3.14 + dependencias del motor + toolchain de OCR (`ocrmypdf`, `tesseract` con español, `poppler_utils`) para procesar los reglamentos escaneados pendientes.

## Extensiones futuras (fuera de alcance por ahora)

- Capa de checks semánticos con un LLM local (vía Ollama o llama.cpp server, API compatible OpenAI) para validaciones que las reglas deterministas no pueden capturar: coherencia del resumen, consistencia del estilo de citas, correspondencia entre índice y títulos de capítulo reales.
- Si se agrega, correría *después* de que el documento pase las reglas deterministas (para no gastar cómputo en documentos que ya van a fallar por formato), y solo recibiría el fragmento relevante + la regla textual específica, no el reglamento completo.

## Estado actual

Motor de reglas de producción implementado y probado end-to-end (extractor + checks + engine + filtro de severidad + generador de prompts), validado contra un DOCX de prueba y contra las 5 plantillas oficiales (25/32 mecanizadas PASS). Los dos RCU escaneados fueron leídos vía OCR (2026-09-02) y quedaron reflejados en el YAML: la lista de líneas de investigación del RCU-220 alimenta la regla `caratula_linea_investigacion` y el aporte del RCU-274 (Anexo 5) se registró como no determinista.

**API implementada** (semana 2-3): `POST /validar` en FastAPI, contrato v1.1.0 "Implementado". Ver [`docs/CONTRATO_API.md`](docs/CONTRATO_API.md) para el contrato completo y [`docs/FLUJO_API.md`](docs/FLUJO_API.md) para el diagrama de flujo. Frontend React pendiente de conexión.
