# Semana 8 — Trabajo realizado

**Integrante**: retblast
**Rol**: Integrante 1 — Backend / API
**Semana**: 8 de 14 (19/10/2026 – 24/10/2026) — **en curso (parcial al 19/10)**
**Proyecto**: VistoBueno — Validador automático de formato de tesis (UNT FECyC)

---

## Objetivos de la semana

1. Analizar el formulario real de depósito de DSpace (captura del
   navegador del operador) y congelar el plan de la ficha de depósito.
2. Implementar el contrato v1.7.0: ficha solo con semáforo verde, buzón
   de una ranura, constancia del Modelo B y fila del registro.
3. Construir el userscript que pre-llena el formulario oficial, con su
   ensayo general local.
4. Agregar la licencia MIT (el proyecto pasa a OSS).

---

## Actividades realizadas

### Tarea 1: análisis del formulario real y plan congelado (19/10)

- Captura del flujo "Nuevo envío" (HAR del navegador del operador,
  destruido tras la extracción): sección `traditionalPeruOne` confirmada
  (el típico `traditionalpageone` no aplica), creación del workspaceitem
  con JSON vacío, 16 campos pre-llenados por el servidor según la
  colección, vocabularios controlados con valores URI, QUALDROP de DNIs
  y bug de `dc.rights` (default `http` vs vocabulario `https`: el
  operador debía re-seleccionar "Acceso abierto" en cada envío).
  Hallazgos en `docs/DSPACE_API.md` §11.
- Hallazgo de seguridad operativa: el export "sanitized" de Chrome NO
  elimina los cuerpos POST (el HAR traía el login en claro). Regla
  establecida: todo `.har` se maneja como secreto; `*.har` quedó en
  `.gitignore` y se pidió la rotación de la contraseña al operador.
- `docs/PLAN_FICHA_DEPOSITO.md` v0.2 congelado: flujo aprobado, registro
  de 15 decisiones (login propio rechazado por la barrera BunkerWeb;
  excepción IP cancelada; userscript sobre la sesión del operador),
  mapa de campos, estrategia de pruebas de 4 niveles y rutas aparcadas
  (navegador automatizado; condición de activación de la ruta REST).
- Handover del motor actualizado: 7 extracciones + viabilidad de jurado;
  grado y línea de investigación descartados (pre-llenos del servidor).

### Tarea 2: contrato v1.7.0 — ficha, buzón, constancia y fila (19/10)

- `ficha_deposito` en `POST /validar` SOLO con semáforo verde (invariante
  con test). 24 tests nuevos entre buzón, contrato y guardas
  reforzadas: los guard tests existentes detectaron el drift del
  contrato y se actualizaron en la misma dirección del cambio.
- Buzón de una ranura (`validator/buzon.py`): TTL de 1 h, "última gana",
  ranuras independientes para ficha y depósito, sin cabeceras CORS
  (invariante con test: una página web cualquiera del navegador no puede
  leer los datos personales del estudiante).
- Constancia (`validator/constancia.py` + `POST /constancia`): Modelo B
  lleno por autor (evidencia del registro: una fila por estudiante, la
  misma handle para tesis con dos autores), 11 MERGEFIELD reemplazados
  por texto plano — incluida `ESCUELAS`, que el análisis inicial no
  había visto y la encontró el test de fidelidad contra la plantilla
  oficial. Fila TSV en el orden exacto de columnas del XLSX oficial
  (`POST /fila-registro`); el registro oficial jamás se escribe desde
  la app. 25 tests: golden files, multi-autor, 422/500 con detalle en
  español.
- Suite: 429 → 478.

### Tarea 3: userscript del formulario + ensayo general (19/10)

- `tools/dspace-fill/`: núcleo puro testeable (compuertas, mapeador
  ficha→plan, ejecutor DOM con setter nativo + eventos Angular) +
  wrapper delgado (buzón por `GM_xmlhttpRequest` con `@connect
  localhost`, MutationObserver para la navegación SPA, timestamp del
  clic en Depositar, watcher del handle, toast con resumen lleno/a
  mano/sin dato) + `dist/` instalable (commiteado, el CI verifica el
  drift) + `shim-gm.js` para correr sin Tampermonkey. 24 tests en
  node con jsdom.
