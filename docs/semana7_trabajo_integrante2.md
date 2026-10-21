# Semana 7 — Pruebas de usabilidad + documentación

**Integrante**: Integrante 2 (Frontend / UX)  
**Fecha**: 2026-09-23  
**Rama**: `s7-usabilidad-ihc` (PRs: retblast#31, Rodo00#10)

---

## Objetivos

1. Ejecutar pruebas de usabilidad del flujo de carga y visualización de resultados.
2. Aplicar mejoras IHC a la interfaz.
3. Pruebas finales del flujo completo (frontend ↔ backend).
4. Corregir errores y documentar avances.

---

## Actividades realizadas

### Evaluación IHC

Se evaluaron las interfaces de **carga**, **resultados** y **desplegables** contra principios de usabilidad (visibilidad de estado, prevención de errores, affordance, contraste, redundancia). Hallazgos principales:

- Límite de archivo inconsistente (25 MB UI vs 10 MB backend).
- Falta de feedback durante la validación.
- Errores de API ocultos detrás del reporte mock.
- Click en dropzone no abría el selector.
- Badge de severidad redundante con el icono.
- Fuentes por debajo de 12 px en contadores/detalles.
- `API_BASE_URL=''` acoplada a mismo origen sin documentar.

### Correcciones aplicadas (commit `e27e683` + commit de revisión)

| Área | Cambio |
|------|--------|
| **Carga** | Límite unificado a **10 MB**; spinner + dropzone deshabilitada; click en toda la dropzone; botón ✕ para quitar archivo; aviso de error cerrable; solo `.docx`. |
| **Errores API** | HTTP con cuerpo JSON (`detail`) → mensaje real al usuario **sin** mock. Error de red o proxy sin JSON → fallback a mock **como modo demo** (avisado en Report con `__mock`). Título de aviso genérico: “No se pudo validar.” (luego reemplazado por mensajes específicos en C26) |
| **Resultados** | Scroll suave al semáforo; categorías en cards IA en vez de `rule_id`; desplegables cerrados por defecto; badge de severidad eliminado (redundante con icono); iconos compactos con `aria-label`. |
| **Layout / CSS** | Pantalla completa centrada (alto y ancho); botón “← Validar otro archivo” visible; separación intro ↔ dropzone; footer separado; fuentes mínimas 12 px; `focus-visible` en `summary`/labels; botón Copiar ≥ 44 px; contraste dark en chips/avisos; spinner. |

### Documentación de despliegue (punto 2 de `Arreglos.txt`)

- `README.md` → sección **“Despliegue del frontend (`VITE_API_URL` y proxy)”**: tabla dev / preview / build, nota de reverse proxy y modo demo.
- `frontend/src/App.jsx` y `frontend/vite.config.js` → comentarios sobre alcance del proxy (solo `vite dev`) y variables de entorno.
- `frontend/.env.example` → plantilla de `VITE_API_URL`.

### Pruebas del flujo completo

- Backend: `.venv/bin/python -m uvicorn validator.api:app` en `:8000` (PID estable con `setsid`).
- Frontend: `npm run dev` en `:5173`.
- `POST` a `http://localhost:5173/validar` (proxy) → **HTTP 200**, 41 reglas, semáforo rojo con DOCX de prueba.
- Suite de tests backend: **132 passed, 17 skipped** (verificado en iteraciones previas).

### Nueva tanda — `Arreglos.txt` v2 (posicionamiento + notificación)

Se recibió una nueva versión de `Arreglos.txt` con 3 puntos a coordinar:

#### §0 — Cambio de posicionamiento del producto (C11)

El producto ahora se orienta al **personal de la sede (Repositorio FECyC)**, no a la autogestión del estudiante. Textos reorientados de 2ª persona informal a operador:

| Archivo | Cambio |
|---------|--------|
| `Upload.jsx` | Título "Sube tu tesis" → **"Validar documento de tesis"**; intro, dropzone y textos a "Adjunte/Arrastre/selecciónelo" |
| `Report.jsx` | "¡Puedes entregar!" → **"Documento listo para entregar"**; "Tu documento" → "El documento"; "corrige" → "corregir"; "Copia y pega" → "Copie y pegue" |
| `docs/diseno/01_requisitos_interfaz.md` | Tabla de actores: operador como usuario primario, estudiante como receptor; objetivos y RF renumerados (RF-01…RF-25) |
| `docs/diseno/03_wireframes.md` | Títulos, dropzone, error copy, semáforo, prompts — todo reorientado; limitado a `.docx`, 10 MB |
| `mockups/carga.html`, `mockups/reporte.html` | Mismos cambios de copy |

#### §1 — Captura del correo del estudiante (C12/C13)

- **Nuevo campo opcional** en `Upload.jsx`: input `type="email"` con:
  - Validación de formato en cliente (`/^[^\s@]+@[^\s@]+\.[^\s@]+$/`) para evitar 422 innecesario.
  - `aria-invalid`, `aria-describedby`, mensaje de error inline.
  - Copy de privacidad: *"El correo se usará únicamente para enviar el reporte de validación al estudiante."*
- **Restricción técnica**: el correo viaja en la **misma solicitud** `POST /validar` (campo de formulario `correo`), así que se pide **antes** de validar, no después.
- En `validate()`: `if (correo && esCorreoValido(correo)) form.append('correo', correo)`.
- Si el backend responde `422` con `detail` español, el banner existente ya lo muestra (sin cambios).
- CSS nuevo: `.campo-correo`, `.campo-ayuda`, `.campo-error` + variante dark mode.

#### §2 — Respuesta aditiva `notificacion` (C14, preparado para cablear)

- `mocks.js`: `MOCK_REPORT.notificacion = { enviado: true }` (aditivo, no rompe parsing).
- `Report.jsx`: badge condicional bajo el semáforo:
  - `enviado: true` → *"📧 El reporte fue enviado al correo del estudiante."* (verde)
  - `enviado: false` → *"⚠ No se pudo enviar el correo al estudiante."* (rojo)
- CSS: `.badge-notif.ok` / `.badge-notif.fail` + dark mode.

> **Nota**: §3 confirma que el contrato API no cambia esta semana (correo sigue siendo opcional; sin él el endpoint se comporta igual). §4 indica envío real ~S6/S7 con credenciales SMTP institucionales.

### Tercera tanda — `Arreglos.txt` v3 (notificación por correo: opt-in + estados)

Se describió el contenido del **PR #37** (`semana5-notificacion-correo`, backend), que extiende la respuesta de `POST /validar` a **v1.3.0 (aditivo)** y agrega el envío opt-in de observaciones. Frontend preparado en consecuencia:

#### §1 — Respuesta `notificacion: { estado, detalle }` (C15)

El campo deja de ser `{ enviado: boolean }` y pasa a un objeto con 6 estados (contrato `NotificacionAPI` / `EstadoNotificacionAPI`):

| `estado` | Qué muestra el badge |
|----------|----------------------|
| `enviado` | 🟢 "Enviamos las observaciones al correo del estudiante." |
| `fallo` | 🔴 "No se pudieron enviar..." + **detalle técnico** (`SMTPAuthenticationError: 535 ...`) para reintentar o enviar manualmente |
| `sin_correo` | 🟠 Pide el correo del estudiante en el formulario de carga |
| `no_solicitado` | 🔵 Ofrece la casilla de envío (opt-in) en el formulario |
| `sin_observaciones` / `deshabilitado` | Sin badge (nada relevante) |

- `Report.jsx`: nueva función `badgeNotificacion(notif)` con el mapa anterior; solo se renderiza si `estado` es string (retrocompatible: backend anterior sin el campo → sin badge, sin romper).
- `mocks.js`: `notificacion: { estado: 'enviado', detalle: null }`.
- CSS: `.badge-notif.warn` (ámbar), `.badge-notif.info` (azul), `.badge-notif-detalle` (detalle técnico en bloque secundario) + variantes dark mode.

#### §2 — Casilla opt-in `notificar` (C16)

- Nuevo checkbox en `Upload.jsx` **junto al campo de correo**: *"Enviar observaciones por correo al estudiante"*.
- **Habilitada solo con correo válido** (sin correo no hay notificación posible): si el operador borra o invalida el correo, la casilla se desmarca y deshabilita.
- En `validate()`: `if (notificar && correo && esCorreoValido(correo)) form.append('notificar', 'true')` — el backend interpreta la ausencia como `false` (default).
- Envío efectivo solo si se cumplen **todas**: `notificar=true`, correo válido, semáforo rojo y SMTP habilitado en el servidor → así el estudiante no recibe correo por validaciones intermedias.
- CSS `.check-notificar` (incl. estados `disabled`, `focus-visible`, dark mode); `mockups/carga.html` sincronizado (casilla + lógica mínima que la habilita con correo válido).
- Docs actualizados: `01_requisitos_interfaz.md` (RF-26 nuevo; RF-12 y RF-20 ajustados), `03_wireframes.md` (bloque correo + casilla en escritorio ×3 y móvil), `README.md` (flujo y estado actual).

#### Verificación

- Backend del PR #37 en `:8001`: con correo → `{"estado":"deshabilitado","detalle":null}` (SMTP apagado); sin correo → `{"estado":"sin_correo"}`.
- Backend `master` en `:8000`: acepta el campo extra `notificar` sin romperse (HTTP 200, sin `notificacion` → la UI no muestra badge).
- Proxy Vite `:5173` → `:8000`: 200 (docx), 415 (.txt), 422 (correo inválido) — todos con `detail` español.
- `npm run build` OK; `pytest` 192 passed / 21 skipped (re-verif. 2026-10-06: 223 passed, 21 skipped tras #37–#39).

---

### Cuarta tanda — Auditoría UX integral (opción 3, C17–C29)

Se pidió comparar tres opciones de mejora de la interfaz y se aplicó la completa, con una auditoría automatizada (`explore`) sobre `App.jsx`, `Upload.jsx`, `Report.jsx`, `index.css` y `mocks.js`.

#### 3 bugs de alta severidad

- **C17 — modo oscuro inoperante**: el JS aplicaba la clase `.dark` pero el CSS solo escuchaba `@media (prefers-color-scheme)`, así que el botón no cambiaba nada y la preferencia no persistía. Se agregó `temaOscuroInicial()` (localStorage `vb-tema` → `matchMedia`) aplicado en `main.jsx` **antes del primer render**, `DarkModeToggle` con `aria-pressed`, y se eliminó el bloque `@media` para que `.dark` sea la única fuente de verdad.
- **C18 — semáforo verde por defecto**: `data?.semaforo || 'verde'` podía pintar paloma sobre un reporte caído → fallback seguro (solo `verde` explícito).
- **C19 — mock incoherente**: `resumen.total = 47` contra 13 resultados listados → KPIs calculados de `MOCK_RESULTADOS` (13/2/2).

#### Accesibilidad y móvil

- **C20–C22**: regiones y anuncios `aria-live` (`sr-only role=status`) para validación, filtros, búsqueda, copiado y carga de reporte; dropzone operable con teclado (`role=button`, Enter/Espacio) con foco de retorno al cerrar errores; foco al título del reporte al montar.
- **C23–C24**: contraste AA (`--ambar` `#b26a00`→`#9c5700` = 5.56:1, subtítulo del header, microtexto `.72rem`) y targets ≥44 px (chips, `btn-vista`, tema, quitar, cerrar, seleccionar, `summary`).
- **C25**: primera `@media (max-width:599px)` — header envolvente, corte del nombre de archivo, chips con scroll horizontal (exigido por el wireframe S2) y controles apilados.

#### Microcopy, features y tooling

- **C26**: errores como objetos `{titulo, texto}` (formato, peso, HTTP del servidor, correo) en vez del "No se pudo validar." genérico; fallo de clipboard visible en el botón; botón "Validar otro archivo" duplicado del header eliminado.
- **C27–C28**: se implementaron las dos piezas del wireframe S2 que nunca existieron — **barra de progreso de cumplimiento** (`role=progressbar`, 3 segmentos + "X de 47 reglas cumple (Y%)") y **campo "Buscar regla o mensaje…"** que filtra ambas vistas con anuncio de resultados.
- **C29**: `npm run lint` no ejecutaba (eslint sin configuración) → `.eslintrc.cjs` con `eslint:recommended` + `plugin:react` + `plugin:react-hooks` (`rules-of-hooks` y `exhaustive-deps` activos).

#### Verificación (2026-10-06)

- `npm run lint` → 0 errores · `npm run build` → OK (166.48 kB JS / 16.48 kB CSS).
- `pytest` → 223 passed, 21 skipped · `scripts/e2e_flujo_completo.sh` → **11/11 ✅** (`resultados_vistobueno/S7_pruebas_usabilidad/evidencias/e2e_run.log`).
- Commit `df05bd6` (rama `s7-auditoria-ux`) → PR [#41](https://github.com/retblast/vistobueno/pull/41) (abierto).

---

### Quinta tanda — Fase A de la revisión integrada (C30–C38)

Se ejecutó la fase A del plan propuesto en `resultados_vistobueno/INFORME_REVISION_INTEGRADA.txt` (revisión exhaustiva del 07/10 que identificó 33 hallazgos en total). Se aplicaron los 8 puntos del frontend sobre la rama `s7-auditoria-ux`:

- **C30 (F1)**: `npm run lint` ahora cubre `.jsx` (`eslint . --ext .js,.jsx`) → 0 errores y 0 warnings **reales** (antes el lint silenciosamente ignoraba los componentes); se corrigieron el import muerto de `MOCK_REPORT` y las dependencias de `handleFiles`.
- **C31–C33 (F2–F4) dark**: `--ambar: #ffb74d` dentro de `.dark` (el valor de claro daría ~2.5:1 sobre el fondo oscuro), `.dark .chip.on` para que el chip activo conserve el resaltado verde, y `color-scheme: dark` para que el placeholder nativo del buscador sea legible.
- **C34–C35 (F5–F6) aria-live/buscador**: el anuncio ahora cuenta solo las filas visibles de la vista actual (`cuentaVisible`) y va con debounce de 350 ms (sin spam al teclear); el buscador también filtra la sección "Cómo preguntar a una IA" (`promptsVisibles` con `useMemo`).
- **C36 (F7)**: el mock de demo pasó de `notificacion.enviado` a `no_solicitado` — la demo ya no afirma envíos inexistentes.
- **C37–C38 (F8)**: re-elegir el mismo archivo ahora dispara `change` (reset del input), el foco vuelve a la dropzone al regresar desde el reporte, validador y constantes a nivel de módulo, rama muerta de correo fuera; limpieza de 29 selectores `[data-theme]` muertos, `--tinta`, `.der-header` e import sin uso; `favicon.svg` real (antes 404).

#### Verificación (2026-10-07)

- `npm run lint` → **0 errores / 0 warnings** · `npm run build` → OK (162.66 kB JS / 15.78 kB CSS + chunk `mocks`).
- `pytest -o addopts=""` → 223 passed, 21 skipped · `scripts/e2e_flujo_completo.sh` → **11/11** (`resultados_vistobueno/S7_pruebas_usabilidad/evidencias/e2e_run.log`).
- CSS servido verificado en `:5173`: sin `data-theme`, con `.dark --ambar: #ffb74d`, `color-scheme: dark` y `.dark .chip.on`; `/favicon.svg` → 200.
- Commit `d306f36` + `4c9cc55` pushados 2026-10-07 a `Rodo00/vistobueno`: rama `s7-auditoria-ux` (PR #41 ahora con 4 commits, mergeable) y `master` del fork actualizado a `d05d8e1` (upstream `e98ea7a` + C17–C38 + workflows propios `Main.yml`/`main.yml`).

---

### Sexta tanda — Observaciones de la revisión independiente (Arreglos.txt v4)

El revisor probó el PR por su cuenta (CI 2/2 verde, lint/build/pytest locales, merge de prueba contra `e98ea7a` sin conflictos) y dejó dos observaciones no bloqueantes, ejecutadas el 07/10:

- **C39 (obs 1)**: `scripts/e2e_flujo_completo.sh` se citaba como evidencia (11/11) pero no existía en el repo → **versionado canónico** en `scripts/e2e_flujo_completo.sh`: `ROOT` autodetectado desde la ubicación del script (antes hardcodeado) e intérprete `.venv`/`python3` portable. La copia de `resultados_vistobueno/` quedó como wrapper hacia el canónico (la referencia documentada sigue funcionando). Verificado: E2E **11/11** vía wrapper (`evidencias/e2e_run.log`, 2026-10-07). Commit `21d0ac3` (PR #42).
- **C40 (obs 2)**: el PR agregaba ESLint pero el CI no ejecutaba `npm run lint` → **PR separado [#43](https://github.com/retblast/vistobueno/pull/43)** (`ci-frontend-lint`, `abac6b6`): paso aditivo `Lint frontend (eslint)` en el job `frontend` (reutiliza `node_modules`, no toca pasos existentes), más la config que la base `e98ea7a` necesita (`.eslintrc.cjs`, `--ext .js,.jsx`, `eslint-plugin-react-hooks`) y el fix del import `MOCK_REPORT` sin uso para que el paso nazca verde (mismo hallazgo C30). Los 3 warnings restantes los cierra la Fase A (#42). **Pendiente de aprobación del equipo** (AGENTS: todo cambio al CI verde en su propio PR).

#### Verificación (2026-10-07)

- Rama `ci-frontend-lint`: `npm run lint` → 0 errores (exit 0; 3 warnings no bloqueantes) · `npm run build` → OK.
- Rama `s7-auditoria-ux`: E2E **11/11** con el script versionado (`scripts/e2e_flujo_completo.sh`).

---

### Séptima tanda — Arreglos.txt v5 (C41): badge de `deshabilitado` con nota de configuración

El backend (v1.4 del contrato) ahora llena `notificacion.detalle` también cuando `estado=deshabilitado` — una nota de configuración para administradores (`CONTRATO_API.md`: *"Mostrar detalle como nota de configuración para administradores"*); antes el campo venía `null` y la UI no tenía nada que mostrar. La parte visual queda de este lado (**C41**, `Report.jsx`):

- `badgeNotificacion()` suma el caso `deshabilitado`: **solo** si el backend envía `detalle` muestra un badge informativo (clase `info`, junto a `no_solicitado`) con el texto *"El envío de correos no está habilitado en el servidor."* y la nota de configuración en `.badge-notif-detalle` (mismo estilo que el detalle de `fallo`). Sin `detalle` (backend anterior o respuesta incompleta) no se muestra nada, como hasta ahora — el cambio es aditivo y backwards-compatible.
- `sin_observaciones` sigue sin badge.
- `docs/diseno/01_requisitos_interfaz.md`: RF-20 y la tabla del reporte actualizadas con el nuevo comportamiento.

#### Verificación (2026-10-09)

- Backend en `:8000` (post-merge de upstream): `POST /validar` con `correo` + `notificar=true` + semáforo rojo → `{"estado":"deshabilitado","detalle":"El servidor no tiene la notificación habilitada: configure VISTOBUENO_NOTIFICACIONES=1 y VISTOBUENO_SMTP_HOST."}`.
- UI en `:5173` (Playwright): badge azul visible con texto + nota de configuración (evidencia en `resultados_vistobueno/S7_pruebas_usabilidad/capturas/14_deshabilitado_nota.png`, local).
- `npm run lint` → 0 errores/0 warnings · `npm run build` → OK.

#### Revisión del PR #48 — comentarios aplicados (2026-10-09)

El revisor marcó el PR como "Verificado" y dejó 4 comentarios no bloqueantes; se aplicaron los 4:

1. **README** no listaba `sin_observaciones` ni `deshabilitado` → commit `docs: sincronizar estados de notificacion en README` (`2def0f1`, aparte como pidió el revisor).
2. **Cabecera de `badgeNotificacion()`** decía "v1.3.0" → aclarada como v1.3.0 + `deshabilitado` detalle v1.4 (`3315231`).
3. **Texto del badge solapado con el detalle del backend** → el texto principal ahora es solo el marco *"Nota para administradores:"* y el `detalle` del backend aporta la frase completa con las variables de entorno (`85296b1`).
4. **Sin test automatizado de `badgeNotificacion()`** → se exportó la función y se agregó **vitest** como primer runner de tests del frontend (`npm test`): `Report.badgeNotificacion.test.js` con **10 tests** — los 6 estados del contrato, backwards-compatibilidad (`deshabilitado`/`fallo` sin detalle, `sin_observaciones`), payload inválido y trim del detalle (`8b8ddce`). *Pendiente de equipo: agregar `npm test` al job `frontend` de `ci.yml` en un PR aparte (precedente C40).*

---

### Novena tanda — Arreglos.txt v7 (2026-10-12): carga, estados y pulido

`Arreglos.txt` se reemplazó por una lista nueva de 3 puntos (sin numeración de observaciones):

1. **Reducir el área de carga, mejorar las etiquetas y hacer más visible el botón «Validar documento».**
   - Dropzone compacta: `padding 2rem→1.1rem` (tablet `3rem→1.3rem`, móvil `→.9rem`); icono más pequeño.
   - Etiquetas reescritas: *"Arrastre aquí su documento .docx"*, *"o selecciónelo desde su equipo"*, *"Examinar archivos"*, nota *"Formato .docx · Tamaño máximo: 10 MB"*.
   - El botón pasó de estar dentro del chip del archivo (texto `Validar ✦`) a **acción principal `.acciones-form` siempre visible, a todo el ancho y 48 px de alto**, con `box-shadow`; se deshabilita sin archivo/correo inválido con ayuda contextual (`#validar-ayuda`, `aria-describedby`).
2. **Implementar los estados de archivo seleccionado, inválido, procesamiento y error.**
   - `Upload.jsx` calcula `estado ∈ {vacio, seleccionado, invalido, procesando, error}` y lo pinta en la dropzone (`estado-*`): check verde, cruz roja, spinner grande o icono de documento.
   - `error.tipo` separa `archivo` (validación del cliente, mensaje *dentro* de la dropzone con `role=alert` y foco ahí) de `servidor` (aviso rojo cerrable debajo, como antes).
   - Estados documentados en `docs/diseno/03_wireframes.md` y en la tabla de funcionalidades de `01_requisitos_interfaz.md`.
3. **Pulir tipografía, modo oscuro, adaptación móvil y accesibilidad.**
   - `line-height: 1.45` + antialiasing en `body`; `h1–h3` con `letter-spacing -.01em`; `.card h2` con tamaño/tono propio (1.05/1.15/1.3 rem por breakpoint).
   - Dark: variantes de los 5 estados de la dropzone, botón deshabilitado con borde, `h2` claro y spinner en verde AA.
   - Móvil: dropzone compacta, `Examinar archivos` y `Validar documento` a todo el ancho (52 px), `h2` más pequeño.
   - Accesibilidad: `aria-busy` en la dropzone, `role=alert` vs `role=status` según estado, foco al dropzone al rechazar un archivo, `prefers-reduced-motion` (spinner lento, sin transiciones ni desplazamientos), iconos **SVG inline** en lugar de emoji (render igual en todos los SO y en capturas headless).

#### Verificación (2026-10-12)

- `npm run lint` → 0 errores/0 warnings · `npm test` → **10/10** · `npm run build` → 164.62 kB OK.
- **E2E completo 9/9** (`scripts/e2e_flujo_completo.sh`): 200/49 reglas, 415, 422, `deshabilitado`, `no_solicitado`, mock 500.
  - Corrección colateral: la aserción `total==47` del script quedó obsoleta tras el PR #46 del backend (hoy 49) → cambiada a `>=47`.
- 9 capturas de estados (vacío ×3, seleccionado ×2, inválido ×2, procesando, error 413) en `resultados_vistobueno/S7_pruebas_usabilidad/capturas/`.

---

### Décima tanda — Prompt único en «Cómo preguntar a una IA» (2026-10-12)

Petición directa: *«en la sección de preguntar a la IA, crea una sección donde se junten todos los prompts en uno solo listo para copiar y pegar, a parte de los que ya están»*.

- **`Report.jsx`**: función `construirPromptUnico(prompts)` (exportada y testeada) que une los prompts visibles en UNO solo:
  - marco general (*"… con N problemas de formato. Corrige todos los siguientes problemas en Microsoft Word, sin afectar el resto del formato…"*; singular cuando hay 1),
  - un bloque numerado por problema (`════ Problema i de N · Categoría ════`) con el prompt individual **íntegro** (sin recortes ni reescritura),
  - entradas sin texto se ignoran y no cuentan en el total; categoría desconocida → `Otros` (igual que las tarjetas).
- **UI** (arriba de las tarjetas, dentro de la misma card): título, botón **«Copiar todo junto»** (mismos estados `¡Copiado!`/fallo que los prompts individuales, `aria-live` incluido), recuento de prompts visibles y `<details>` *"Ver el prompt completo"* con vista previa desplegable (`max-height` con scroll). Respeta el **filtro de búsqueda** de la sección (si el operador filtra, el prompt único une solo los visibles).
- **CSS**: `.ia-unico*` con borde verde, fondo `--gris-claro`, título/summary en verde-oscuro; dark con verde AA `#81c784` (el `#2e7d32` da ~2.3:1 sobre `#242424`); móvil con botón a todo el ancho; tablet con tipografía ampliada.
- **Docs**: RF-27 + funcionalidad 10b (`01_requisitos_interfaz.md`), wireframe ASCII y bullets (`03_wireframes.md`), README (flujo + estado actual).
- **Tests**: `Report.promptUnico.test.js` — **6 tests** (listas vacías/inválidas, filtrado de entradas sin prompt, marco singular/plural, integridad y orden de cada prompt, `Otros`).

#### Verificación (2026-10-12)

- `npm run lint` → 0 errores · `npm test` → **16/16** (10 badge + 6 prompt único) · `npm run build` → 166.10 kB / CSS 19.63 kB OK.
- E2E del flujo con Playwright: validación real (49 reglas), clic en «Copiar todo junto» → botón `¡Copiado!` y **portapapeles con 24.323 caracteres** verificados.
- 4 capturas (claro con copiado confirmado, con el desplegable abierto, oscuro y móvil) en `resultados_vistobueno/S7_pruebas_usabilidad/capturas/` (`19`–`22`).
- **CI (Arreglos.txt del 12/10)**: paso **`Test frontend (vitest)`** agregado al job `frontend` de `ci.yml` (`nix develop --command sh -c "cd frontend && npm run test"`), reutilizando `node_modules` del paso de build igual que el lint; aditivo, sin tocar pasos existentes. *El archivo indicaba `--comand` (typo): se usó `--command`, la flag real de nix, consistente con los pasos vecinos.*

---

### Undécima tanda — Revisión de código propia: edge-cases de robustez (2026-10-13)

Diagnóstico pedido sobre el área (Upload/Report/App/CSS/E2E): sin errores graves; se implementaron los edge-cases acordados (lote «bugs + quick wins»):

- **`Upload.jsx`**:
  - drop/cambio de archivo **ignorado durante «procesando»** (`cargandoRef`): la selección ya no cambia bajo un resultado que corresponde al archivo anterior;
  - **guard síncrono anti doble clic** en `validate` (el estado `loading` llegaba tarde para dos clics en el mismo tick);
  - **timeout de 30 s** con `AbortController` → banner *El servidor tardó demasiado* (tipo servidor; **no** cae al mock: el servidor puede estar vivo pero colgado);
  - input file oculto con `tabIndex={-1}` + `aria-hidden="true"` (desaparece la parada de tabulación invisible que dejaba la técnica `clip`);
  - `role="alert"` del texto principal de la dropzone **solo** para error de archivo (el error de servidor ya tiene su banner `role=alert`: se anunciaba dos veces).
- **`Report.jsx`**:
  - concordancia singular/plural en el contador del prompt único («con 1 prompt visible…»);
  - `scrollIntoView` respeta `prefers-reduced-motion` vía `matchMedia` (el CSS reducido no cubre la API JS).
- **`scripts/e2e_flujo_completo.sh`**: mensaje de aserción honesto del paso 9 (`esperaba 500, vino …`, antes imprimía el valor recibido como si fuera el esperado) y texto del paso 1/9 sin el «0 skipped» falso.

#### Verificación (2026-10-13)

- `npm run lint` → 0 errores · `npm test` → **16/16** · `npm run build` → 166.69 kB / CSS 19.63 kB.
- E2E completo → **11/11** (pytest 399 passed, 49 reglas, 415/422, deshabilitado/no_solicitado, 500→mock).

Commits: `8296055` (Upload), `9b406dd` (Report), `817507b` (script E2E) → rama `s7-fixes-review`.

---

### Duodécima tanda — Incoherencias con el backend (contrato v1.5) (2026-10-13)

Diagnóstico cruzado backend↔frontend (api.py/api_models.py/CONTRATO_API.md contra Upload/Report/mocks): el frontend había quedado consumiendo el contrato v1.4 mientras el backend sirve el v1.5 (aplicabilidad de reglas por tipo de documento). Hallazgos y fixes del lado del frontend:

- **Bug grave — reglas no aplicables pintadas como cumplidas**: las 9 reglas que no aplican al tipo detectado llegan con `paso:true, aplicable:false` y la checklist las mostraba como «✓ Cumple», el KPI decía «Reglas evaluadas: 49» cuando se evaluaban 40, y la barra inflaba el % (caso vivo: 33% mostrado vs 17.5% real) — justo lo que la decisión 5 de `docs/diseno/15_tipo_documento_grupos.md` quería evitar. Fix: helper `filtrarAplicables()` (exportado, testeado) + KPI/barra/anuncios sobre `total_evaluadas` + nota «N reglas no aplican a este tipo de documento».
- **9 `rule_id` sin categoría** (suite DSL ampliada, PRs #45/#46) caían a «Otros»: mapeadas a Índice (3), Encabezados y pies (2), Notas al pie, Carátula (línea de investigación) y Tipo de documento (2, incluida la sintética `tipo_documento_no_determinado`).
- **`metadatos` invisible**: el reporte ahora muestra archivo (nombre/tamaño) y tipo de documento detectado (`vigente` / `sin_determinar` honesto / `contradictorio` como aviso ámbar).
- **`ubicacion` sin uso**: cada regla fallida muestra su referencia al reglamento («Ref.: …») cuando el backend la envía.
- **Correo**: `strip()` en el cliente antes de validar/enviar (el backend lo hace; un espacio pegado ya no da falso error inline).
- **Mock alineado al contrato v1.5** (aplicable, total_evaluadas, reglas_no_aplicables, metadatos, un ejemplo no-aplicable) y **E2E con aserciones v1.5** (`aplicable` presente, `total ≥ total_evaluadas`, coherencia de `reglas_no_aplicables`, `tipo_documento_estado` válido).

**Coordinación pendiente con Integrante 1** (notificado en el PR, no tocado `validator/`): (a) `api.py` no tiene `CORSMiddleware` mientras los docs del frontend sugieren `VITE_API_URL` cross-origin — o se agrega CORS o se restringe a same-origin/reverse proxy; (b) decisión sobre el timeout de 30 s del cliente vs peor caso del servidor (validación CPU + SMTP hasta 10 s: el correo podría salir tras el aborto del frontend).

#### Verificación (2026-10-13)

- `npm run lint` → 0 errores · `npm test` → **20/20** (16 + 4 nuevos de `Report.aplicabilidad.test.js`) · `npm run build` → OK.
- E2E completo → **11/11** con las aserciones v1.5 nuevas (total 49 / evaluadas 40 coherentes).
- Respuesta viva del backend verificada antes/después: KPI pasa de 49 a 40 evaluadas y la nota informa las 9 no aplicables.

---

### Decimotercera tanda — Contrato v1.6: ficha de depósito DSpace en la UI (2026-10-21)

Actualización de `upstream/master` con el módulo de depósito en DSpace del equipo (Actividad 10, contrato v1.6.0 ya vivo en `POST /validar`) y el PR #49 de Ivan (Integrante 3). Revisión general y soporte de UI:

- **Ficha de depósito (`Upload.jsx`)**: sección plegable «Depositar en el repositorio digital (opcional)» con la casilla opt-in `depositar` y los metadatos del ítem (título, autores, asesor, resumen, palabras clave). **Título y autores son obligatorios en el cliente** (`fichaIncompleta()`, exportada + 4 tests): sin ellos el alta llegaría hasta DSpace y fallaría con un 422 que el operador vería tarde. El botón «Validar documento» se deshabilita con ayuda contextual si la ficha está incompleta (mismo patrón que el correo).
- **Badge de depósito (`Report.jsx`)**: `badgeDeposito(deposito, semaforo)` (exportada + 8 tests) con los 5 estados del contrato: `enviado` (cola de aprobación), `fallo` (detalle técnico), `no_apto` (solo verdes), `deshabilitado` (nota para administradores, solo con `detalle`) y `sin_solicitud` — que **solo** ofrece la casilla cuando el semáforo es verde (con rojo sería ruido).
- **Timeout dinámico**: con depósito solicitado el cliente espera 90 s en vez de 30 (el backend suma SMTP ~10 s + alta DSpace ~30 s por solicitud: abortar en 30 s dejaría un depósito que el servidor terminaría igual — mismo problema anotado para Int1 en el PR #54).
- **Regla nueva del motor (PR #49)**: `track_changes_sin_resolver` mapeada a la categoría «Control de cambios» (antes habría caído a «Otros»).
- **Mock y E2E alineados al v1.6**: mock con `deposito.sin_solicitud`; paso 5 assertciona el campo y nuevo paso 8c verifica `depositar=true → no_apto` con semáforo rojo (12 checks ahora).

**Módulo de IA (PR #49 de Ivan)**: el motor está completo (`validator/llm.py` + `asistente.py`, Func 1/2/3/5 con `StubLLM`), pero los endpoints `/asistente/*` aún no existen — el handover (`docs/HANDOVER_API_IA.md` §2.2/§6) los deja como pendiente de Integrante 1. **La UI de los botones del asistente queda bloqueada hasta ese wiring**; cuando existan, seguirá los DTOs ya acordados (`EstadoAsistenteAPI`, `ExplicacionYPrioridadAPI`, sección separada «Revisión semántica» desconectada del semáforo).

#### Verificación (2026-10-21)

- `npm run lint` → 0 errores · `npm test` → **32/32** (20 + 8 badgeDeposito + 4 ficha) · `npm run build` → 172.99 kB.
- E2E completo → **12/12** (pytest 545 passed; total 50 reglas / 41 evaluadas; `deposito.estado: no_apto` verificado en vivo con `depositar=true`).

---

## Evidencias

- Commits: `e27e683` (mejoras IHC), `7bd0be4` (Arreglos.txt v1), `5c169ef` (v2), `6c512ec` (v3), `df05bd6` (auditoría UX C17–C29), `d306f36` + `4c9cc55` (Fase A revisión, C30–C38), `21d0ac3` (script E2E versionado, C39), `abac6b6` (lint en CI, C40, rama `ci-frontend-lint`).
- PRs: https://github.com/retblast/vistobueno/pull/41 · https://github.com/retblast/vistobueno/pull/42 · https://github.com/retblast/vistobueno/pull/31 · https://github.com/Rodo00/vistobueno/pull/10
- Archivos: `frontend/src/components/Upload.jsx`, `Report.jsx`, `frontend/src/index.css`, `frontend/src/mocks.js`, `frontend/src/App.jsx`, `frontend/vite.config.js`, `frontend/.env.example`, `README.md`, `docs/diseno/01_requisitos_interfaz.md`, `docs/diseno/03_wireframes.md`, `mockups/carga.html`, `mockups/reporte.html`.

---

## Relación con competencias curriculares

| Competencia | Evidencia |
|-------------|-----------|
| **Interacción Humano-Computador** | Evaluación IHC, correcciones de usabilidad, pruebas de flujo, documentación de avances. |
| **Ingeniería de Software II** | Separación de manejo de errores (red vs HTTP), documentación de configuración de despliegue. |

---

## Dificultades y aprendizajes

- Distinguir **error de red** vs **respuesta HTTP con detalle** evita ocultar fallos reales del backend detrás del modo demo.
- El proxy de Vite **no existe** en build estático: hay que documentar `VITE_API_URL` o reverse proxy desde el inicio.

---

## Plan siguiente

- **2026-10-09**: el equipo fusionó los PRs de frontend — [#41](https://github.com/retblast/vistobueno/pull/41) (`be33d60`, C17–C39) y [#43](https://github.com/retblast/vistobueno/pull/43) (`dd76185`, lint de frontend en el CI); [#42](https://github.com/retblast/vistobueno/pull/42) cerrado (subsumido por #41).
- **C41** (Arreglos.txt v5) en PR propio desde `upstream/master`; integrar feedback si lo hay.
- Tag `v0.7.0` pendiente de creación; fases B/C/D de la revisión pendientes de asignación (el backend ya avanzó con #46).
