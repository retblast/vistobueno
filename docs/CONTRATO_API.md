# Contrato de API — VistoBueno

**Versión**: 1.5.0 (Semana 7 — revisión integrada B3/B4)  
**Fecha**: 2026-10-09  
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
| `correo` | `string` (form) | No | Correo electrónico del estudiante. Si se envía, debe tener formato válido (`usuario@dominio`); es el destinatario del correo de observaciones cuando el operador lo solicita (campo `notificar`). Cadena vacía se trata como ausente. |
| `notificar` | `bool` (form) | No (default: `false`) | Opt-in del operador para enviar el correo de observaciones al estudiante. El envío solo se intenta si además hay `correo` válido y semáforo `rojo`. |
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
  "notificacion": {
    "estado": "sin_correo",
    "detalle": null
  },
  "resumen": {
    "total": 49,
    "total_evaluadas": 43,
    "reglas_no_aplicables": 6,
    "fallidos_error": 0,
    "fallidos_warning": 2
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
      "cita": "\"Tamaño A4/papel (210x297 cm)\"",
      "aplicable": true
    },
    {
      "rule_id": "estructura_tinv_cualitativo",
      "paso": true,
      "severidad": "error",
      "mensaje": "Estructura obligatoria del Trabajo de Investigación (Cualitativo)",
      "esperado": "secciones obligatorias del esquema cualitativo",
      "encontrado": "no aplica a este documento",
      "ubicacion": "Esquema del Trabajo de Investigación Cualitativo (párr. 380-420)",
      "fuente": "MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx",
      "cita": "Esquema enumerado en párr. 381-420 del manual",
      "aplicable": false
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
    "reglas_evaluadas": 43,
    "reglas_totales": 49,
    "version_esquema": "2026-09-01",
    "tipo_documento_declarado": null,
    "tipo_documento_inferido": "tinv_cuantitativo",
    "tipo_documento_estado": "vigente"
  }
}
```

> **Nota sobre los conteos**: el ejemplo muestra un plan cuantitativo conforme,
> donde las 6 reglas de otros tipos de documento no aplican. Por eso
> `total` (49) ≠ `total_evaluadas` (43) y `reglas_no_aplicables` = 6.

### Descripción de campos de respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `semaforo` | `string` | `"verde"` si todas las reglas de severidad `error` pasan; `"rojo"` si alguna falla |
| `notificacion.estado` | `string` | Veredicto del envío del correo de observaciones (ver sección siguiente) |
| `notificacion.detalle` | `string?` | Motivo técnico cuando `estado` es `"fallo"`; nota de configuración cuando es `"deshabilitado"`; `null` en el resto de casos |
| `resumen.total` | `int` | Total de reglas presentes en el YAML de reglas |
| `resumen.total_evaluadas` | `int` | Reglas realmente evaluadas sobre el documento |
| `resumen.reglas_no_aplicables` | `int` | Reglas omitidas porque no aplican al tipo de documento detectado |
| `resumen.fallidos_error` | `int` | Reglas con severidad `error` que no pasaron |
| `resumen.fallidos_warning` | `int` | Reglas con severidad `warning` que no pasaron |
| `resultados` | `array` | Lista de resultados individuales por regla. Incluye las no aplicables, distinguibles por `aplicable=false` |
| `resultados[].rule_id` | `string` | Identificador único de la regla |
| `resultados[].paso` | `bool` | `true` si la regla se cumplió. En una regla no aplicable vale `true` porque no falló: no se evaluó |
| `resultados[].severidad` | `string` | `"error"` o `"warning"` |
| `resultados[].mensaje` | `string` | Descripción de la regla en lenguaje natural |
| `resultados[].esperado` | `string` | Valor esperado según el reglamento |
| `resultados[].encontrado` | `string` | Lo que encontró el validador (`"cumple"` si pasó; `"no aplica a este documento"` si no aplicó) |
| `resultados[].ubicacion` | `string?` | Referencia al documento del reglamento |
| `resultados[].fuente` | `string` | Archivo fuente del que se extrajo la regla |
| `resultados[].cita` | `string` | Cita textual del reglamento |
| `resultados[].aplicable` | `bool` | `true` si la regla se evaluó. `false` = la regla no aplica al tipo de documento (p. ej. la estructura de otro tipo de tesis) |
| `como_preguntar_a_una_ia` | `array` | Bloques de prompts listos para copiar/pegar en una IA |
| `como_preguntar_a_una_ia[].rule_id` | `string` | ID de la regla fallida |
| `como_preguntar_a_una_ia[].prompt` | `string` | Prompt completo en español |
| `metadatos.archivo_nombre` | `string` | Nombre original del archivo subido |
| `metadatos.archivo_tamano_bytes` | `int` | Tamaño en bytes del archivo |
| `metadatos.reglas_evaluadas` | `int` | Reglas realmente ejecutadas (= `resumen.total_evaluadas`) |
| `metadatos.reglas_totales` | `int` | Total de reglas presentes en el YAML (= `resumen.total`) |
| `metadatos.version_esquema` | `string` | Versión del esquema YAML de reglas |
| `metadatos.tipo_documento_declarado` | `string?` | Tipo declarado en el Anexo 10 del documento; `null` si no declaró |
| `metadatos.tipo_documento_inferido` | `string?` | Tipo deducido de las firmas estructurales; `null` si no se pudo inferir |
| `metadatos.tipo_documento_estado` | `string` | `"vigente"`, `"sin_determinar"` o `"contradictorio"` |

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

## Notificación de observaciones por correo (Actividad 6)

La herramienta es de **uso interno** (personal del repositorio): el correo
se envía al **estudiante**, pero quien opera la validación y decide el envío
es el personal del repositorio.

### Comportamiento

- El envío es **opt-in por solicitud**: requiere `notificar=true`,
  un `correo` válido y semáforo `rojo`. Sin `notificar`, jamás se abre una
  conexión SMTP (el estado es `no_solicitado`).
- Es **best-effort**: un fallo de SMTP (conexión rechazada, credenciales,
  timeout) nunca cambia el código HTTP de la respuesta; el fallo queda
  expuesto en `notificacion.detalle` para que el operador reintente o envíe
  el correo manualmente.
- Deshabilitado por defecto en el servidor: el envío además exige que la
  configuración SMTP esté presente (ver abajo).

### Estados de `notificacion.estado`

| Estado | Significado | Sugerencia de UI (personal del repositorio) |
|--------|-------------|---------------------------------------------|
| `enviado` | El servidor SMTP aceptó el correo | "Enviamos las observaciones al correo del estudiante." |
| `fallo` | Se intentó enviar y falló | Mostrar `detalle` (motivo técnico) para reintentar o enviar manualmente |
| `no_solicitado` | Había correo, pero no se pidió el envío | Ofrecer el checkbox de envío |
| `sin_correo` | No se envió `correo` (aunque haya `notificar`) | Pedir el correo del estudiante |
| `sin_observaciones` | Se pidió el envío, pero el semáforo no es `rojo` | Nada que notificar |
| `deshabilitado` | Se pidió el envío, pero el servidor no tiene la notificación habilitada | Mostrar `detalle` como nota de configuración para administradores |

### Configuración del servidor (variables de entorno)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `VISTOBUENO_NOTIFICACIONES` | (vacío) | `1`/`true`/`yes` habilitan el envío (mismo criterio que `VISTOBUENO_SMTP_STARTTLS`) |
| `VISTOBUENO_SMTP_HOST` | (vacío) | Servidor SMTP institucional |
| `VISTOBUENO_SMTP_PORT` | `587` | Puerto SMTP |
| `VISTOBUENO_SMTP_USER` | (vacío) | Usuario SMTP (vacío = sin autenticación) |
| `VISTOBUENO_SMTP_PASSWORD` | (vacío) | Contraseña SMTP. **Nunca se commitea** (bloqueada por pre-commit y CI) |
| `VISTOBUENO_SMTP_STARTTLS` | `true` | Negociar STARTTLS tras conectar |
| `VISTOBUENO_CORREO_REMITENTE` | `no-responder@unitru.edu.pe` | Buzón institucional que figura como From |

El correo incluye una tabla HTML con las observaciones (severidad,
mensaje, valores esperado/encontrado, referencia normativa y `rule_id`),
una versión en texto plano y encabezados `Date`/`Message-ID` exigidos por
los servidores reales.

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
  -F "correo=estudiante@unitru.edu.pe" \
  -F "notificar=true"
```