- Un test del ejecutor detectó un fallo invisible propio: las filas
  incompletas (botón "+" no encontrado) se reportaban como éxito. Se
  corrigió la implementación hacia fallo visible — el resumen del toast
  nombra lo que quedó pendiente.
- Selectores verificados contra el DOM real capturado: `dc.rights` es un
  combobox (fix por texto + clic en la opción renderizada, con fallback
  manual visible); el botón "+" de filas solo existe en vivo
  (selectores candidatos + fallback).
- `nix run .#mock-dspace`: mock de las páginas de DSpace con proxy
  same-origin al buzón de la API real (la invariante sin-CORS queda
  intacta; el shim habla por el proxy). Checklist de 10 pasos en
  `dev/mock-dspace/README.md`. Verificado en vivo: ficha publicada en
  la API real y leída íntegra por el proxy.
- CI: paso aditivo en el job del frontend (`npm ci && npm test` del
  userscript + drift del dist), justificado en el PR #55 según la regla
  "toda área con verificación propia debe tener su paso en CI".

### Tarea 4: integración de la entrega del motor (diseño 17) (19/10)

- Rebase del PR #56 de Int3 (extracción de la ficha, sección DSL
  `extraccion` sobre `reglas_ficha.yaml`): sin conflictos de archivos.
- Activación de las capturas en la API (`load_ficha_rules` en
  `POST /validar`). Hallazgo y corrección de un leak propio: las reglas
  de captura llegaban a `resultados` porque el mapeo usaba la lista
  cruda del motor; ahora se excluyen (`captura=True`). Sondas de
  concurrencia actualizadas a la firma nueva de `validate_docx`. La
  ficha viaja con valores reales de extremo a extremo; el test
  transitorio se invirtió para afirmar la entrega real (con el doc
  bueno del factory). Suite: 493.
- Nota pendiente de relay a Int3: `dc.title` llega con el prefijo
  "Título del trabajo de investigación:" de la carátula — candidato a
  pulir en la captura; hoy el operador lo recorta en la pantalla.

### Tarea 5: OSS y verificación de la advertencia de secretos (19/10)

- LICENSE MIT (línea de copyright "VistoBueno contributors"), `*.har`
  en `.gitignore`, README sincronizado (regla de mantenimiento del
  AGENTS.md en cada commit que toca el contrato).

---

## Evidencias producidas

