# Contrato de API — VistoBueno

**Versión**: 1.1.0 (Semana 3)  
**Fecha**: 2026-09-09  
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
| `incluir_prompts_ia` | `bool` (query) | No (default: `true`) | Incluir la sección "Cómo preguntar a una IA" en la respuesta |

### Content-Type

```
multipart/form-data
```

### Tipos de archivo aceptados

| Extensión | MIME Type |
|-----------|-----------|
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |

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
    "total": 31,
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
    "reglas_evaluadas": 31,
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

```json
{
  "detail": "El archivo excede el tamaño máximo permitido (10 MB). Tamaño recibido: 15.2 MB."
}
```

### 422 Unprocessable Entity — Archivo corrupto o inválido

```json
{
  "detail": "No se pudo procesar el archivo DOCX: archivo corrupto o no es un DOCX válido."
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
| `413` | Archivo excede 10 MB |
| `415` | Tipo de archivo no soportado (no es `.docx`) |
| `422` | Solicitud mal formada (sin campo `archivo`) / Archivo corrupto o no procesable |
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

### v1.1.0 (2026-09-15 — Semana 4, nota F5)

- Sin cambios de campos en el contrato (las llamadas son idénticas).
- Fuente de reglas: la API carga `reglas_unt.yaml` (DSL, 41 reglas) desde la
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