Sin `notificar=true` el correo **no** se envía: la respuesta devolvería
`notificacion.estado = "no_solicitado"`.

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
| `RuleResult.aplicable` | `resultados[].aplicable` | Sin cambio de nombre; `false` = regla omitida por tipo de documento |
| `build_report()["semaforo"]` | `semaforo` | Sin cambio |
| `build_report()["resumen"]` | `resumen` | Mapeado campo a campo (incluye `total_evaluadas` y `reglas_no_aplicables`) |
| `build_report()["resultados"]` | `resultados` | Mapeado a DTO (la API envía TODOS los resultados, también los no aplicables) |
| `build_ai_help_section()` | `como_preguntar_a_una_ia` | Solo si `incluir_prompts_ia=true` |
| regla `deteccion_tipo_documento` (su `found`) | `metadatos.tipo_documento_declarado/inferido/estado` | Derivado por la API de la salida de la regla de detección |
| — | `metadatos` | Agregado por la API: nombre, tamaño, conteos, tipo de documento y versión del esquema |

---

## Changelog

### v1.5.0 (2026-10-09 — Semana 7, revisión integrada, hallazgos B3/B4)

Endurecimiento del flujo de notificación tras la auditoría de la Semana 7.
Cambio aditivo: ningún campo desaparece ni cambia de tipo.

