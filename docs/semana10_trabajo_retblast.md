# Bitácora Semana 10 — retblast

- **Integrante**: retblast (Integrante 1 — Backend / API)
- **Semana**: 10
- **Fechas**: 2026-11-01 → 2026-11-07 (semana en curso)
- **Rol**: Backend / API (FastAPI, contrato de la API, buzón de ficha,
  constancias y registro, escáner de secretos)
- **Ramas**: `fix/api-hardening-b0-b1` (25 commits sobre `master`; PR #71
  mergeado el 2026-11-03) y `docs/registro-documentos-sede` (cierre de la
  Actividad 14). El 2026-11-01 el trabajo siguió en la primera rama. Después
  se usaron las ramas `feature/act15-verificacion-frontend` (PR #79),
  `docs/kit-piloto-operador` (PR #80) y `fix/ensayos-aislados` (PR #81), los
  tres mergeados el 2026-11-04.

---

## Objetivos de la semana

1. **Actividad 14 — material de demostración**: dejar un par de documentos
   de ejemplo reproducible (uno conforme, otro no) con sus respuestas de
   `POST /validar`, una guía de lectura y la propuesta de estructura para
   registrar los documentos aportados por la sede.
2. **Informe de Avance de la semana 10**: dejar el informe en el formato
   que exige la guía de la asignatura (APA 7, carátula institucional) y
   el Portafolio Digital de Evidencias listo para subir.
3. **Cerrar la entrega del ciclo**: subir el portafolio, el plan v10 y el
   informe, y dejar la pila de commits de la rama lista para su PR.

---

## Actividades realizadas

### 2026-11-01 — Par de ejemplo de la actividad 14 (rama `fix/api-hardening-b0-b1`)

Segundo commit de la actividad 14. El primero (`7d7a26c`) agregó el
generador `scripts/ejemplo_bueno_malo.py`; este (`7c338c9`) agrega el par
de documentos y sus respuestas.

- **Generador reproducible**: `scripts/ejemplo_bueno_malo.py` construye los
  dos DOCX con la misma fábrica determinista que usa la suite de pruebas
  (`tests/docx_factory.py`). No hay datos de personas ni tesis reales: el
  par es sintético y se regenera en cualquier máquina.
- **`docs/ejemplos/doc_bueno.docx`**: cumple el formato institucional.
  `POST /validar` devuelve semáforo **verde**, 0 fallos.
- **`docs/ejemplos/doc_malo.docx`**: incumple varias reglas. `POST /validar`
  devuelve semáforo **rojo**, 4 errores y 1 warning.
- **Las dos respuestas** quedan versionadas tal cual (`respuesta_doc_bueno.json`,
  `respuesta_doc_malo.json`): son la evidencia del resultado esperado de
  cada documento.
- **`docs/ejemplos/GUIA_EJEMPLOS.md`**: explica qué se revisó en cada
  documento y qué resultado produce. Es la guía que acompaña al material
  en el portafolio (`semana 10/GUIA_EJEMPLOS.pdf`).

El par quedó en `master` con el PR #71 (mergeado el 2026-11-03). La segunda
parte de la actividad —el registro de los documentos aportados por la sede—
se cerró el 2026-11-04 con la propuesta de estructura (ver abajo); el
llenado real depende de los documentos que entregue la sede.

### 2026-11-01 — Informe de Avance y Portafolio Digital de Evidencias

- **Informe de Avance** (`Informe_Avance_S10_VistoBueno.md`, en la carpeta
  de la asignatura): 19 actividades, 16 narrativas (14 discretas y 2
  cargas transversales), 50 PRs mergeados y 696 pruebas. En ese informe, la
  actividad 14 figura como **en ejecución** desde el 01/11, con el par de
  ejemplo como evidencia parcial; el 2026-11-04 se cerró con la propuesta de
  estructura.
- **DOCX final con formato APA 7**: `generar_informe_docx.py` convierte el
  Markdown en un DOCX con carátula institucional, Times New Roman 12,
  interlineado doble, sangría de 1,25 cm, número de página arriba a la
  derecha, tablas sin bordes verticales y referencias con sangría
  francesa. El generador reemplaza al prompt externo: el contenido
  sigue teniendo una sola fuente de verdad (el Markdown) y el formato
  deja de depender de un copiado manual.
- **Correcciones de maquetación**: la nota de la Tabla 3 quedaba sola en
  una página (huérfana) y algunas filas de la Tabla 5 se partían entre
  dos páginas. Se corrigió con `keep_with_next` en el encabezado, el
  título y la última fila de cada tabla, `cantSplit` en las filas y un
  párrafo separador de 6 pt. El DOCX quedó en 43 páginas, sin páginas
  huérfanas y con las 19 filas de la Tabla 5 completas.
- **Portafolio Digital de Evidencias**: 209 archivos (14 MB), semanas 2 a
  10, con el índice de 7 páginas que mapea cada actividad con su
  evidencia. El escaneo de secretos da limpio.

---

### 2026-11-02 — Revisión del PR #71 y sus correcciones

El PR #71 recibió una revisión con 3 hallazgos bloqueantes, 5 medios y 3
bajos, más correcciones de documentación. Todo quedó corregido en seis
commits atómicos:

- `87778ab` — **cupos por CPU real**: el cupo adaptativo medía latencia
  (`perf_counter`) en vez de consumo de CPU. Con peticiones concurrentes la
  deuda se inflaba ~18× y bloqueaba la API con `429` espurios. Ahora se
  mide `time.thread_time()` dentro del hilo que valida y el papeleo se
  despacha al threadpool. Además: el modo legacy (`VISTOBUENO_RATE_LIMIT_MAX`)
  ya no cobra deuda de CPU, la ventana del entorno rige en los dos modos y
  el papeleo tiene salida de emergencia (`VISTOBUENO_RATE_LIMIT_PAPELES_CPU_SEG`,
  con `0` para desactivarlo).
- `87778ab` — **acceso remoto**: `VISTOBUENO_HOSTS` normaliza el puerto de
  cada entrada, y el peer remoto necesita **token y Host permitido**: la
  documentación prometía un `200` que nunca llegaba.
- `97081f6` — **userscript**: el botón "+" de Angular renderiza de forma
  asíncrona y el ejecutor lo contaba en el mismo tick (el segundo autor
  quedaba duplicado y vacío). Ahora espera el crecimiento de las filas. El
  re-llenado ya no pisa la edición del operador ni borra el timestamp del
  clic en Depositar, y el script sube a `@version 1.1.0` con
  `@updateURL`/`@downloadURL`.
- `97081f6` — **mock de DSpace**: el mock tenía un DOM propio que no
  ejercitaba el camino de las filas repetidas. Ahora replica la estructura
  real (`#N_array` + `ds-form-add-more`, verificada contra la captura
  oficial) y el ensayo general cubre una ficha con **dos autores**.
- `7eff923`, `320402b` — **escáner de secretos**: deja pasar valores
  formados solo por puntuación (`"..."`), expresiones que esconden un
  literal (`self.password+"extra"`) y el valor por defecto de una lectura
  del entorno (`os.environ.get("X", "secreto")`).
- `3cfd57d` y el commit siguiente — **corrección de documentación**: los
  comandos de `uvicorn` en `AGENTS.md` ahora llevan `--no-proxy-headers`
  (sin él, un `X-Forwarded-For` puede falsificar el peer y saltar el
  control de loopback). El cambio se hizo con la aprobación del
  responsable del repositorio, como exige la cláusula de `AGENTS.md`.

Al cierre del PR #71 la suite quedó con **730 tests recolectados**: en el
CI, donde `recursos/` no está, 721 pasan, 3 se omiten porque las plantillas
oficiales no se versionan y 6 quedan como `xfail(strict=True)`. Los 32
tests de node del userscript pasan, el ensayo general
`nix run .#test-ficha-deposito` pasa (incluye el flujo con dos autores) y el
CI del PR #71 queda en verde.

### 2026-11-04 — Cierre de la actividad 14 con la propuesta de registro

La actividad 14 pide una **propuesta de estructura** para registrar los
documentos que aporte la sede, no el registro lleno. Se agregó
`docs/REGISTRO_DOCUMENTOS_SEDE.md` con:

- campos de recepción, validación, devolución y cierre;
- la regla de privacidad: códigos, sin datos personales y carpeta local
  fuera del repositorio;
- el flujo de seis pasos y los estados permitidos;
- el criterio de cierre de la actividad y las preguntas abiertas.

El registro lleno se hará en el piloto (Actividad 16), cuando la sede
entregue los documentos. El archivo versionado es una plantilla y no
contiene datos de personas.

### 2026-11-04 — Verificación del frontend (actividad 15)

Lote 3 del plan previo al piloto (`docs/PLAN_LOTES_PRE_PILOTO.md`). La
pantalla de ficha de depósito se verificó contra la API real.

**Qué se comprobó:** los diez pasos del checklist —subir el documento
conforme, confirmar el semáforo verde, editar los datos extraídos,
completar los del operador, publicar en el buzón, confirmar el panel de
espera, aceptar el handle, descargar la constancia y la fila del registro,
comprobar la cabecera de token y limpiar el resguardo del navegador—. La
constancia sale del Modelo B oficial con los MERGEFIELD ya reemplazados
(137 KB) y la fila del registro responde en `tsv`, `csv`, `xlsx` y `json`.

**Hueco encontrado y cerrado:** la pantalla **no tenía ninguna prueba de
componente**; solo existían tests de las funciones puras de `ficha.js`. Se
agregó `frontend/src/components/FichaDeposito.test.jsx` con 8 casos que
montan la pantalla y recorren el flujo completo. Los casos se validaron con
mutaciones: sin publicar la ficha, o sin cotejar el título antes de usar el
handle, el test falla.

**Desfase encontrado y cerrado:** las respuestas versionadas del par de
ejemplo quedaron con el formato de detalle anterior al PR #78 (AUD-03):
5 reglas y sus prompts de IA seguían desfasados. Se regeneraron con
`scripts/ejemplo_bueno_malo.py` y se agregó
`tests/test_ejemplos_versionados.py`, que compara las respuestas versionadas
con las del motor para que el desfase no vuelva a colarse.

El detalle completo está en `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md` §8.

---

### 2026-11-04 — Kit del piloto (lote 4)

Lote 4 del plan previo al piloto (`docs/PLAN_LOTES_PRE_PILOTO.md`). Se
escribió el kit que va a seguir el operador de la biblioteca en la
primera sesión con la instancia real de DSpace:
`docs/PILOTO_OPERADOR.md`.

**Qué lleva:** propósito y alcance; roles (operador, Integrante 1 y
contacto de la sede); estado de la entrega; nueve precondiciones con su
comprobación; el checklist de ejecución de once pasos, cada uno con su
esperado objetivo; las limitaciones que el operador va a ver (AUD-24 a
AUD-27, el prefijo de `dc.title` y el `palabras_clave_minimo`); una tabla
de hallazgos para llenar durante la sesión; las reglas de datos
personales y datos locales; la reversión; y el cierre de la sesión.

**Borrador de coordinación:** va en el Anexo B. Es neutral y trae
marcadores entre corchetes (`[FECHA]`, `[HORA]`, `[LUGAR]`,
`[NOMBRE]`). Lo revisa y lo envía el contacto de la sede; el equipo no
envía nada en su nombre.

**Decisión de diseño:** las precondiciones van en una sección aparte, antes
del checklist. Varias solo se pueden comprobar con la API levantada
(`/docs` en 200, un `Host` ajeno en 400, la plantilla del Modelo B
presente, `VISTOBUENO_FIRMA` definida), y mezclarlas con los pasos de
ejecución las convertía en pasos sin criterio de falla.

---

### 2026-11-04 — Ensayo completo contra el mock (lote 5)

Lote 5 del plan previo al piloto (`docs/PLAN_LOTES_PRE_PILOTO.md`). La
compuerta final antes de agendar el piloto: correr los dos ensayos de
punta a punta.

**Resultado:** los dos pasan.

- `nix run .#test-ficha-deposito` → **«✅ FLUJO COMPLETO OK»**. Valida el
  doc bueno del factory, publica la ficha en el buzón, corre el userscript
  real contra el mock, rellena el formulario, conserva la edición del
  operador al volver a rellenar, alinea los dos autores con sus DNI,
  reporta el handle y el timestamp, y genera `registro.csv`,
  `registro.xlsx`, la constancia del Modelo B (137 103 bytes, sin ningún
  MERGEFIELD sin reemplazar) y el paquete `zip` con la fila del autor.
- `nix run .#test-local` → **«✅ TODAS LAS PRUEBAS E2E PASARON»**. Build del
  frontend, suite backend (736 pasan, 6 `xfail`), `POST /validar` por el
  proxy de Vite, 415 por tipo de archivo, 422 por correo inválido, el
  estado de la notificación (`deshabilitado` con `notificar=true`,
  `no_solicitado` sin él) y el proxy devolviendo 500 con body vacío
  cuando la API está caída.

**Tres cosas que había que arreglar antes de poder correrlos.** En su
estado anterior los dos comandos no se podían usar sin romper el trabajo
de otra sesión:

1. **Verde falso por API ajena.** Los dos ensayos levantan su propia API
   en el 8000. Con ese puerto ocupado, el `uvicorn` del ensayo no lograba
   hacer bind y el chequeo de arranque respondía contra la API que ya
   estaba escuchando: el ensayo daba verde sin haber probado nada. Ahora
   los puertos son configurables (`VISTOBUENO_API_PUERTO`,
   `VISTOBUENO_MOCK_PUERTO`, `VISTOBUENO_FRONTEND_PUERTO`) y los dos
   comandos **comprueban que estén libres antes de arrancar**: si no lo
   están, se detienen con un mensaje que dice qué hacer.
2. **Mataban procesos ajenos.** Al terminar, los dos scripts detenían
   cualquier `uvicorn` y cualquier `vite` del sistema. Ahora detienen solo
   los que levantaron, por PID. En este caso concreto se verificó que la
   API y el dev server de otra sesión siguen vivos después del ensayo.
3. **`test-local` no arrancaba.** `nix run .#test-local` fallaba con
   «python3: command not found»: la app del flake no ponía `pythonEnv`
   ni `nodejs` en el `PATH`, como sí hacía su hermana
   `test-ficha-deposito`.

También: `test-local` levantaba la API en `0.0.0.0`, en contra del
despliegue documentado (el loopback es la frontera de confianza). Ahora
usa `127.0.0.1`, y el proxy del dev server de Vite apunta a un destino
configurable (`VISTOBUENO_API_URL`).

**Lo que no se hizo:** el ensayo con navegador real. El clic manual contra
la instancia de la sede es parte del piloto (Actividad 16), no de este
lote.

---

## 2026-11-04 — Cierre de evidencias de la semana 10 (lote 6)

Lote 6 del plan previo al piloto (`docs/PLAN_LOTES_PRE_PILOTO.md`). El objeto
es que el registro de la semana no contradiga al repositorio: la suite, el
frontend, el estado de las actividades y el conteo de PRs tienen que coincidir
con lo que hay en `master`.

### Fila de regresión de la semana (Actividad 18)

| Momento | Tests en la suite |
|---|---|
| S1 — contrato inicial | 18 |
| S3–S4 — cierre de la Unidad I | 148 |
| S5 — notificación por correo | 244 |
| S6 — estructuras pendientes y contrato `tipo_documento` | 371 |
| S7 — depósito en DSpace y escáner de credenciales | 429 |
| S8 — ficha de depósito v1.7.0 | 622 |
| S9 — endurecimiento de API y userscript | 696 |
| **S10 — verificación frontend, kit del piloto y ensayos aislados** | **742** |

La medición es reproducible: `pytest tests/ -v` sobre `master` da 742
recolectados, 736 pasan y 6 quedan como `xfail(strict=True)`. Los 3 tests
que dependen de `recursos/` se omiten cuando esa carpeta no está, como pasa
en el CI.

### Registro de pull requests (Actividad 19)

**64 PRs mergeados en `master`**: 35 de autoría propia y 29 de compañeros
revisados e integrados. El repositorio suma el PR #10, pero su commit de
merge no está en el historial de `master`: se integró a una rama de trabajo,
así que no cuenta como mergeado en `master`.

El conteo sale del historial de git y de GitHub: los títulos y las fechas,
de `gh`; el conjunto de PRs que llegaron a `master`, de `git log`. Hay que
contar **los dos formatos de integración** del repositorio: los commits de
merge (`Merge pull request #N`) y los commits squash (`<título> (#N)`), que
GitHub crea al aplanar un PR. Un PR integrado con squash no deja commit de
merge, así que contar solo con `git log --merges` lo deja fuera: por eso el
conteo con `--merges` solo daba 60.

PRs mergeados en la semana universitaria 11:

| N.° | Título | Fecha | Rol |
|---|---|---|---|
| #62 | feat(frontend): limite de error, envio con Enter y toggle de tema con SVG (cierre S10, dia 1) | 2026-11-03 | Revisión e integración (autor: Rodo00) |
| #68 | feat(frontend): pantalla de ficha de deposito + cierre AUD-16/17/18 (Int2) | 2026-11-03 | Revisión e integración (autor: Rodo00) |
| #71 | fix(api): endurecer acceso, Host, cupo de CPU y userscript (AUD-28 a AUD-34) | 2026-11-03 | Autor |
| #74 | docs: corregir el estado de Int2 en los handover de auditoria | 2026-11-03 | Autor |
| #76 | docs: sincronizar contrato, README y handovers con el estado actual | 2026-11-04 | Autor |
| #77 | docs: agregar propuesta de registro de documentos de la sede | 2026-11-04 | Autor |
| #78 | fix(motor): enumerar todos los incumplimientos en el detalle de las reglas (AUD-03) | 2026-11-04 | Revisión e integración (autor: Rodo00) |
| #79 | test(frontend): verificar el flujo de la ficha de depósito (Actividad 15) | 2026-11-04 | Autor |
| #80 | docs: escribir el kit del piloto para el operador de la biblioteca | 2026-11-04 | Autor |
| #81 | fix(ensayos): que los dos ensayos no se pisen entre sí ni con otras sesiones | 2026-11-04 | Autor |
| #82 | docs: registrar el cierre de evidencias del lote 6 | 2026-11-04 | Autor |
| #83 | docs: registrar el PR #82 en el plan de lotes | 2026-11-04 | Autor |
| #84 | docs: corregir el conteo de pull requests de la bitácora | 2026-11-04 | Autor |

El conteo incluye el PR que lleva esta corrección: la cifra se mide sobre
`master` con el cierre documental de la semana ya integrado.

PRs abiertos que no son de este autor y siguen esperando al responsable del
motor: #72, #73 y #75.

### Informe y portafolio de prácticas

El informe de avance y el portafolio viven fuera del repositorio, en la
carpeta de la asignatura. Se actualizaron tres cosas:

- **Estado de las actividades**: la 14 pasó de *en ejecución* a *concluida*
  (PR #77) y la 15 quedó como *en ejecución* (PR #79), con el detalle de lo
  que falta: el clic manual en un navegador real contra la instancia de la
  sede, que es parte del piloto.
- **Rutas de la columna de evidencia**: la tabla de cobertura del índice
  apuntaba a una estructura de carpetas anterior (`02_BITACORAS_SEMANALES/`,
  `03_API_Y_VALIDACION/`, `07_CODIGO_Y_RESPALDO_TECNICO/`). Ninguna de esas
  rutas existía en la carpeta generada, así que toda evidencia citada era
  un enlace roto. Se reescribieron las 17 actividades con rutas reales
  (`semana N/`, `semana N/codigo/`) y se comprobó que todas existen.
- **Conteo de PRs**: el informe decía 61 PRs y 32 propios. El número
  correcto para `master` es 64 y 35, por dos razones: el PR #10 explicado
  arriba no cuenta, y el conteo tiene que incluir los PRs integrados con
  squash, que no dejan commit de merge. El caso del PR #10 estaba resuelto;
  el del squash, no: faltaba la mitad de los PRs.

El portafolio quedó con **258 archivos (19 MB)**, semanas 2 a 11, con el
índice de 10 páginas. La carpeta `semana 11/` lleva la bitácora de la
semana, el kit del operador, el plan de los lotes, la propuesta de registro de
la sede, el par de ejemplo con sus respuestas y el código de los ensayos.

---

## Evidencias producidas

| Evidencia | Dónde |
|-----------|-------|
| Par de ejemplo (documentos) | `docs/ejemplos/doc_bueno.docx`, `docs/ejemplos/doc_malo.docx` |
| Respuestas del validador | `docs/ejemplos/respuesta_doc_bueno.json`, `docs/ejemplos/respuesta_doc_malo.json` |
| Guía de lectura del par | `docs/ejemplos/GUIA_EJEMPLOS.md` |
| Propuesta de registro de documentos de la sede | `docs/REGISTRO_DOCUMENTOS_SEDE.md` |
| Generador del par | `scripts/ejemplo_bueno_malo.py` |
| Plan de lotes previos al piloto | `docs/PLAN_LOTES_PRE_PILOTO.md` |
| Kit del piloto para el operador | `docs/PILOTO_OPERADOR.md` |
| Verificación de la Actividad 15 | `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md` §8 |
| Guía de ejemplos en el portafolio | `semana 11/GUIA_EJEMPLOS.pdf` (carpeta de la asignatura) |
| Kit del piloto en el portafolio | `semana 11/PILOTO_OPERADOR.pdf` (carpeta de la asignatura) |
| Plan de lotes en el portafolio | `semana 11/PLAN_LOTES_PRE_PILOTO.pdf` (carpeta de la asignatura) |
| Índice y mapeo de evidencias | `semana 11/../00_INDICE_y_MAPEO.pdf` (carpeta de la asignatura) |
| Bitácora | este archivo |

- Commits de la semana: `7d7a26c` (generador del par de ejemplo),
  `7c338c9` (par de documentos, respuestas y guía), `87778ab`,
  `97081f6`, `7eff923` y `320402b` (correcciones de la revisión del
  PR #71), `931644e` y `707dc6f` (sincronización de documentación, PR #76).
- Cierre de la Actividad 14: `d06284f` en la rama
  `docs/registro-documentos-sede` (propuesta de registro), mergeado con el
  PR #77.
- Verificación de la Actividad 15: rama `feature/act15-verificacion-frontend`
  (pruebas de componente de la pantalla de ficha, regeneración de las
  respuestas de ejemplo y su test de guarda).
- Suite actual: **742 tests recolectados**: 736 pasan y **6 quedan como
  `xfail(strict=True)`** (los criterios de aceptación de AUD-24 a AUD-27 del
  motor). Los 3 tests que dependen de `recursos/` se omiten cuando esa
  carpeta no está disponible, como pasa en el CI.
- Frontend: **76 tests** en 9 archivos de prueba (`vitest` + `jsdom`).

---

## Relación con competencias curriculares

- **Ingeniería de Software II**: la reproducibilidad del par de ejemplo
  se resolvió con un generador determinista en lugar de archivos
  editados a mano; el par se puede regenerar y volver a verificar.
- **Estructura de Datos**: el par expone la estructura de la respuesta de
  la API (semáforo, resumen y resultados) y su correspondencia con el
  contrato vigente v1.12.0.
- **Redes de Computadoras I**: las dos respuestas son el registro de dos
  llamadas reales a `POST /validar` con `multipart/form-data`.
- **Ingeniería de Software I**: el informe de avance y el portafolio
  traducen el estado técnico a un documento académico con formato APA 7.

---

## Dificultades y aprendizajes

- **Un prompt externo no es un proceso reproducible**: el DOCX del informe
  se armaba a mano con una herramienta externa. El generador en el repo
  deja la fuente de verdad en un solo archivo (el Markdown) y hace el
  formato verificable: cualquier cambio del contenido se refleja con un
  comando.
- **Una maquetación se rompe por milímetros, no por párrafos**: la nota de
  la Tabla 3 quedó sola en la página siguiente por un párrafo separador
  demasiado alto. La corrección fue de espacios, no de contenido.
- **Verificar por coordenadas en vez de por imágenes**: la revisión de las
  43 páginas por texto y coordenadas de bloque detectó los problemas de
  paginación sin revisar 43 imágenes una por una.
- **Lo que un ejemplo no cubre**: el par demuestra el validador, no la
  integración con DSpace ni con el correo institucional. Esa parte sigue
  dependiendo de las credenciales de la sede.

---

## Plan de la semana siguiente

1. Verificar el CI de `master` después del merge del PR #71 (2026-11-03).
2. Reflejar el cierre de la actividad 14 —propuesta de estructura en
   `docs/REGISTRO_DOCUMENTOS_SEDE.md`— en el informe de avance y el
   portafolio; el registro lleno se hace en el piloto.
3. Verificar los `XPASS` de los `xfail` cuando Int3 corrija AUD-24 a
   AUD-27 y quitar las marcas.
4. Coordinar con Int2 el ajuste de la pantalla de ficha a los criterios de
   Int3 para AUD-24 a AUD-27. El token compartido (`X-VistoBueno-Token`)
   ya está implementado (`cda3d56`).
5. Cerrar el resto de la auditoría cuando Int3 entregue su parte: recién
   entonces se borra el bloque de aviso de `AGENTS.md` y se deja la línea
   en `docs/cronologia_trabajo.md`. Int2 ya cerró AUD-16 a AUD-18 con el
   PR #68.
6. Cerrar con el equipo las 6 decisiones de dominio abiertas (§8 del
   handover; AUD-18 ya está decidida).
