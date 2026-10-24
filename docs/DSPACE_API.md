# API REST de DSpace — Instancia institucional UNT

**Versión**: 1.0 (análisis)  
**Fecha**: 2026-09-30  
**Estado**: Análisis (Actividad 9 del plan de prácticas — producto: registro técnico
de la API de DSpace con endpoints, autenticación y flujo de depósito)  
**Actividad siguiente**: Actividad 10 (implementación del módulo de depósito)

> Todos los datos de la instancia fueron verificados empíricamente el
> 2026-09-30 contra el repositorio en producción (ver §9 "Cómo reproducir
> este análisis"). Los puntos que requieren gestión ante la sede están
> marcados como **PENDIENTE**.

---

## 1. Instancia institucional

| Dato | Valor |
|------|-------|
| Repositorio | Repositorio Universidad Nacional de Trujillo |
| URL | https://repositorio.unitru.edu.pe |
| Base de la API | https://repositorio.unitru.edu.pe/server/api |
| **Versión de DSpace** | **8.1** (`GET /server/api` → `dspaceVersion`) |
| UI | Angular (DSpace 7/8) |
| Comunidad FECyC | "Educación y Ciencias de la Comunicación" — UUID `9f93d7e9-ad18-4cc7-9472-7ee47fbbfe8f`, handle [20.500.14414/861](https://hdl.handle.net/20.500.14414/861), 2365 ítems |

DSpace 8 mantiene el contrato REST de la serie 7 (`DSpace/RestContract`):
autenticación JWT, HATEOAS (`_links`/`_embedded`), metadatos como mapa
clave→lista y depósito vía `workspaceitems`.

---

## 2. Acceso a la API

### 2.1 Barrera de protección (BunkerWeb) — restricción operativa

El sitio (incluida la ruta `/server/api`) está detrás de BunkerWeb con
detección de bots: la primera solicitud recibe un `302 → /challenge`
que ejecuta un **proof-of-work SHA-256 en JavaScript** y, tras resolverlo,
establece una cookie y redirige de vuelta. Un navegador real pasa en
segundos; un cliente HTTP programático NO (curl recibe el `302` aunque
envíe las cookies de la sesión).

**Implicancia para el módulo de depósito (Actividad 10):** el cliente
programático no debe resolver el desafío en producción. ~~Se requiere una
**excepción de la sede**~~ **CANCELADO (2026-10-19)**: el depósito en esta
instancia se hace con el userscript sobre la sesión del operador; la ruta
REST queda como condición de activación (`PLAN_FICHA_DEPOSITO.md` §9.2).
Re-verificado el 2026-10-19: el `302 → /challenge` persiste incluso con
User-Agent de navegador y sin cookies previas.

Para trabajo exploratorio sin navegador, se usó Chrome headless (ver §9).

### 2.2 Autenticación (JWT + CSRF)

La API usa JWT (RFC 7519). El login es `POST` con
`application/x-www-form-urlencoded` y exige el par CSRF de DSpace
(cookie `DSPACE-XSRF-COOKIE` + header `X-XSRF-TOKEN`), que se obtiene de
cualquier llamada previa a la API:

```bash
# 0) Obtener el par CSRF (la API lo entrega en las cookies de cualquier GET)
curl -c cookies.txt -b cookies.txt \
  "https://repositorio.unitru.edu.pe/server/api/authn/status"

# 1) Login (el header X-XSRF-TOKEN debe llevar el valor de la cookie)
curl -c cookies.txt -b cookies.txt \
  -X POST "https://repositorio.unitru.edu.pe/server/api/authn/login" \
  --data "user=USUARIO&password=CLAVE" \
  -H "X-XSRF-TOKEN: <valor-de-DSPACE-XSRF-COOKIE>" \
  -D -   # el JWT llega en el header Authorization: Bearer eyJ...

# 2) Todas las llamadas posteriores llevan el JWT
curl -H "Authorization: Bearer eyJhbG..." \
  "https://repositorio.unitru.edu.pe/server/api/authn/status"
```

- `GET /server/api/authn/status` responde `{"okay": true, "authenticated": ...}`
  y permite verificar el token sin efectos secundarios.
- Vigencia del token: ~30 min (configurable). Se refresca reenviando el
  login `POST` con solo el header `Authorization: Bearer ...`.
- `POST /server/api/authn/logout` invalida el JWT del lado del servidor.
- Los métodos disponibles (password / Shibboleth / etc.) se anuncian en el
  header `WWW-Authenticate` de un `401`. **PENDIENTE**: confirmar con la
  cuenta de servicio qué método aplica.

### 2.3 Formato de las respuestas

HATEOAS (HAL+JSON): todo recurso trae `_links` y `_embedded`. El paginado
usa los parámetros `page`, `size` (y `embed` para traer subrecursos, p. ej.
`?embed=metadata`). El límite por página lo configura el servidor.

---

## 3. Modelo de metadatos

Los metadatos son un **mapa clave→lista ordenada** de valores. La clave es
el campo con separador de punto (`dc.title`, `thesis.degree.name`, ...):

```json
{
  "dc.title": [ { "value": "...", "language": null, "authority": null, "confidence": -1, "place": 0 } ],
  "dc.contributor.author": [ { "value": "...", "language": null, "authority": null, "confidence": -1, "place": 0 } ]
}
```

- `value`: el texto del metadato.
- `language`: código ISO (p. ej. `es`, `en_US`) o `null`.
- `authority`/`confidence`: clave de autoridad (vocabularios controlados) y
  su nivel de confianza; `-1` si no aplica.
- `place`: orden del valor dentro de la clave.

Durante el envío, los metadatos se editan con **JSON Patch (RFC 6902)** sobre
la sección del formulario (ver §4).

---

## 4. Flujo de depósito (submission)

1. **Crear el WorkspaceItem** (el "envío en progreso"). Requiere la colección
   destino; opcionalmente sube el archivo en el mismo POST (multipart):

   ```
   POST /server/api/submission/workspaceitems?owningCollection=<uuid>
   ```

   La respuesta trae el `id` del WorkspaceItem y la lista de `sections`
   disponibles. **Conservar el `id`**: es el identificador de todo el resto
   del flujo.

2. **Completar las secciones.** Cada `section` tiene un `sectionType`
   visible en `GET /server/api/config/submissionsections`:

   | sectionType | Uso | Interacción |
   |-------------|-----|-------------|
   | `submission-form` | Metadatos | JSON Patch sobre `/sections/<sección>/<metadato>` |
   | `upload` | Archivos (bitstreams) | `POST` multipart del archivo a la sección |
   | `license` | Aceptación de licencia | `POST` de aceptación |
   | `access` | Embargo / derechos | Opcional |

   Ejemplo de escritura de metadatos (JSON Patch):

   ```bash
   curl -X PATCH \
     "https://repositorio.unitru.edu.pe/server/api/submission/workspaceitems/<id>" \
     -H "Authorization: Bearer eyJ..." \
     -H "Content-Type: application/json" \
     --data '[
       {"op": "add", "path": "/sections/traditionalpageone/dc.title",
        "value": [{"value": "Título de la tesis"}]}
     ]'
   ```

   Nota: para **inicializar** un metadato el `add` recibe la lista completa de
   valores; el path con `/-` solo agrega a listas ya inicializadas.

3. **Depositar**: `POST` del WorkspaceItem a `POST /server/api/workflow/workflowitems`.

   - Si la colección **no** tiene flujo de aprobación → el ítem se publica
     de inmediato (mismo UUID).
   - Si la colección **sí** tiene flujo (roles reviewer/editor/finaleditor) →
     queda como WorkflowItem a la espera de revisión humana.

   En las colecciones de tesis FECyC la respuesta expone grupos de rol
   `reviewer`, `editor` y `finaleditor`, lo que indica flujo de aprobación
   configurado: **el depósito desde VistoBueno quedaría en cola de revisión**,
   lo que mantiene a una persona de la sede en el circuito (deseable).

4. **Errores**: la API responde `401/403` (auth/permisos), `400` (payload),
   `422` (validación del formulario; p. ej. metadato obligatorio faltante).
   Los `422` de sección indican exactamente qué campo falla.

**Secciones confirmadas (captura del 2026-10-19, ver §11)**: el envío tiene
tres secciones — `traditionalPeruOne` (metadatos; el formulario típico
`traditionalpageone` NO aplica en esta instancia), `upload` (bitstreams) y
`license` (aceptación de la licencia de distribución: un checkbox
"Confirmo la licencia", no una subida de archivo). El payload de la
aceptación de licencia y del POST al workflow no se capturaron (el
operador no llegó a depositar); solo interesan a la ruta REST aparcada
(`PLAN_FICHA_DEPOSITO.md` §9.2).

---

## 5. Colecciones de tesis de la FECyC

Comunidad: "Educación y Ciencias de la Comunicación"
(`9f93d7e9-ad18-4cc7-9472-7ee47fbbfe8f`, 2365 ítems). Colecciones de tesis:

| Colección | UUID | Handle | Ítems |
|-----------|------|--------|-------|
| Tesis de Ciencias de la Comunicación | `d26aecbf-f733-4682-9fbd-1174e944f2c3` | 20.500.14414/887 | 135 |
| **Tesis de Educación Inicial** | `8d575820-ab89-43e0-abeb-33ee14b912c8` | 20.500.14414/884 | 455 |
| Tesis de Educación Primaria | `4a88b41d-5295-4145-900b-70768f66f12a` | 20.500.14414/885 | 789 |
| T. de Ed. Secundaria Mención: Ciencias Matemáticas | `87e6643d-4623-47b4-851b-220d7717abb9` | 20.500.14414/7796 | 129 |
| T. de Ed. Secundaria Mención: C. Naturales (Física, Química y Biología) | `35f1c421-c5ee-4d1f-9658-1b2776975501` | 20.500.14414/7795 | 46 |
| T. de Ed. Secundaria Mención: Filosofía, Psicología y C.C.S.S. | `d3b4caaf-08f0-4a1c-9ac5-c6d6f6190b05` | 20.500.14414/7801 | 145 |
| T. de Ed. Secundaria Mención: Historia y Geografía | `67f22b33-bde5-49df-a72b-8b263ffa82fc` | 20.500.14414/886 | 120 |
| T. de Ed. Secundaria Mención: Idiomas: Inglés - Alemán | `26395d1e-65e4-4fee-ac3f-dedd2ca8259f` | 20.500.14414/7798 | 36 |
| T. de Ed. Secundaria Mención: Idiomas: Inglés - Francés | `ed0fc4de-0399-4661-b59f-fd34aca24515` | 20.500.14414/7797 | 64 |
| T. de Ed. Secundaria Mención: Lengua y Literatura | `318cdc2f-83fc-4555-9d86-c3142002fe5b` | 20.500.14414/7799 | 240 |
| Tesis de Segunda Especialidad en Estimulación Temprana | `f717c60a-7b05-470b-8a80-5b34bae8ed80` | 20.500.14414/12318 | 77 |
| Tesis de Segunda Especialidad en Tecnología Educativa | `13daeb1e-4a70-4c09-b639-f617cee972e4` | 20.500.14414/12317 | 129 |

En negrita la colección piloto sugerida: "Tesis de Educación Inicial"
(programa de la plantilla de pruebas del proyecto,
`recursos/EDUCACION INICIAL-PLANTILLA INVESTIGACIÓN CUANTITATIVA.docx`).
**PENDIENTE (Salcedo)**: confirmar la(s) colección(es) destino del
depósito automático.

---

## 6. Metadatos observados en tesis FECyC

Extraídos de un ítem archivado en "Tesis de Educación Inicial" (la
consulta es pública vía `GET /server/api/discover/search/objects?...&embed=metadata`):

| Campo DSpace | Contenido | Fuente candidata en VistoBueno |
|--------------|-----------|-------------------------------|
| `dc.title` | Título de la tesis | Carátula (regla `caratula_titulo_trabajo`) |
| `dc.contributor.author` | Autor(es) | Carátula (regla `caratula_autor`) |
| `dc.contributor.advisor` | Asesor(a) | Carátula (regla de asesor) |
| `dc.description.abstract` | Resumen | Cuerpo del documento |
| `dc.subject` | Palabras clave | Resumen / carátula |
| `dc.subject.ocde` | Categoría OCDE | **PENDIENTE**: catalogación (posiblemente manual) |
| `dc.date.issued` | Fecha | Fecha del documento |
| `dc.publisher` | Editorial (UNT) | Constante de configuración |
| `dc.publisher.country` | País (PE) | Constante de configuración |
| `dc.language.iso` | Idioma (es) | Constante / detección del documento |
| `dc.type` | Tipo (Thesis/Bachelor) | Constante por colección |
| `dc.type.version` | Versión (accepted/published) | Configuración |
| `thesis.degree.name` | Grado (Título Profesional) | Constante por colección |
| `thesis.degree.level` | Nivel (Pregrado) | Constante por colección |
| `thesis.degree.discipline` | Programa | Colección destino |
| `thesis.degree.grantor` | Institución (UNT) | Constante de configuración |
| `dc.rights` / `dc.rights.uri` | Licencia | Configuración / licencia del formulario |
| `dc.relation.ispartofseries` | Serie (programa) | Constante por colección |
| `dc.identifier.uri` / `dc.description.uri` | URI | Los asigna DSpace |
| `dc.date.accessioned` / `dc.date.available` | Fechas de acceso | Los asigna DSpace |

El mapeo detallado (qué campos son obligatorios en el formulario de la
instancia) se completa en la Actividad 10 con el primer login.

---

## 7. Preguntas abiertas (gestión ante la sede)

1. **Cuenta de servicio** — **YA NO REQUERIDA** para este despliegue
   (2026-10-19): el depósito usa la sesión del operador. Queda como
   requisito de la ruta REST aparcada (`PLAN_FICHA_DEPOSITO.md` §9.2);
   las credenciales se inyectan por variables de entorno, nunca viven en
   el repositorio.
2. **Excepción BunkerWeb** — **CANCELADA** para este despliegue, por la
   misma razón. El re-probe del 2026-10-19 confirma el `302` para
   clientes programáticos.
3. **Política de depósito**: las colecciones destino son las de tesis
   FECyC (§5); el operador elige en el flujo oficial como siempre. El
   flujo aprobado mantiene a la persona de la sede en el circuito
   (aprueba el workflow, firma la constancia).
4. **Método de autenticación** — **CONFIRMADO password**: la captura del
   2026-10-19 incluye el login `POST /authn/login` con
   `user`/`password` form-urlencoded; la UI de login es el formulario
   estándar de DSpace (email + contraseña).
5. **Secciones del formulario** — **CONFIRMADO** `traditionalPeruOne` +
   `upload` + `license` (§4 y §11).

---

## 8. Decisiones de diseño anticipadas (para la Actividad 10)

- **Módulo**: `validator/dspace.py` en la capa API, con el mismo patrón que
  `notificacion.py`: configuración exclusivamente por variables de entorno
  (`VISTOBUENO_DSPACE_*`), deshabilitado por defecto, `ResultadoDeposito`
  con estado + detalle, jamás rompe la respuesta HTTP.
- **Opt-in**: depósito explícito del operador (campo de formulario), análogo
  a `notificar`; solo con semáforo `"verde"` (documento apto para entrega).
- **Flujo**: login JWT → workspaceitem en la colección destino → metadata
  (JSON Patch) → bitstream (el .docx validado) → licencia → depositar.
  El ítem queda en cola de aprobación de la sede.
- **Cliente HTTP**: reutilizar `httpx` (ya presente para tests) en lugar de
  stdlib, por soporte de multipart y timeouts con la API HAL.
- **Pruebas**: unidad con cliente falso + E2E contra un DSpace falso local
  (stub del contract HAL) — el mismo enfoque del sink SMTP de aiosmtpd.
- **Credenciales**: `VISTOBUENO_DSPACE_USER` / `VISTOBUENO_DSPACE_PASSWORD`
  cubiertas por el escáner de secretos de pre-commit/CI (ampliar
  `scripts/verificar_secretos.py`).

---

## 9. Cómo reproducir este análisis

La barrera antibot ejecuta un proof-of-work en JavaScript; un navegador
headless lo resuelve como lo haría el de cualquier visitante:

```bash
# Versión y estado de la API (el DOM resultante es el JSON de la raíz)
google-chrome-stable --headless=new --disable-gpu \
  --virtual-time-budget=20000 --dump-dom \
  "https://repositorio.unitru.edu.pe/server/api"

# Comunidades de primer nivel
google-chrome-stable --headless=new --disable-gpu \
  --virtual-time-budget=20000 --dump-dom \
  "https://repositorio.unitru.edu.pe/server/api/core/communities?size=100"

# Colecciones de la comunidad FECyC (subcomunidades y colecciones)
google-chrome-stable --headless=new --disable-gpu \
  --virtual-time-budget=20000 --dump-dom \
  "https://repositorio.unitru.edu.pe/server/api/core/communities/9f93d7e9-ad18-4cc7-9472-7ee47fbbfe8f/collections?size=50"

# Metadatos de un ítem archivado (búsqueda con embed)
google-chrome-stable --headless=new --disable-gpu \
  --virtual-time-budget=20000 --dump-dom \
  "https://repositorio.unitru.edu.pe/server/api/discover/search/objects?query=educación%20inicial&scope=8d575820-ab89-43e0-abeb-33ee14b912c8&size=1&embed=metadata"
```

`--virtual-time-budget` da tiempo al JS del desafío; el DOM volcado del
endpoint de la API es el JSON (Chrome lo renderiza dentro de `<pre>`).
`curl` solo sirve para endpoints una vez resuelto el desafío en la misma
sesión (cookie `DSPACE-XSRF`/sesión BunkerWeb).

---

## 10. Referencias

- Contrato REST oficial DSpace 7/8: <https://github.com/DSpace/RestContract>
  - Autenticación: `authentication.md` (JWT, CSRF, status, refresh)
  - Depósito: `submission.md` (workspaceitems, secciones, workflowitems)
  - Metadatos del formulario: `workspaceitem-data-metadata.md` (JSON Patch)
- Instancia: <https://repositorio.unitru.edu.pe> (DSpace 8.1)

---

## 11. Captura del 2026-10-19: hallazgos del formulario real

Fuente: HAR exportado del navegador del operador durante un "Nuevo envío"
en la colección "Tesis de Ciencias de la Comunicación"
(`d26aecbf-f733-4682-9fbd-1174e944f2c3`). El análisis estructural vive en
`recursos/har-analisis/` (local, no versionado).

Hallazgos:

1. **Creación del workspaceitem**: `POST /submission/workspaceitems?owningCollection={uuid}`
   con cuerpo JSON vacío `{}` (la UI no usa multipart en la creación).
2. **Secciones**: `traditionalPeruOne` + `upload` + `license` (§4).
3. **Pre-llenos del servidor (16 campos)**: el workspaceitem nace con
   `dc.publisher`, `dc.publisher.country`, `dc.type`, `dc.type.version`,
   `dc.format`, `dc.language.iso`, `dc.rights`, `dc.rights.uri`,
   `dc.source`, `dc.subject.ocde`, `renati.type`, `renati.level`,
   `renati.discipline`, `thesis.degree.name`, `thesis.degree.discipline` y
   `thesis.degree.grantor`. Los valores dependen de la colección destino
   (tabla completa en `PLAN_FICHA_DEPOSITO.md` §4.1).
4. **Vocabularios controlados cerrados con valores URI**:
   `common_types_peru` (COAR), `common_version`, `common_format`,
   `common_iso_languages_peru`, `common_publisher`, `common_rights`,
   `dc_subject_ocde` (FORD), `renati_level_identifier`,
   `renati_type_identifier`. El formulario envía URIs, nunca texto de
   presentación.
5. **Bug de `dc.rights`**: el default configurado es
   `http://purl.org/coar/access_right/c_abf2`, pero el vocabulario
   `common_rights` solo contiene `https://…` (la consulta de resolución
   del UI devuelve vacía). El operador debe re-seleccionar "Acceso
   abierto" a mano en cada envío; el userscript lo corrige. Pendiente
   informar a la sede para que corrija la configuración del formulario.
6. **QUALDROP de documentos de identidad**:
   `renati.author.[dni|cext|pasaporte|cedula]` y
   `renati.advisor.[…]`: un dropdown (tipo de documento) + un valor
   (número) por entrada.
7. **`dc.date.issued`**: input tipo fecha (día/mes/año).
8. **Licencia de depósito**: texto Creative Commons de la colección +
   checkbox "Confirmo la licencia" (obligatorio). No es subida de
   archivo.

> **Advertencia operativa**: el export "sanitized" de Chrome NO elimina
> los cuerpos POST (el HAR capturado contenía el usuario y la contraseña
> del login en texto plano, y el JWT en las cabeceras de respuesta).
> Todo archivo `.har` se maneja como secreto: canal privado, extracción
> fuera del repo, destrucción posterior. `*.har` está en `.gitignore`.