- **`notificacion.detalle` ahora también se llena con `estado` `"deshabilitado"`**
  (hallazgo B3): nota de configuración que indica cómo habilitar el
  servidor (`VISTOBUENO_NOTIFICACIONES=1` y `VISTOBUENO_SMTP_HOST`). Antes
  el estado `deshabilitado` era el default real del servidor pero la
  respuesta no traía ningún dato: "casilla marcada → 200 OK → nada" era
  indistinguible de un envío silencioso.
- **`VISTOBUENO_NOTIFICACIONES` acepta `1`/`true`/`yes`** (hallazgo B4),
  igual que `VISTOBUENO_SMTP_STARTTLS`. Antes solo aceptaba el literal
  `1`: poner `true` dejaba el envío apagado sin error visible.
- **Best-effort total en el envío** (hallazgo B5, sin cambio de contrato):
  la plantilla y las cabeceras del correo se arman dentro del manejo de
  errores; ningún fallo del armado (p. ej. CR/LF en el nombre del archivo)
  puede romper la respuesta HTTP. El nombre se sanitiza en el Subject
  para impedir inyección de cabeceras.
- `docs/openapi_spec.json` regenerado (el CI verifica el drift).
- Versión del endpoint: `1.4.0` → `1.5.0`.

### v1.4.0 (2026-10-09 — Semana 7, paso 7 del plan de tipo de documento)

Refleja en el contrato los cambios del motor (pasos 1–6 del
`docs/PLAN_TIPO_DOCUMENTO.md`): aplicabilidad por tipo de documento y
detección del tipo. Antes de esta versión, una regla no aplicable salía
con `paso=true`, idéntica a una regla que pasó de verdad, y
`metadatos.reglas_evaluadas` reportaba el total del YAML (48) aunque solo
se evaluaran 46.

- **Nuevo campo `resultados[].aplicable`** (`bool`, default `true`):
  `false` marca reglas que no aplican al tipo de documento detectado
  (hoy, las estructuras de los otros tipos de tesis). No se excluyen de
  la respuesta: el frontend puede distinguir "aprobada" de "omitida".
- **Nuevos campos requeridos en `resumen`**: `total_evaluadas` y
  `reglas_no_aplicables`. `resumen.total` pasa a significar "reglas
  presentes en el YAML".
- **Cambio de semántica en `metadatos.reglas_evaluadas` (breaking)**:
  ahora vale las reglas realmente ejecutadas (p. ej. 46 para un plan
  cuantitativo), no el total del YAML. El nuevo campo
  `metadatos.reglas_totales` conserva el total (48).
- **Nuevos metadatos de tipo de documento** (derivados de la regla
  `deteccion_tipo_documento`): `tipo_documento_declarado`,
  `tipo_documento_inferido` y `tipo_documento_estado`
  (`vigente | sin_determinar | contradictorio`), para que el frontend no
  parsee texto libre.
- `docs/openapi_spec.json` regenerado (el CI verifica el drift).
- Versión del endpoint: `1.3.0` → `1.4.0`. **No es un cambio puramente
  aditivo**: `reglas_evaluadas` cambia de valor y `resumen`/`metadatos`
  ganan campos requeridos. El frontend actual no se rompe (sigue
  leyendo `resumen.total`, `paso` y `severidad`, que se conservan), pero
  los clientes que validen la forma del JSON de forma estricta deben
  actualizarse.

### v1.3.0 (2026-09-30 — Semana 5, Actividad 6)

- **Nuevo campo opcional `notificar`** (form, default `false`): opt-in del
  operador para el envío del correo de observaciones. Sin él no se abre
  conexión SMTP.
- **Nuevo campo en la respuesta `notificacion`**: `{estado, detalle}` con
  estados `enviado | fallo | no_solicitado | sin_correo | sin_observaciones
  | deshabilitado`. Con `fallo`, `detalle` expone el motivo técnico.
- **Envío best-effort cableado al flujo de validación**: requiere
  `notificar=true` + `correo` válido + semáforo `rojo` + notificaciones
  habilitadas en el servidor; un fallo SMTP jamás cambia el código HTTP.
- Nueva sección de documentación del comportamiento y de la configuración
  SMTP por variables de entorno.
- Ejemplo `curl` con `correo` + `notificar`.
- Versión del endpoint: `1.2.0` → `1.3.0` (cambio aditivo; el frontend
  existente no se rompe: `notificacion` tiene valor por defecto).

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
- Ejemplos de respuesta sincronizados a 48 reglas (antes decían 31).
- Versión del endpoint: `1.1.0` → `1.2.0` (cambio aditivo, sin romper
  clientes existentes).

### v1.1.1 (2026-09-15 — Semana 4, nota F5)

- Sin cambios de campos en el contrato (las llamadas son idénticas).
- Fuente de reglas: la API carga `reglas_unt.yaml` (DSL, 48 reglas) desde la
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
