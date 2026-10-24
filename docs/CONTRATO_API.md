# Contrato de API — VistoBueno

**Versión**: 1.7.0 (Semana 8 — ficha de depósito y buzón de una ranura)  
**Fecha**: 2026-10-14  
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
| `depositar` | `bool` (form) | No (default: `false`) | Opt-in del operador para depositar el documento en el repositorio institucional DSpace (actividad 10). Solo se intenta con semáforo `verde`; el ítem queda en la cola de aprobación de la sede. |
| `titulo` | `string` (form) | No | Título del trabajo: metadato `dc.title` del depósito. |
| `autores` | `string` (form) | No | Autor(es), separados por `;` o saltos de línea: metadato `dc.contributor.author`. |
| `asesor` | `string` (form) | No | Asesor(a): metadato `dc.contributor.advisor`. |
| `resumen` | `string` (form) | No | Resumen: metadato `dc.description.abstract`. |
| `palabras_clave` | `string` (form) | No | Palabras clave, separadas por `;` o `,`: metadato `dc.subject`. |
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
  "deposito": {
    "estado": "sin_solicitud",
    "detalle": null
  },
  "ficha_deposito": {
    "extraidos": [
      {"campo": "dc.title", "valor": "Taller de dramatización de títeres…", "pagina": 1, "detectado": true},
      {"campo": "dc.contributor.author", "valor": ["Br. Apellido, Nombre"], "pagina": 1, "detectado": true},
      {"campo": "dc.date.issued", "valor": null, "pagina": null, "detectado": false}
    ],
    "manuales": [
      {"campo": "matricula", "valor": null},
      {"campo": "renati.author.dni", "valor": null},
      {"campo": "renati.advisor.dni", "valor": null},
      {"campo": "renati.advisor.orcid", "valor": null}
    ]
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
| `deposito.estado` | `string` | Veredicto del depósito en DSpace (ver sección "Depósito en DSpace") |
| `deposito.detalle` | `string?` | Nota de seguimiento cuando se depositó (cola de aprobación); motivo técnico cuando `"fallo"`; nota de configuración cuando `"deshabilitado"`; `null` en el resto de casos |
| `ficha_deposito` | `object?` | Ficha de depósito (v1.7.0). **Solo con semáforo `"verde"`; `null` en cualquier otro caso**. Valores detectados del DOCX listos para que el operador los corrija (ver sección "Ficha de depósito") |
| `ficha_deposito.extraidos[].campo` | `string` | Clave acordada: `dc.title`, `dc.contributor.author`, `dc.contributor.advisor`, `dc.description.abstract`, `dc.subject`, `dc.date.issued`, `escuela`, `renati.juror` |
| `ficha_deposito.extraidos[].valor` | `string \| array \| null` | Texto completo o lista de textos (autores, palabras clave); `null` si no detectado |
| `ficha_deposito.extraidos[].pagina` | `int?` | Página de origen en el DOCX, si el motor la conoce |
| `ficha_deposito.extraidos[].detectado` | `bool` | `true` si el motor encontró el elemento (publicación vía `reglas_ficha.yaml`, diseño 17; `renati.juror` viaja `false`) |
| `ficha_deposito.manuales[].campo` | `string` | Clave acordada: `matricula`, `renati.author.dni`, `renati.advisor.dni`, `renati.advisor.orcid` |
| `ficha_deposito.manuales[].valor` | `string?` | Valor tecleado por el operador en pantalla; `null` desde el servidor |
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

## Depósito en DSpace (Actividad 10)

El semáforo verde no publica nada por sí solo: el depósito en el
repositorio institucional DSpace es un **opt-in del operador** (campo
`depositar`) que solo procede cuando el documento está apto
(`semaforo: "verde"`). El resultado se expone en `deposito` con la misma
forma que `notificacion`.

El ítem NO se publica directo: entra al workflow de aprobación de DSpace
de la colección destino (las colecciones de tesis FECyC tienen flujo de
revisión), de modo que una persona de la sede queda en el circuito.

### Comportamiento

- El depósito es **opt-in por solicitud**: requiere `depositar=true` y
  semáforo `verde`. Sin `depositar`, el estado es `sin_solicitud` y jamás
  se abre una conexión al repositorio.
- Con semáforo `rojo` el estado es `no_apto`: solo se depositan documentos
  aptos para el repositorio.
- Es **best-effort**: un fallo de DSpace (conexión, credenciales,
  validación del formulario) nunca cambia el código HTTP; el fallo queda
  expuesto en `deposito.detalle` para que el operador reintente o suba el
  documento manualmente.
- Deshabilitado por defecto en el servidor: el depósito exige configuración
  completa (ver abajo); si falta algo, el estado es `deshabilitado` y el
  `detalle` lista exactamente qué variables faltan.
- Los metadatos del depósito (`titulo`, `autores`, `asesor`, `resumen`,
  `palabras_clave`) son opcionales y los completa el operador; los
  `422` del formulario de DSpace indican qué campo obligatorio falta y
  se exponen tal cual en `detalle`.

> **Alcance**: el flujo sigue el contrato REST de DSpace 7/8 (login JWT +
> par CSRF, workspaceitem, JSON Patch de metadatos, licencia, workflow) y
> está verificado contra un stub local del contrato. La validación contra
> la instancia institucional real (incluidos el nombre de la sección del
> formulario y los metadatos obligatorios) queda pendiente de la gestión
> ante la sede (ver `docs/DSPACE_API.md` §7).

### Estados de `deposito.estado`

| Estado | Significado | Sugerencia de UI (personal del repositorio) |
|--------|-------------|---------------------------------------------|
| `enviado` | DSpace aceptó el ítem; quedó en cola de aprobación de la sede | "El documento quedó en la cola de aprobación del repositorio." |
| `fallo` | Se intentó depositar y falló | Mostrar `detalle` (motivo técnico, p. ej. `422` del formulario) para corregir y reintentar |
| `sin_solicitud` | No se pidió el depósito | Ofrecer el checkbox de depósito cuando el semáforo es verde |
| `no_apto` | Se pidió, pero el semáforo no es verde | Nada que depositar: el documento aún tiene observaciones |
| `deshabilitado` | Se pidió, pero el servidor no tiene el depósito configurado | Mostrar `detalle` como nota de configuración para administradores |

### Configuración del servidor (variables de entorno)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `VISTOBUENO_DSPACE` | (vacío) | `1`/`true`/`yes` habilitan el depósito |
| `VISTOBUENO_DSPACE_URL` | (vacío) | Base de la API REST (p. ej. `https://repositorio.unitru.edu.pe/server/api`) |
| `VISTOBUENO_DSPACE_USER` | (vacío) | Cuenta de servicio con permiso de envío. **Nunca se commitea** (bloqueada por pre-commit y CI) |
| `VISTOBUENO_DSPACE_PASSWORD` | (vacío) | Contraseña de la cuenta de servicio. **Nunca se commitea** (bloqueada por pre-commit y CI) |
| `VISTOBUENO_DSPACE_COLECCION` | (vacío) | UUID de la colección destino (confirmar con la sede) |
| `VISTOBUENO_DSPACE_SECCION` | `traditionalpageone` | Sección del formulario donde viven los metadatos (configuración por instancia) |
| `VISTOBUENO_DSPACE_TIMEOUT` | `30` | Timeout por solicitud HTTP, en segundos |

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

## Ejemplo con depósito en DSpace

```bash
curl -X POST "http://localhost:8000/validar?incluir_prompts_ia=true" \
  -F "archivo=@mi_tesis.docx" \
  -F "depositar=true" \
  -F "titulo=Taller de dramatización de títeres" \
  -F "autores=Linares A, Angie Lizeth; Morales, Víctor" \
  -F "asesor=Dr. Pérez" \
  -F "resumen=El resumen del trabajo..." \
  -F "palabras_clave=títeres; preescolar"
```

Requiere semáforo `verde` y configuración completa en el servidor; si no,
la respuesta trae `deposito.estado = "no_apto"` o `"deshabilitado"` con
el motivo en `detalle`.

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

## Ficha de depósito (Semana 8, v1.7.0)

Objeto `ficha_deposito` en la respuesta de `POST /validar`, **solo con
semáforo `"verde"`** (invariante: con `"rojo"` el campo es `null` — un
documento con errores bloqueantes no se deposita y no hay nada que
pre-llenar).

### Comportamiento

- Contiene los valores que el operador necesita para el depósito:
  **extraídos** del DOCX por el motor (título, autores, asesor, resumen,
  palabras clave, año de emisión, escuela y jurado opcional) y
  **manuales** (matrícula, DNI del autor, DNI del asesor, ORCID), que
  viajan vacíos y el operador llena en pantalla.
- Los extraídos los publica el motor vía la sección DSL `extraccion`
  (`reglas_ficha.yaml`, diseño 17): 7 campos capturados sobre el mismo
  árbol del documento, sin afectar el semáforo ni el resumen.
  `renati.juror` viaja con `detectado=false` (viabilidad negativa
  documentada en el diseño 17: la sección de firmas no es confiable);
  el operador lo teclea. Un despliegue sin `reglas_ficha.yaml` responde
  la ficha completa con todos los extraídos en `detectado=false`.
- 16 campos del formulario oficial de DSpace no viajan en la ficha: el
  servidor de DSpace los pre-llena según la colección destino
  (`docs/DSPACE_API.md` §11 y `docs/PLAN_FICHA_DEPOSITO.md` §4.1).
- La SPA edita la ficha y la publica al buzón (endpoint
  `POST /ficha-pendiente`) para que el userscript la lea y rellene el
  formulario oficial. Ver la sección siguiente.

## Buzón de una ranura (comunicación con el userscript)

Mecanismo de intercambio entre la SPA y el userscript que corre sobre
las páginas de DSpace en el navegador del operador. Sin archivos, sin
pegar, sin sesiones: **una ranura en memoria del proceso, TTL de 1 hora,
"última gana"**. Supuesto documentado: un operador, una tesis en vuelo.

### Endpoints

| Endpoint | Método | Quién llama | Qué hace |
|----------|--------|-------------|----------|
| `/ficha-pendiente` | `POST` (204) | la SPA | Publica la ficha completada (reemplaza la anterior) |
| `/ficha-pendiente` | `GET` → `FichaDeposito` | el userscript | Lee la ficha a rellenar; `404` si vacía o expirada |
| `/deposito` | `POST` (204) | el userscript | Reporta `{handle, titulo, timestamp}` del ítem archivado |
| `/deposito` | `GET` → `DepositoRecibido` | la SPA | Sondea el reporte; `404` si vacío o expirado |

- `DepositoRecibido.handle`: URI del ítem (`https://hdl.handle.net/…`).
- `DepositoRecibido.titulo`: la SPA lo **coteja con la ficha en vuelo**
  antes de usar el handle (defensa contra un handle ajeno).
- `DepositoRecibido.timestamp`: momento del clic en "Depositar"
  capturado por el userscript (ISO 8601); alimenta la columna HORA del
  registro y la constancia.

### Seguridad

- **El buzón no emite cabeceras CORS** (invariante con test): una página
  web cualquiera del navegador del operador no puede leer la ficha, que
  contiene datos personales del estudiante. El userscript lo lee por
  `GM_xmlhttpRequest`, que corre en el contexto de la extensión.
- Peor caso de un `POST` ciego desde una página maliciosa: basura
  visible en el botón/toast del userscript, recuperable publicando de
  nuevo. No hay ruta de exfiltración.
- El buzón es la única pieza de estado del servidor: un reinicio del
  proceso lo vacía (el operador re-valida y re-prepara).

## Constancia de depósito (Semana 8, v1.7.0)

Los dos endpoints que producen el papeleo del registro a partir de la
ficha completada y del reporte del buzón. Entrada común
(`FilaRegistroRequest`): la `ficha` (extraídos corregidos + manuales
llenos), el `handle` del ítem y el `timestamp` del clic en Depositar
(ISO 8601; alimenta DD/MM/AA, HORA, AÑO y la fecha del documento).

**Convención por autor** (evidencia del registro oficial): una fila y
una constancia POR ESTUDIANTE. `matricula` y `renati.author.dni`
aceptan una lista alineada por posición con los autores; las tesis con
dos autores generan dos constancias y dos filas con el mismo handle.

### `POST /constancia` → descarga binaria (o paquete zip)

- Cuerpo: `FilaRegistroRequest` + `indice_autor` (`int`, 0-based).
- Respuesta 200: el `.docx` del Modelo B con los 11 MERGEFIELD
  reemplazados por texto plano (título, autor, matrícula, fecha, hora,
  handle, escuela, fecha del documento). La plantilla oficial vive en
  `recursos/` (ruta configurable por
  `VISTOBUENO_PLANTILLA_CONSTANCIA`); se llena en copia.
- **`?formato=zip`** (revisión del PR #55: "la constancia podría
  incluirlo"): un paquete por autor con la constancia .docx y SU fila
  del registro como `registro.csv` (BOM UTF-8, separador `;`). Una
  descarga = todo el papeleo del estudiante.
- 422: timestamp inválido, falta un dato de la ficha (título, autores,
  matrículas alineadas) o `indice_autor` fuera de rango.
- 500: configuración del servidor — `VISTOBUENO_FIRMA` (columna FIRMA)
  o plantilla ausente; el `detail` nombra exactamente qué falta.

### `POST /fila-registro` → `{"filas": […]}` o archivo descargable

- Por defecto (`formato=json`, retrocompatible): una fila TSV por autor,
  en el orden exacto de columnas del registro oficial: N°, TESIS/TSP,
  BACHILLER/LICENCIADO, N° MATRIC., DD, MM, AA, HORA, DIRECCION URL,
  FIRMA, FECHA DEL DOC., ESCUELAS, AÑO.
- `?formato=tsv|csv|xlsx` (hallazgo 11 de la revisión del PR #55):
  devuelve un **archivo descargable** listo para abrir en
  Excel/LibreOffice — elimina los errores de pegado (encoding, tabs
  perdidos, columnas desalineadas):
  - `tsv`: `text/tab-separated-values` con BOM UTF-8.
  - `csv`: `text/csv` con BOM UTF-8, separador `;` (regional español)
    y citas RFC 4180 para los campos que contienen `;`.
  - `xlsx`: libro de una hoja con la fila de encabezado
    (`COLUMNAS_REGISTRO`, 13 columnas).
- La columna N° va vacía: la numeración pertenece al registro de la
  biblioteca. DD y MM llevan barra final ("20/", "01/") y HORA va en
  24 h, igual que las celdas existentes.
- La app JAMÁS escribe el XLSX oficial: el operador pega la fila o
  copia las celdas del archivo descargado.

## Changelog

### v1.7.0 (2026-10-19 — Semana 8: ficha de depósito y buzón)

Ficha de depósito y mecanismo de comunicación con el userscript que
rellena el formulario oficial de DSpace. Cambio aditivo: ningún campo
existente desaparece ni cambia de tipo.

- **Nuevo objeto `ficha_deposito` en la respuesta** (`null` salvo con
  semáforo `verde`): `extraidos` (8 claves acordadas con el motor) +
  `manuales` (4 claves que el operador llena en pantalla; `matricula` y
  `renati.author.dni` aceptan lista alineada por autor). Los extraídos
  los publica el motor (`reglas_ficha.yaml`, diseño 17, entrega de
  Int3): 7 campos capturados; `renati.juror` viaja `detectado=false`
  (viabilidad negativa documentada).
- **Nuevos endpoints del buzón**: `POST/GET /ficha-pendiente` y
  `POST/GET /deposito` (una ranura, TTL de 1 hora, "última gana").
- **Nuevos endpoints del papeleo**: `POST /constancia` (descarga del
  Modelo B lleno, una por autor, índice 0-based) y `POST /fila-registro`
  (filas TSV en el orden de columnas del registro; con `?formato=tsv |
  csv | xlsx` devuelve un archivo descargable — revisión del PR #55,
  hallazgo 11). Configuran `VISTOBUENO_FIRMA` y opcionalmente
  `VISTOBUENO_PLANTILLA_CONSTANCIA`.
- **Ensayo general de un comando** (revisión del PR #55, hallazgo 10):
  `nix run .#test-ficha-deposito` corre el flujo completo contra el mock
  de DSpace y verifica el papeleo de punta a punta.
- **Invariante de seguridad**: el buzón no emite cabeceras CORS (con
  test que lo protege contra regresiones).
- Contexto y decisiones: `docs/PLAN_FICHA_DEPOSITO.md` (v0.2, congelado);
  hallazgos del formulario real en `docs/DSPACE_API.md` §11.
- `docs/openapi_spec.json` regenerado (el CI verifica el drift).

### v1.6.0 (2026-10-14 — Semana 7, actividad 10: depósito en DSpace)

Exposición del depósito en el repositorio institucional como opt-in del
operador. Cambio aditivo: ningún campo desaparece ni cambia de tipo.

- **Nuevo campo de formulario `depositar`** (`bool`, default `false`):
  opt-in del operador para depositar el documento validado en DSpace.
  Solo se intenta con semáforo `verde`; el ítem entra a la cola de
  aprobación de la sede (workflow de DSpace), nunca se publica directo.
- **Nuevos campos de formulario opcionales de metadatos**: `titulo`,
  `autores` (separados por `;` o saltos de línea), `asesor`, `resumen` y
  `palabras_clave` (separadas por `;` o `,`). Se envían como metadatos
  Dublin Core del ítem (`dc.title`, `dc.contributor.author`,
  `dc.contributor.advisor`, `dc.description.abstract`, `dc.subject`).
- **Nuevo objeto `deposito` en la respuesta** (`estado` + `detalle`),
  misma forma que `notificacion`. Estados: `enviado | fallo |
  sin_solicitud | no_apto | deshabilitado`, con sugerencias de UI en la
  sección "Depósito en DSpace".
- **Best-effort total**: un fallo del depósito (conexión, credenciales,
  `422` del formulario) nunca cambia el código HTTP; el motivo técnico
  viaja en `deposito.detalle` para el personal del repositorio.
- **Escáner de secretos ampliado** (pre-commit + CI): cubre
  `VISTOBUENO_DSPACE_PASSWORD` y `VISTOBUENO_DSPACE_USER`.
- `docs/openapi_spec.json` regenerado (el CI verifica el drift).
- Versión del endpoint: `1.5.0` → `1.6.0`.

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
