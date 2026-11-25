# Bitácora Semana 11 — integrante2

- **Integrante**: integrante2 (Integrante 2 — Frontend / React)
- **Semana**: 11
- **Fechas**: 2026-11-23 → 2026-11-25
- **Rol**: Frontend (React + Vite): aplicación de los arreglos de `Arreglos.txt`
  v9 — timeout de 2 min y 429 en la carga, ORCID del asesor como campo
  extraído, resguardo local versionado por contenido y con caducidad,
  sección de configuración de papeleo.
- **Rama**: `frontend/timeout-429-orcid-papeleo` (desde `upstream/master`
  `2d2f0ac`, independiente de `fix-detalle-incidencias-aud03` / PR #78).

---

## Objetivos de la semana

1. **Parte 1 — Timeout y 429** (`Upload.jsx` + `upload.js`): subir el timeout
   del navegador a 2 min (sin cancelar el servidor al abortar) y manejar el
   HTTP 429 leyendo `Retry-After` (espera real, hora de reintento, botón
   deshabilitado, reintento manual, sin peticiones paralelas, archivo y correo
   conservados).
2. **Parte 2 — ORCID del asesor** (`ficha.js` + `FichaDeposito.jsx`): mover
   `renati.advisor.orcid` de `CAMPOS_MANUALES` a `CAMPOS_EXTRAIDOS` con aviso
   de revisión; si no se detectó, decirlo y pedir escribirlo a mano.
3. **Parte 3 — Resguardo local (F1 y F5)**: identificar el resguardo por
   contenido (hash) y no por nombre; verificar versión, identidad y caducidad
   al restaurar tras recarga; mensaje de descarte con motivo.
4. **Configuración de papeleo** (frontend solo, contrato propuesto pendiente
   de Int1): sección con nombre del responsable y plantilla Modelo B antes de
   «Preparar depósito».

---

## Actividades realizadas

### 2026-11-24 — Arreglos v9: timeout, 429, ORCID y resguardo (PR pendiente)

**`frontend/src/upload.js` (nuevo):**
- `TIMEOUT_VALIDACION_MINUTOS = 2` y `TIMEOUT_VALIDACION_MS = 120000`.
- `leerRetryAfter`, `formatearEspera`, `horaDeReintento`, `mensajeEspera`,
  `textoEspera`, `textoEsperaHasta` (helpers puros, testeados en
  `upload.test.js`).
- `hashDeArchivo` (SHA-256 del contenido, fallback `''` para `identidadDeArchivo` en `ficha.js`).

**`frontend/src/components/Upload.jsx`:**
- Timeout de 2 min con el nuevo mensaje; abortar la espera no cancela el
  servidor.
- Manejo 429 con `Retry-After`: cuenta regresiva, botón deshabilitado hasta el
  fin, reintento manual, conserva archivo y correo, no hay peticiones
  paralelas (`cargandoRef`).
- `identidadRef` se pasa a `onValidated(data, archivo)`.

**`frontend/src/ficha.js`:**
- `renati.advisor.orcid` de `CAMPOS_MANUALES` a `CAMPOS_EXTRAIDOS` (con
  `aviso` / `avisoSinDetectar`); `establecerValor` publica en `extraidos`
  (mueve manual→extraidos al editar).
- `VERSION_RESGUARDO=2`, `CLAVE_RESGUARDO`,
  `CADUCIDAD_RESGUARDO_MS=1h`, `identidadDeArchivo` (hash > nombre+tamaño),
  `guardarResguardo`/`leerResguardo`/`borrarResguardo`/`mensajeDeDescarte`.
- `estadoPapeleoDe` + `ESTADO_PAPELEO`; helpers `consultarPapeleo` /
  `guardarNombreResponsable` / `subirPlantillaPapeleo` (404 = no soportado,
  degrada con aviso).

**`frontend/src/components/FichaDeposito.jsx`:**
- Prop `archivo` con su identidad; resguardo versionado+identidad+caducidad con
  motivos de descarte mostrados al operador.
- Aviso ORCID (detectado/no detectado) y sección «Configuración de papeleo»
  (nombre responsable + plantilla Modelo B .docx) antes de «Preparar depósito».
- Borra el resguardo al volver al reporte.

**`frontend/src/App.jsx`:** guarda `identidadArchivo` y se lo pasa a `Upload`
y `FichaDeposito`.

### 2026-11-24 — Tests, docs y README

- `frontend/src/components/FichaDeposito.test.jsx` (nuevo, 11 tests): ORCID
  precargado con aviso, aviso si no se detectó, ORCID no bloquea, sección de
  papeleo completa/incompleta/no soportada, guardado del nombre, resguardo de
  versión/identidad/caducidad diferente y vigente.
- `frontend/src/components/Upload.test.jsx`: 2 tests del bloque 429 corrigidos
  (query robusto del botón y espera separada del mensaje de error); ahora 14/14.
- `frontend/src/ficha.test.js`: +15 tests (ORCID en extraidos,
  `establecerValor` manual→extraidos, `faltantesDe`, resguardo versión/
  identidad/caducidad, `estadoPapeleoDe`); ahora 47/47.
- `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md`: nota fechada del 2026-11-24 con
  los tres cambios + el contrato propuesto `GET/POST /papeleo-config` y
  `POST /papeleo-config/plantilla`.
- `README.md`: ORCID ya no es manual en el flujo (líneas 2 y 3 del flujo),
  ficha con resguardo versionado por contenido y caducidad de 1 h, sección de
  papeleo, espera de 2 min y manejo del 429 en la zona de carga.

### 2026-11-25 — Verificación y merge listo

- `npm run lint` → 0 errores (eliminada import `textoEspera` ahora no usada en
  `Upload.jsx`).
- `npm test` → **112 passed** (9 archivos): upload 13, upload.component 14,
  ficha 47, FichaDeposito 11, App 2, Report 20, ErrorBoundary 5.
- `npm run build` → 196.42 kB OK (Vite, producción).

---

## Evidencias producidas

- `frontend/src/components/Upload.jsx` — espera de 2 min + manejo del 429 con
  `Retry-After`; `identidadRef` a `onValidated`.
- `frontend/src/upload.js` — helpers puros de espera y hash de archivo.
- `frontend/src/components/Upload.test.jsx` — 14 tests de componente (incl.
  429 largo y reintento manual sin peticiones paralelas).
- `frontend/src/upload.test.js` — 13 tests de `leerRetryAfter`,
  `formatearEspera`, `textoEspera`, `textoEsperaHasta`, `horaDeReintento`.
- `frontend/src/ficha.js` — ORCID extraído, resguardo v2 por contenido con
  caducidad, `estadoPapeleoDe`, helpers de papeleo.
- `frontend/src/components/FichaDeposito.jsx` — resguardo versionado,
  aviso ORCID, sección de papeleo.
- `frontend/src/components/FichaDeposito.test.jsx` — 11 tests de componente.
- `frontend/src/ficha.test.js` — 47 tests de lógica de ficha.
- `frontend/src/App.jsx` — `identidadArchivo` compartido.
- `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md` — nota fechada 2026-11-24.
- `README.md` — estado actual del frontend (ORCID, resguardo, papeleo, 429).
- Commits en rama `frontend/timeout-429-orcid-papeleo` (pendiente de push y
  PR contra `retblast/vistobueno`).

---

## Relación con competencias curriculares

- **Ingeniería de Software II**: separación lógica de flujo (funciones puras
  de `ficha.js` testeables) y presentación; manejo de errores HTTP 429 con
  cuenta regresiva y salida recuperable; calidad de código (commits
  atómicos, lint, build en CI).
- **Redes de Computadoras I**: cabeceras HTTP (`Retry-After`), multipart,
  código 429 como respuesta de control de tráfico, endpoints propuestos
  `GET/POST /papeleo-config`.
- **Ingeniería de Software I**: documentación técnica (handover, bitácora,
  README) y respuesta documentada a los arreglos del usuario (`Arreglos.txt`
  v9).

---

## Dificultades y aprendizajes

- **El nombre del botón cambia durante la carga** («Validando…»), así que el
  test no puede buscarlo por nombre estático: se consulta por
  `button[type="submit"]` y se comprueba `textContent` con regex.
- **La espera del 429 va en un bloque separado del mensaje de error**: si se
  mezcla en `texto` del error, aparece dos veces (banner + aviso) y el test
  falla por elementos duplicados.
- **`textoEspera` importado y no usado**: el linter lo atrapó antes del
  commit; se eliminó de la importación de `Upload.jsx`.
- **Resguardo por contenido**: dos tesis con el mismo nombre pero distinto
  hash no se confunden; la identidad se calcula sobre el archivo real, no sobre
  el nombre que el usuario elija al subirlo.
- **`localStorage` en jsdom está disponible por defecto**: no hace falta
  polyfill para los tests de resguardo.

---

## Plan de la semana siguiente

1. PR #130 abierto contra `retblast/vistobueno` (rama
   `frontend/timeout-429-orcid-papeleo`). Revisado localmente: 112/112 tests,
   lint 0, build OK.
2. Cambios derivados de la revisión (`Arreglos.txt` revisión de PR #130):
   - `frontend/package.json` declara `"engines": { "node": ">=20 <23 }` y se
     agregó `frontend/.nvmrc` con `22` (jsdom 25 requiere Node 22 LTS; en Node
     26 `window.localStorage` es `undefined` y rompen los tests de resguardo).
   - Puntos de seguimiento no bloqueantes: base del 429 por latencia real
     (PR pequeño de seguimiento) y contrato de papeleo pendiente de Int1
     (el frontend ya degrada con «no soportado»).
3. Botones IA y estimador de paginación del informe PPP: se dejan para
   después (acordado con el usuario).
