# Plan: ficha de depósito, relleno del formulario oficial y constancia

**Versión**: 0.2 (congelado)
**Fecha**: 2026-10-19
**Estado**: aprobado para construcción. Las decisiones están cerradas tras
el análisis del formulario real de la instancia (captura del 2026-10-19).
**Área**: Backend/API (Int1), con Motor (Int3) y Frontend (Int2)
**Relacionados**: `docs/DSPACE_API.md` (análisis de la instancia y hallazgos
de la captura), contrato v1.6.0 (`docs/CONTRATO_API.md`),
`docs/HANDOVER_MOTOR_FICHA_DEPOSITO.md` (pedido al motor)

---

## 1. Contexto

El repositorio institucional de la UNT (DSpace 8.1) opera bajo la política
nacional de acceso abierto: la Ley 30035 y las directivas del CONCYTEC
establecen el depósito digital obligatorio de tesis en repositorios
institucionales, con metadatos estandarizados que Renati cosecha. El
formulario de depósito tiene tantos campos porque replica ese formato
nacional (RENATI), no por diseño local.

Hoy el responsable del repositorio de la FECyC llena esos campos a mano,
tesis por tesis, y luego produce a mano la constancia (Modelo B) y la fila
del registro (XLSX). VistoBueno ya abre y analiza el DOCX completo, así que
puede eliminar esa transcripción.

El 2026-10-19 se capturó el flujo real "Nuevo envío" del formulario de la
instancia (HAR del navegador del operador). Esa captura congeló el mapa de
campos y las decisiones de este plan. El análisis estructural vive en
`recursos/har-analisis/` (local, no versionado; regla de manejo en §10).

## 2. El flujo aprobado

Todo ocurre en la PC del operador. La app nunca escribe a la API de DSpace:
el formulario oficial es quien construye todas las peticiones.

```
1. subir .docx → POST /validar → semáforo
   ROJO → reporte + prompts IA. Fin.
   VERDE → ficha editable en pantalla
2. ficha: 7 campos extraídos del DOCX + 4 manuales del operador
   [Preparar depósito] → POST /ficha-pendiente (buzón: 1 ranura, TTL 1h)
3. DSpace, cualquier pestaña: userscript (compuertas: ficha fresca +
   colección de tesis) → auto-rellena el formulario → selecciona
   "Acceso abierto" → registra el timestamp del clic en Depositar
4. operador: arrastra el .docx (upload) → checkbox "Confirmo la licencia"
   → Depositar → aprueba → abre el ítem
5. userscript en la página del ítem: detecta el handle →
   POST /deposito {handle, título, timestamp}
6. la SPA (sondeando) auto-completa el panel de depósito
   → [Descargar constancia + fila]: N constancias .docx (una por autor)
     + fila TSV para pegar en el XLSX oficial
```

El checkbox "Confirmo la licencia" NO es una subida de archivo: es la
aceptación de la licencia de distribución (texto Creative Commons de la
colección) en la última pantalla del envío oficial. El operador ya lo marca
hoy en cada envío y sigue siendo su clic: es una declaración legal, el
userscript nunca lo toca.

## 3. Decisiones congeladas (2026-10-19)

