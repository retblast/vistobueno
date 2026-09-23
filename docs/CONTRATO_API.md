# Contrato de API — VistoBueno

**Versión**: 1.2.0 (Semana 4)  
**Fecha**: 2026-09-23  
**Estado**: Implementado

---

## Endpoint principal

### `POST /validar`

Recibe un archivo DOCX de tesis y devuelve un reporte de validación estructurado contra las reglas de formato de la UNT.

---

## Requisitos de la solicitud

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `archivo` | `file` | Sí | Archivo `.docx` a validar |
| `correo` | `string` (form) | No | Correo electrónico del estudiante. Si se envía, debe tener formato válido (`usuario@dominio`); se usará para notificar resultados cuando el envío esté habilitado (Actividad 6). Cadena vacía se trata como ausente. |
| `incluir_prompts_ia` | `bool` (query) | No (default: `true`) | Incluir la sección "Cómo preguntar a una IA" en la respuesta |

### Content-Type

```
multipart/form-data
```

### Tipos de archivo aceptados

| Extensión | MIME Type |
|-----------|-----------|
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.docx` | `application/octet-stream` (algunos navegadores envían este MIME type) |

### Validación de cabecera (magic bytes)

El archivo debe comenzar con la firma ZIP local `PK\x03\x04` (todo DOCX es un
paquete OPC comprimido). Archivos renombrados a `.docx` sin cabecera ZIP se
rechazan con `422` antes de intentar abrirlos.

### Tamaño máximo

10 MB

---

## Respuestas

### 200 OK — Validación exitosa

El archivo se procesó correctamente y se evaluaron las reglas.

```json
{
  "semaforo": "verde",
  "resumen": {
    "total": 47,
    "fallidos_error": 0,
    "fallidos_warning": 0
  },
  "resultados": [
    {
      "rule_id": "papel_tamano",
      "paso": true,
      "severidad": "error",
      "mensaje": "El tamaño del papel debe ser A4",
      "esperado": "210 x 297 mm",
      "encontrado": "cumple",
      "ubicacion": "Sección \"Formato general\" (párr. 124-125)",
      "fuente": "MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx",
      "cita": "\"Tamaño A4/papel (210x297 cm)\""
    }
  ],
  "como_preguntar_a_una_ia": [
    {
      "rule_id": "caratula_titulo_trabajo_tamano",
      "prompt": "Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: Tamaño de letra del título del trabajo en carátula\n- Valor esperado según el reglamento: 14pt\n- Lo que encontró el validador: @w:val=['26'] esperado=28\n- Cita del reglamento: \"Título del Trabajo...\"\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?"
    }
  ],
  "metadatos": {
    "archivo_nombre": "tesis.docx",
    "archivo_tamano_bytes": 123456,
    "reglas_evaluadas": 47,
    "version_esquema": "2026-09-01"
  }
}
```

### Descripción de campos de respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `semaforo` | `string` | `"verde"` si todas las reglas de severidad `error` pasan; `"rojo"` si alguna falla |
| `resumen.total` | `int` | Total de reglas evaluadas |
| `resumen.fallidos_error` | `int` | Reglas con severidad `error` que no pasaron |
| `resumen.fallidos_warning` | `int` | Reglas con severidad `warning` que no pasaron |
| `resultados` | `array` | Lista de resultados individuales por regla |
| `resultados[].rule_id` | `string` | Identificador único de la regla |
| `resultados[].paso` | `bool` | `true` si la regla se cumplió |
| `resultados[].severidad` | `string` | `"error"` o `"warning"` |
| `resultados[].mensaje` | `string` | Descripción de la regla en lenguaje natural |
| `resultados[].esperado` | `string` | Valor esperado según el reglamento |
| `resultados[].encontrado` | `string` | Lo que encontró el validador (`"cumple"` si pasó) |
| `resultados[].ubicacion` | `string?` | Referencia al documento del reglamento |
| `resultados[].fuente` | `string` | Archivo fuente del que se extrajo la regla |
| `resultados[].cita` | `string` | Cita textual del reglamento |
| `como_preguntar_a_una_ia` | `array` | Bloques de prompts listos para copiar/pegar en una IA |
| `como_preguntar_a_una_ia[].rule_id` | `string` | ID de la regla fallida |
| `como_preguntar_a_una_ia[].prompt` | `string` | Prompt completo en español |
| `metadatos.archivo_nombre` | `string` | Nombre original del archivo subido |
| `metadatos.archivo_tamano_bytes` | `int` | Tamaño en bytes del archivo |
| `metadatos.reglas_evaluadas` | `int` | Cantidad de reglas ejecutadas |
| `metadatos.version_esquema` | `string` | Versión del esquema YAML de reglas |

### 422 Unprocessable Entity — Sin archivo (validación de FastAPI)

FastAPI valida automáticamente que el campo `archivo` esté presente. Si no se envía, devuelve su propio 422 con un mensaje de validación:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "archivo"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

### 400 Bad Request — Sin nombre de archivo

Si el campo `archivo` está presente pero el nombre está vacío:

```json
{
  "detail": "Campo 'archivo' requerido. Envíe un archivo .docx en el campo 'archivo' del formulario multipart."
}
```

### 415 Unsupported Media Type — Tipo incorrecto

El endpoint valida primero la extensión del archivo y luego el Content-Type. Dependiendo de cuál falle, devuelve un mensaje diferente:

**Extensión incorrecta** (ej. enviar un `.txt`):

```json
{
  "detail": "Tipo de archivo no soportado: 'documento.txt'. Solo se aceptan archivos .docx (.docx)."
}
```

**Content-Type no soportado** (extensión correcta pero MIME type inválido):

```json
{
  "detail": "Content-Type no soportado: 'text/plain'. Solo se aceptan archivos .docx."
}
```

### 413 Request Entity Too Large — Archivo muy grande

Para evitar cargar uploads arbitrariamente grandes en memoria, el servidor
lee a lo sumo 10 MB + 1 byte del body. Por eso el mensaje **no** reporta el
tamaño exacto recibido:

```json
{
  "detail": "El archivo excede el tamaño máximo permitido (10 MB)."
}
```

### 422 Unprocessable Entity — Archivo corrupto o inválido

```json
{
  "detail": "No se pudo procesar el archivo DOCX: archivo corrupto o no es un DOCX válido."
}
```

### 422 Unprocessable Entity — Cabecera ZIP inválida (magic bytes)

El archivo no comienza con la firma `PK\x03\x04` (no es un ZIP/DOCX):

```json
{
  "detail": "El archivo no es un ZIP/DOCX válido: cabecera incorrecta (se esperaba la firma 'PK')."
}
```

### 422 Unprocessable Entity — ZIP válido pero sin `word/document.xml`

El archivo es un ZIP pero no contiene la parte esencial `word/document.xml`
(el extractor lanza `KeyError`):

```json
{
  "detail": "El archivo no contiene un documento Word válido: archivo interno faltante ('word/document.xml')."
}
```

### 422 Unprocessable Entity — Estructura DOCX inválida

El extractor no encontró una parte esperada del DOCX (lanza `ValueError`):

```json
{
  "detail": "El archivo no contiene un documento Word válido: <detalle del extractor>."
}
```

### 422 Unprocessable Entity — Correo electrónico inválido

Si el campo `correo` se envía pero no tiene formato válido:

```json
{
  "detail": "Correo electrónico inválido: 'no-es-un-correo'. Formato esperado: usuario@dominio."
}
```

### 422 Unprocessable Entity — Archivo vacío

```json
{
  "detail": "El archivo está vacío."
}
```

### 500 Internal Server Error — Error interno

```json
{
  "detail": "Error interno del validador: ExceptionType: mensaje de error"
}
```

> **Nota**: El detalle incluye el tipo de excepción y el mensaje para facilitar
> el diagnóstico en desarrollo. En producción podría omitirse por seguridad.

---

## Ejemplo de solicitud curl

```bash
curl -X POST "http://localhost:8000/validar?incluir_prompts_ia=true" \
  -F "archivo=@mi_tesis.docx"
