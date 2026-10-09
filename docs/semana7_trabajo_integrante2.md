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