| # | Decisión | Veredicto |
|---|----------|-----------|
| 1 | Rellenar el formulario oficial por DOM (userscript en la sesión del operador) | Adoptado. El UI oficial construye las peticiones; un fallo del script es visible e inocuo (el operador teclea a mano) |
| 2 | Página de login propia / capturar credenciales DSpace en la app | Rechazado. BunkerWeb bloquea clientes programáticos con o sin credenciales (re-verificado el 2026-10-19: `302 /challenge` incluso con User-Agent de navegador). Credenciales ≠ conectividad |
| 3 | Excepción de IP + cuenta de servicio ante la sede | Cancelado. El depósito usa la sesión del operador. La ruta REST queda como condición de activación (§9.2) |
| 4 | Navegador automatizado (Playwright) | Aparcado (§9.1) |
| 5 | Restricción localhost | Adoptado. uvicorn ya hace bind a `127.0.0.1` por defecto; es el control de acceso del MVP. Frontera de confianza: el usuario del sistema operativo |
| 6 | Ficha | 7 extraídos + 4 manuales (§4). 16 campos los pre-llena el servidor por colección; la ficha nunca los carga |
| 7 | Mapeo línea de investigación → OCDE | Cancelado. `dc.subject.ocde` viene pre-lleno por colección |
| 8 | Bug de `dc.rights` (default `http` vs vocabulario `https`) | El userscript selecciona "Acceso abierto" (valor canónico del vocabulario). Cortesía pendiente: informar a la sede |
| 9 | Constancia | `.docx` lleno con python-docx sobre el Modelo B, sin conversión a PDF (sin LibreOffice). Una constancia por autor |
| 10 | Fila de registro | TSV en el orden exacto de las columnas del XLSX; el operador la pega. Nunca se escribe el XLSX oficial desde la app |
| 11 | Comunicación app ↔ userscript | Buzón de una ranura en el backend local + `GM_xmlhttpRequest` (`@connect localhost`) + `GM_setValue`. `postMessage` descartado (depende de pestañas abiertas por la app) |
| 12 | Auto-relleno | Con compuertas (ficha fresca por TTL + colección de tesis FECyC). Toast con el título como autocomprobación. Botón manual como fallback. Sin etapas |
| 13 | Handle | Auto-push desde la página del ítem. Timestamp capturado en el clic Depositar. Pegado manual como fallback oculto |
| 14 | Puerta verde | La ficha solo materializa en respuestas con semáforo verde (invariante con test) |
| 15 | OSS | LICENSE MIT; `*.har` en `.gitignore`; README de operación; sin CORS en el buzón (una web cualquiera del navegador no puede leer la ficha) |

## 4. El mapa de campos (evidencia: captura del formulario)

### 4.1 Pre-llenos del servidor (16 campos)