- Commits de la rama `semana8-deposito-ficha` (PR #55): `bc81822`
  (LICENSE + .har), `5039795` (plan v0.2), `3411a33` (DSPACE_API §11),
  `8bfb595` (handover), `9abf8ec` (buzón + ficha v1.7.0), `2d0f0f8`
  (contrato), `a134ae9` (constancia), `24cfbd7` (contrato constancia),
  `f85922b` (userscript), `bbcdbdf` (activación del diseño 17),
  `9914090` (contrato: ficha poblada), `e671fea` (mock-dspace),
  `9d56148` (CI del userscript).
- Documentos: `docs/PLAN_FICHA_DEPOSITO.md` v0.2, `docs/DSPACE_API.md`
  §11, `docs/CONTRATO_API.md` v1.7.0,
  `docs/HANDOVER_MOTOR_FICHA_DEPOSITO.md`, `docs/FLUJO_API.md` (buzón),
  README (sección de operación).
- Artefactos: `tools/dspace-fill/dist/vistobueno-dspace-fill.user.js`
  (instalable), `nix run .#mock-dspace` (ensayo general), paso de CI del
  userscript.
- Análisis local (no versionado, `recursos/`): `recursos/har-analisis/`
  con los cuerpos extraídos de la captura y los extractores.

---

## Relación con competencias curriculares

- **Ingeniería de Software II**: arquitectura del buzón (estado mínimo,
  invariante sin-CORS con test de regresión), manejo del drift de
  contrato vía guard tests, estrategia de pruebas de 4 niveles, ensayo
  general previo al piloto.
- **Estructuras de Datos**: DTOs de la ficha (extraídos/manuales,
  alineación por autor), serialización motor→API, colapso de capturas
  por campo en `build_report`.
- **Redes de Computadoras I**: análisis del contrato HAL de DSpace desde
  el HAR, CORS vs contexto de extensión (`GM_xmlhttpRequest`), proxy
  same-origin del mock, multipart y códigos de estado del contrato.
- **Ingeniería de Software I**: contrato v1.7.0 documentado, plan
  congelado con registro de decisiones, handover al motor, README de
  operación.

---

## Dificultades y aprendizajes

- El export "sanitized" de Chrome NO sanea los cuerpos POST: los `.har`
  se manejan como credenciales y se destruyen tras la extracción.
- Los guard tests existentes cumplieron su función: detectaron el drift
  del contrato y obligaron a que el cambio llegara con dirección
  declarada (tests actualizados, no eliminados).
- Un test propio del ejecutor cazó un fallo invisible mío antes de que
  existiera: filas incompletas reportadas como éxito. La suite gana al
  orgullo.
- El DOM real tiene piezas que la captura estática no muestra (el
  combobox renderiza opciones en vivo; el botón "+" solo existe
  hidratado). La respuesta correcta no es adivinar: selectores
  candidatos + fallo visible con instrucción para el operador.
- La captura del jefe trajo más de lo pedido: al exportar "sanitized"
  pero no guardar, se preservó la evidencia estructural sin riesgo de
  estado en la instancia; el borrador sobrante quedó como víctima del
  piloto.

---

## Plan de la semana siguiente

1. Piloto real con el operador (borrador descartable, checklist firmado)
   sobre la rama ya integrada.
2. UI de la ficha (Int2): pantalla de revisión, manuales, "Preparar
   depósito", panel de espera con auto-completado del handle, botón de
   copia de la fila TSV, resguardo en localStorage.
3. Relay a Int3: prefijo de `dc.title` en la captura (pulió el diseño
   17).
4. Merge del PR #55 con el CI en verde.

---

## Apéndice (23/10): revisión del PR #55 — hallazgos 10 y 11

Revisión propia del PR con dos hallazgos, ambos atendidos en la misma
rama:

- **Hallazgo 11 — registro descargable** (`POST /fila-registro` con
  `?formato=tsv | csv | xlsx`): el operador ya no depende del
  copiar-pegar crudo; los tres formatos llegan como archivo (BOM UTF-8
  para Excel, separador ';' y citas RFC 4180 en csv, libro con
  encabezado de 13 columnas en xlsx — `openpyxl` entró al flake). 6
  tests nuevos de formatos.
- **Hallazgo 10 — ensayo general de un comando**
  (`nix run .#test-ficha-deposito`): `scripts/e2e_ficha_deposito.sh`
  levanta API + mock, valida el doc bueno del factory, publica la ficha,
  corre el userscript real contra el mock con un driver jsdom
  (`tools/dspace-fill/dev/e2e_ensayo.js`), verifica timestamp del clic
  en Depositar y handle en el buzón, y descarga constancia + registro.
  Salida: "✅ FLUJO COMPLETO OK".
- **Bugs encontrados por el ensayo** (por eso existe):
  1. El driver hacía clic en Depositar antes de que el wrapper
     guardara el envío en curso (carrera microtask): el driver ahora
     espera su precondición.
  2. El proxy del mock calculaba `Content-Length` en caracteres, no en
     bytes: los títulos con acentos (UTF-8 multibyte) truncaban el JSON
     y la API respondía 422. Corregido con `Buffer.byteLength`; el
     ensayo ahora cruza títulos con acentos de punta a punta.
- Handovers para el resto del equipo, delimitados:
  `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md` (Int2: pantalla de ficha,
  panel de espera, descargas) y la nota de seguimiento §8 en el handover
  del motor (Int3: prefijo de la captura de `dc.title`).
- **Relectura de la revisión, puntos residuales**: el paréntesis del
  hallazgo 11 ("`POST /constancia` podría incluirlo") se materializó como
  `?formato=zip` (constancia .docx + registro.csv del autor en un solo
  paquete), y el "verifica archivos" del hallazgo 10 pasó de checar
  tamaños a verificar el CONTENIDO: MERGEFIELD reemplazados, matrícula y
  handle dentro de la constancia. Suite: 622.
- **Firma**: los commits de la revisión quedaron re-firmados tras recargar
  la identidad en el agente SSH.
- **23/10, segunda tanda — revisión completa (items 1-11)**: triage punto
  por punto publicado en el PR. Hechos: Swagger sin placeholders "string"
  (`6b4db6b`), plantilla sintética con ESCUELAS como campo complejo
  (`76f2d91`), realismo del mock (checkbox de licencia, file, título del
  ítem, `80b8726`). Corregidos con evidencia: el item 8 (POST /deposito
  NO depende del título del DOM — el e2e lo demuestra) y el 11 (la
  carrera era otra: microtask del relleno vs clic del driver; localStorage
  es síncrono). Verificados y RELAYADOS a Int3 sin tocar su área:
  asesor con valor vacío y detectado=true (reproducido contra la
  plantilla), año capturado como lugar ("Trujillo - Perú"), nota del
  XPath de párrafos hermanos (handover §8.1, `3b06560`). Suite: 622.
- **23/10, tercera tanda — botones del mock**: Master probó el ensayo
  manual y pidió botones ("comfy testing"): el índice ahora guía el flujo
  paso a paso con enlaces grandes; el formulario tiene un panel con
  "Publicar ficha de prueba" (POST al buzón vía proxy) y "Consultar de
  nuevo"; el ítem tiene un indicador persistente del handle (el toast
  dura 6 s, esto queda). El checklist del README ya no requiere curl
  para los pasos 2-3 y 9. Commit: `18a8895` (sin firma: el agente SSH
  tiene la clave pero git -S no la encuentra en este momento).
