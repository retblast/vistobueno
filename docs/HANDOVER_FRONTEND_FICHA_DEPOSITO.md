# Handover: UI de la ficha de depósito (frontend, Semana 8)

**Fecha**: 2026-10-23
**De**: Integrante 1 (Backend/API)
**Para**: Integrante 2 (Frontend)
**Estado**: pedido con especificación — el diseño de pantallas es tuyo
**Contexto de producto**: `docs/PLAN_FICHA_DEPOSITO.md` (leer primero;
v0.2 congelado). Contrato: `docs/CONTRATO_API.md` (v1.7.0).

---

## 1. El problema en una frase

El backend ya entrega la ficha detectada, el buzón que habla con el
userscript, la constancia y el registro descargable; falta la **pantalla
que une todo**: revisar la ficha, prepararla, esperar el handle y
descargar el papeleo.

Todo el backend está en `semana8-deposito-ficha` (PR #55) con suite
verde; el flujo completo está verificado de punta a punta con
`nix run .#test-ficha-deposito` (sin navegador: el driver corre el
userscript real contra el mock).

## 2. Qué se pide, pantalla por pantalla

### 2.1 Ficha de depósito (solo con semáforo verde)

La respuesta de `POST /validar` trae `ficha_deposito` **solo en verde**
(en rojo es `null` y la pantalla no existe). Dos grupos:

- `extraidos` (8 campos, editables — el operador corrige lo que el
  motor detectó):
  | Campo | Cómo llega | UI sugerida |
  |-------|-----------|-------------|
  | `dc.title` | texto completo (HOY llega con el prefijo "Título del trabajo de investigación:" — ver §6; el operador lo recorta) | input largo |
  | `dc.contributor.author` | lista (1-2 autores) | lista editable |
  | `dc.contributor.advisor` | texto | input |
  | `dc.description.abstract` | texto completo | textarea |
  | `dc.subject` | lista | chips/lista editable |
  | `dc.date.issued` | "2026" (solo año) | input corto |
  | `escuela` | texto | input |
  | `renati.juror` | `detectado=false` siempre (captura no confiable) | opcional, a mano |
  | Con `detectado=false` el `valor` viene `null`: campo vacío editable. |
- `manuales` (4 campos, vacíos — el operador los teclea UNA vez):
  `matricula` y `renati.author.dni` aceptan **lista alineada por
  posición con los autores** (una por estudiante; las tesis con dos
  autores generan dos constancias y dos filas), `renati.advisor.dni` y
  `renati.advisor.orcid` son únicos.

Sugerencia: resguardar la ficha editada en `localStorage` (refrescar la
página no debe perder el trabajo del operador). Sin persistencia en el
servidor: es un resguardo de cliente.

### 2.2 Botón "Preparar depósito"

`POST /ficha-pendiente` con la ficha editada (el mismo objeto
`extraidos` + `manuales`, tal cual llegó en la respuesta de /validar).
Respuesta 204. Desde ese momento el userscript (en el navegador del
operador, sobre las páginas de DSpace) puede leer la ficha del buzón.

Nota operativa: el buzón tiene **una sola ranura con TTL de 1 hora** —
preparar de nuevo reemplaza la ficha anterior ("última gana"). Si la
API se reinicia, el buzón se vacía: re-preparar.

### 2.3 Panel de espera ("Esperando el depósito…")

Sondear `GET /deposito` cada ~3 s mientras el panel esté abierto:

- **404** = aún no hay nada: seguir esperando, en silencio (no es error).
- **200** = el userscript reportó el depósito: `{handle, titulo,
  timestamp}`. Cotejar `titulo` contra la ficha preparada (normalizar:
  minúsculas sin acentos, comparar por inclusión — el título del ítem
  puede traer ediciones menores). Si NO coincide: mostrar el recibido
  con el botón de aceptar/rechazar — nunca usarlo a ciegas.

Al recibir: mostrar handle, fecha y hora (derivar del `timestamp`,
editables por si el operador quiera corregir).

### 2.4 Panel de papeleo

- **Constancias**: `POST /constancia` con `{ficha, handle, timestamp,
  indice_autor}` — UNA DESCARGA POR AUTOR (iterar `indice_autor` 0..N-1).
  La respuesta es el `.docx` binario (attachment con el nombre del autor).
  Con `?formato=zip` devuelve un **paquete por autor** con la constancia
  .docx y su fila del registro como `registro.csv` — una descarga = todo
  el papeleo del estudiante (sugerido como opción "Descargar todo").
- **Registro**: `POST /fila-registro` con `{ficha, handle, timestamp}`:
  - `formato=json` (default): `{"filas": ["\tTesis…", …]}` — para el
    botón "copiar fila" al portapapeles.
  - `?formato=tsv | csv | xlsx`: **archivo descargable** directo al
    disco (Excel/LibreOffice lo abre con las columnas sanas).
  - Una fila por autor, mismo handle.
- Los errores llegan como `{"detail": "…"}` en español y nombran
  exactamente el dato faltante ("Faltan 1 matrícula(s)…"); muéstralos,
  no los tragues.

## 3. Errores que sí verás en la operación

| HTTP | Cuándo | UI |
|------|--------|-----|
| 422 | falta un dato de la ficha / índice fuera de rango / timestamp mal | mostrar `detail`, volver a la ficha |
| 500 | `VISTOBUENO_FIRMA` sin configurar, plantilla ausente | mostrar `detail` como nota de configuración |

## 4. Lo que NO se pide

- Sin CORS, sin auth, sin escribir el XLSX oficial (el operador pega la
  fila o copia del archivo descargado — decisión congelada del plan §3).
- Sin llamadas del frontend a DSpace: el mundo DSpace es del userscript
  (`tools/dspace-fill/`, ya construido y probado).
- Sin modificar el backend: si algo del contrato molesta, me lo dices y
  lo discutimos antes de tocar `api.py`.

## 5. Verificación que te pido

- Tests del frontend (vitest) para: ficha solo en verde, manuales por
  autor, sondeo con 404 silencioso, cotejo de título, N descargas.
- Prueba manual con la API real: `nix run .#test-ficha-deposito`
  demuestra el flujo completo sin navegador (buzón incluido); tu
  pantalla se prueba contra la misma API (`nix run .#serve`), con la
  ficha del doc bueno publicada a mano si quieres sondear el panel.
- El checklist del ensayo general manual está en
  `tools/dspace-fill/dev/mock-dspace/README.md`.

## 6. Pendiente conocido (no te frene)

El motor entrega `dc.title` con el prefijo de la etiqueta de carátula
("Título del trabajo de investigación: …"). Está pedido su pulido al
motor (nota de seguimiento en el handover de Int3); mientras tanto el
operador lo recorta en tu pantalla — es el caso `detectado=true` con
texto editable, así que no requiere nada especial de tu lado.

## 7. Después de tu parte

El piloto real con el operador (borrador descartable en la instancia,
checklist firmado) — el ensayo general local ya corre solo con
`nix run .#test-ficha-deposito`.