```

---

## Ejemplo con correo del estudiante

```bash
curl -X POST "http://localhost:8000/validar?incluir_prompts_ia=true" \
  -F "archivo=@mi_tesis.docx" \
  -F "correo=estudiante@unitru.edu.pe"
```

---

## Ejemplo de solicitud sin prompts IA

```bash
curl -X POST "http://localhost:8000/validar?incluir_prompts_ia=false" \
  -F "archivo=@mi_tesis.docx"
```

---

## Códigos de estado

| Código | Significado |
|--------|-------------|
| `200` | Validación exitosa |
| `400` | Campo `archivo` presente pero sin nombre |
| `413` | Archivo excede 10 MB |
| `415` | Tipo de archivo no soportado (no es `.docx`) |
| `422` | Solicitud mal formada (sin campo `archivo`) / Cabecera ZIP inválida / Archivo vacío / DOCX corrupto o sin estructura válida / Correo inválido |
| `500` | Error interno del servidor |

---

## Mapeo del motor interno → API

El motor interno (`validator.engine`) devuelve `RuleResult` (dataclass) y `build_report()` devuelve un diccionario. La API mapea estos a los modelos Pydantic DTO:

| Motor interno | API (JSON) | Notas |
|---------------|------------|-------|
| `RuleResult.rule_id` | `resultados[].rule_id` | Sin cambio |
| `RuleResult.passed` | `resultados[].paso` | Renombrado a español |
| `RuleResult.severity` | `resultados[].severidad` | `"error"` o `"warning"` |
| `RuleResult.message` | `resultados[].mensaje` | Renombrado a español |
| `RuleResult.expected` | `resultados[].esperado` | Renombrado a español |
| `RuleResult.found` | `resultados[].encontrado` | Renombrado a español |
| `RuleResult.location` | `resultados[].ubicacion` | Renombrado a español |
| `RuleResult.fuente` | `resultados[].fuente` | Sin cambio |
| `RuleResult.cita` | `resultados[].cita` | Sin cambio |
| `build_report()["semaforo"]` | `semaforo` | Sin cambio |
| `build_report()["resumen"]` | `resumen` | Renombrado a español |
| `build_report()["resultados"]` | `resultados` | Mapeado a DTO |
| `build_ai_help_section()` | `como_preguntar_a_una_ia` | Solo si `incluir_prompts_ia=true` |
| — | `metadatos` | Agregado por la API (no existe en motor) |

---

## Changelog

### v1.2.0 (2026-09-23 — Semana 4, cierre Actividad 5)

- **Nuevo campo opcional `correo`** (form field): formato validado con
  `email-validator`; inválido → `422` con mensaje en español. Vacío o
  ausente se trata como `None` (retrocompatible).
- **Validación de magic bytes**: el archivo debe comenzar con la firma ZIP
  `PK\x03\x04`; si no, `422` antes de procesarlo.
- **Documentación de errores 400 / 422** que faltaban: nombre de archivo
  vacío, cabecera ZIP inválida, ZIP sin `word/document.xml` (`KeyError`),
  estructura DOCX inválida (`ValueError`), correo inválido.
- **Tabla de códigos de estado** actualizada: agregado `400` y desglose de
  los distintos `422`.
- **Tipos MIME aceptados**: documentado `application/octet-stream` además
  del MIME oficial de OOXML.
- Ejemplo `curl` con campo `correo`.
- Lectura del upload limitada a 10 MB + 1 byte: el `413` ya no reporta
  "Tamaño recibido" (cambio solo del texto del mensaje).
- Ejemplos de respuesta sincronizados a 47 reglas (antes decían 31).
- Versión del endpoint: `1.1.0` → `1.2.0` (cambio aditivo, sin romper
  clientes existentes).

### v1.1.1 (2026-09-15 — Semana 4, nota F5)

- Sin cambios de campos en el contrato (las llamadas son idénticas).
- Fuente de reglas: la API carga `reglas_unt.yaml` (DSL, 47 reglas) desde la
  F5, en lugar del YAML legacy `unt_format_rules_schema.yaml`.

### v1.1.0 (2026-09-09 — Semana 3)

- Estado: **Implementado** (antes: Diseño)
- Corregido ejemplo 500 para reflejar comportamiento real (incluye tipo de excepción)
- Documentación del flujo completo en `docs/FLUJO_API.md`

### v1.0.0 (2026-09-02 — Semana 2)

- Estado: Diseño
- Contrato inicial del endpoint `POST /validar`
- Modelos Pydantic DTO con campos en español
- Ejemplos JSON para todos los códigos de respuesta