Al crear el workspaceitem, el servidor ya trae estos campos con valores
dependientes de la colección destino (observados en "Tesis de Ciencias de
la Comunicación"):

| Campo | Valor observado |
|-------|-----------------|
| `dc.publisher` | Universidad Nacional de Trujillo - UNITRU |
| `dc.publisher.country` | PE |
| `dc.type` | `http://purl.org/coar/resource_type/c_7a1f` (Tesis de bachiller) |
| `dc.type.version` | `http://purl.org/coar/version/c_970fb48d4fbd8a85` (VoR) |
| `dc.format` | `application/pdf` |
| `dc.language.iso` | `spa` |
| `dc.rights` | `http://purl.org/coar/access_right/c_abf2` (ver bug en §4.4) |
| `dc.rights.uri` | `https://creativecommons.org/licenses/by-nc-nd/4.0/` |
| `dc.source` | Repositorio Institucional - UNITRU |
| `dc.subject.ocde` | `https://purl.org/pe-repo/ocde/ford#5.08.00` (Comunicación) |
| `renati.type` | `https://purl.org/pe-repo/renati/type#tesis` |
| `renati.level` | `https://purl.org/pe-repo/renati/level#tituloProfesional` |
| `renati.discipline` | 32100241 |
| `thesis.degree.name` | Licenciado en Ciencias de la Comunicación |
| `thesis.degree.discipline` | Comunicación |
| `thesis.degree.grantor` | Universidad Nacional de Trujillo. Facultad de Educación y Ciencias de la Comunicación |

La ficha nunca los carga: la colección destino los decide.

### 4.2 Ficha: extraídos del DOCX (motor, Int3)

| Dato | Destino |
|------|---------|
| Título | `dc.title` |
| Autores | `dc.contributor.author` (lista) |
| Asesor | `dc.contributor.advisor` |
| Resumen | `dc.description.abstract` |
| Palabras clave | `dc.subject` (lista) |
| Año de emisión | `dc.date.issued` (detección nueva) |
| Escuela | columna ESCUELAS del registro (no es campo del formulario) |

`renati.juror` es opcional y depende de la viabilidad de extraer los
nombres del jurado de la sección de firmas (pedido abierto al motor).

### 4.3 Ficha: manuales del operador

| Dato | Destino |
|-------|---------|
| N° de matrícula | fila del registro + constancia (no es campo DSpace) |
| DNI del autor | `renati.author.dni` (QUALDROP del formulario) |
| DNI del asesor | `renati.advisor.dni` (QUALDROP) |
| ORCID del asesor | `renati.advisor.orcid` |

Se teclean UNA vez en VistoBueno y fluyen a todos los destinos.

### 4.4 Los demás campos

- DOI, ISBN, cita, título alternativo, embargo: opcionales, normalmente
  vacíos; el operador los llena a mano si aplican.
- Bug de `dc.rights`: el default configurado del formulario es
  `http://…c_abf2`, pero el vocabulario `common_rights` solo contiene
  `https://…c_abf2`; la consulta de resolución del UI devuelve vacía y el
  operador debía re-seleccionar "Acceso abierto" en cada envío. El
  userscript lo corrige seleccionando la opción canónica.

## 5. Contrato v1.7.0

`POST /validar` gana una sección `ficha_deposito` SOLO en respuestas con
semáforo verde:

```json
"ficha_deposito": {
  "extraidos": [
    {"campo": "dc.title", "valor": "…", "pagina": 1, "detectado": true},
    {"campo": "dc.contributor.author", "valor": ["…"], "pagina": 1, "detectado": true},
    {"campo": "dc.date.issued", "valor": null, "detectado": false}
  ],
  "manuales": [
    {"campo": "matricula", "valor": null},
    {"campo": "renati.author.dni", "valor": null},
    {"campo": "renati.advisor.dni", "valor": null},
    {"campo": "renati.advisor.orcid", "valor": null}
  ]
}
```

Los manuales viajan vacíos desde el motor; el operador los llena en la
pantalla. Endpoints nuevos: buzón (§6) y `POST /constancia` (§7).

## 6. El buzón (comunicación app ↔ userscript)

- Ranura única en memoria del proceso, TTL de 1 h, "última gana".
  Supuesto documentado: un operador, una tesis en vuelo a la vez.
- `POST /ficha-pendiente`: la SPA publica la ficha completada.
- `GET /ficha-pendiente`: el userscript la lee (`GM_xmlhttpRequest`,
  `@connect localhost`; exento de CORS y mixed content por correr en el
  contexto de la extensión).
- `POST /deposito` (`handle`, `título`, `timestamp`): el userscript reporta
  el depósito desde la página del ítem.
- `GET /deposito`: la SPA sondea mientras espera.
- Sin cabeceras CORS: una web maliciosa del navegador no puede LEER la
  ficha (contiene datos personales del estudiante). Peor caso de un POST
  ciego: basura visible en el botón/toast, recuperable re-preparando.

Compuertas del auto-relleno: ficha fresca (TTL) + colección de destino
perteneciente a las 12 de tesis FECyC (§5 de `DSPACE_API.md`). Falla
cerrada: sin ficha o sin match, no pasa nada; el botón manual queda como
opción deliberada.

## 7. Constancia y fila de registro

- Entrada: ficha completada + handle + timestamp + FIRMA (constante de
  configuración). Salida: `.docx` lleno + fila TSV.
- El registro oficial muestra una fila POR AUTOR (evidencia: tesis con dos
  autores ocupan dos filas con el mismo handle). El Modelo B es por
  estudiante ("Presentado por X, con matrícula N° Y"). Por lo tanto:
  N autores → N constancias + N filas.
- Endpoints: `POST /constancia` (descarga del Modelo B lleno, una por
  autor, `indice_autor` 0-based) y `POST /fila-registro` (filas TSV en
  el orden de columnas). Configuración: `VISTOBUENO_FIRMA` (columna
  FIRMA) y opcional `VISTOBUENO_PLANTILLA_CONSTANCIA`.
- Mergefields del Modelo B (11): `TESIS__TSP`, `BACHILLER__LICENCIADO`,
  `N_MATRIC`, `DD`, `MM`, `AA`, `HORA`, `AÑO`, `DIRECCION_URL`,
  `FECHA_DEL_DOC` y `ESCUELAS` (verificado contra la plantilla oficial:
  11 campos, ninguno sobrevive al llenado; test de fidelidad local).
- Columnas del TSV (orden del XLSX): N°, TESIS/TSP, BACHILLER/LICENCIADO,
  N° MATRIC., DD, MM, AA, HORA, DIRECCION URL, FIRMA, FECHA DEL DOC.,
  ESCUELAS, AÑO.
- El XLSX oficial jamás se escribe desde la app.

## 8. Estrategia de pruebas (resumen)

1. **Unitarios**: mapeador ficha→plan de relleno, compuertas, extracción
   de handle (`node --test`); extracciones del motor, buzón, constancia
   (pytest, golden files).
2. **Ensayo general local**: `shim-gm.js` (GM_* sobre APIs vanilla) +
   fixture del DOM real + `mock-dspace` (`nix run .#mock-dspace`): el flujo
   completo corre local sin tocar la instancia. El núcleo va automatizado
   a CI con jsdom.
3. **Piloto real**: un borrador descartable en la instancia, con el
   operador presente, checklist firmado.
4. **Casos límite**: multi-autor, ficha expirada, colección ajena, handle
   incorrecto, plantilla ausente, año no detectado.

Invariantes con test: ficha solo en VERDE; buzón sin CORS; `@connect` solo
localhost.

## 9. Rutas aparcadas

### 9.1 Navegador automatizado ("Flavor 2")

Estado: descartada para el MVP. Documentada como mejora potencial para que
el equipo futuro sepa que existe y cuándo reconsiderarla.

Qué es: en lugar del userscript en el navegador del operador, la app
abriría una ventana de Chrome automatizada (Playwright). El operador
iniciaría sesión UNA vez en la pantalla real de DSpace y la app
reutilizaría esa sesión para ejecutar el flujo completo de depósito sin
clics.

Por qué no ahora: agrega una dependencia pesada (Playwright) al flake y
requiere gestión de perfil de sesión; pisa la zona gris de la barrera
antibot (la decisión documentada en `DSPACE_API.md` §2.1 es no automatizar
el desafío); el userscript ya elimina la transcripción manual con menos
piezas móviles y cero manejo de credenciales.

Cuándo reconsiderarla: si la sede concediera la excepción de IP, la ruta
REST la vuelve innecesaria; si el operador exigiera depósito sin clics Y la
sede no concediera la excepción, vuelve a la mesa con acuerdo del equipo.

### 9.2 Ruta REST: condición de activación (sin gestión activa)

La ruta REST de `validator/dspace.py` queda implementada, stub-testeada y
deshabilitada por defecto. No se solicita ninguna gestión a la sede: en
esta instancia el depósito se hace con el userscript sobre la sesión del
operador, que ya pasa la barrera antibot como cualquier navegador.

La ruta REST se activa solo cuando la instancia lo permite:

- otra institución que despliegue VistoBueno contra un DSpace sin barrera
  antibot (o con una excepción equivalente), o
- un futuro despliegue de VistoBueno como servidor compartido en la UNT.
  En ese caso hacen falta: excepción de IP para `/server/*` y una cuenta
  de servicio con permiso de envío.

Requisitos de activación: `VISTOBUENO_DSPACE=1`, credenciales por
variables de entorno y colección destino (ver `DSPACE_API.md` §7).

## 10. Riesgos y reglas operativas

- Todo `.har` es un secreto: el export "sanitized" de Chrome NO elimina
  los cuerpos POST (la captura del 2026-10-19 contenía el login en texto
  plano y el JWT en cabeceras). Canal privado, extracción fuera del repo,
  destrucción posterior. `.gitignore` cubre `*.har`.
- Un fallo del userscript es visible (el operador teclea a mano); nunca
  deja estado a medias en el servidor.
- El handle solo existe tras la aprobación del workflow; el pegado manual
  queda como fallback.
- Selector drift si la sede actualiza el UI: fallo visible, se repara.
- El buzón es la única pieza de estado del servidor: una ranura en
  memoria. Reinicio del proceso = re-preparar la ficha (re-validar).

## 11. Distribución

| Tarea | Dueño |
|-------|-------|
| Contrato v1.7.0 + buzón + `POST /constancia` + tests | Int1 |
| Motor: 7 extracciones + viabilidad de jurado | Int3 |
| UI: ficha, manuales, Preparar, panel de espera, TSV, localStorage | Int2 |
| Userscript + shim + mock-dspace + tests | Int1 |
| README de operación + LICENSE + filas de AGENTS.md (con aprobación) | Int1 |
| Piloto con el operador | Int1 + sede |