- **24/10, segunda pasada de revisión (items 12-18)**: hallazgos de
  calidad notablemente superior a la primera tanda. Todos los válidos
  atendidos en el orden sugerido:
  - **14** (inyección de fórmulas, API productiva): neutralización de
    prefijos `=`, `+`, `-`, `@` con comilla simple en csv/xlsx/tsv
    (`1a917a5`). El repro fue verificado contra openpyxl: sin el fix,
    `data_type='f'` (celda de FÓRMULA). Con el fix: texto.
  - **13** (proxy del mock): method por closure, no global (`16c0018`).
  - **15** (indicador del ítem): reintentos con backoff, 4 intentos
    cada 2 s (`16c0018`).
  - **12** (UX del mock): botón flotante siempre visible, texto
    genérico sin ficha; panel y checklist actualizados al comportamiento
    real (`316fad6`).
  - **16a** (pre-flight de la plantilla): mensaje claro al inicio si
    falta el Modelo B (`691606d`).
  - **18** (limpieza): ternario muerto en test del zip, corregido.
  - **16b** (paso de CI para el ensayo) y **17** (AGENTS.md): pendientes
    de aprobación del equipo — anotados en el PR.
  Suite: 626 backend + 24 node, ensayo general en frío verde.
- **24/10, aprobación de 16b y 17**: Master aprobó el paso de CI del
  ensayo general (`e9f0494`) y el sync de AGENTS.md (`fd38a0f`) —
  comandos del entorno, árbol del repo y handover de Int2 en la tabla
  de componentes. Conteo de la bitácora corregido (621→622, `6ccb160`).
- **24/10, cierre de nits**: pre-flight actualizado (el paso 7 omite la
  constancia, no falla), tabla de comandos de AGENTS.md completa
  (mock-dspace y test-ficha-deposito), test-local re-anunciado en el
  shellHook, bitácora al día, pkill con advertencia en el header,
  zip filename consistente con Content-Disposition (_nombre_seguro),
  comentario de esperar() corregido, nota de query strings en el proxy.
- **24/10, seguimiento del hallazgo 12**: la aserción del driver ya
  depende del clic (se limpia dc.title antes de pulsar el botón, que
  antes quedaba enmascarada por el auto-relleno de la ficha en el
  buzón); la segunda página ahora migra localStorage (estado cross-carga,
  el hábitat del bug original).
