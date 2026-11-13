# Plan de lotes previos al piloto — Integrante 1 (Backend / API)

> **Estado**: en ejecución. Lotes 1 a 6 cerrados; el piloto real (Actividad 16) y el cierre de hallazgos (Actividad 17) quedan fuera de este plan.
> **Fecha de creación**: 2026-11-04.
> **Alcance**: todo el trabajo de Integrante 1 que se puede cerrar **sin** la
> presencia del operador de la biblioteca. El piloto real (Actividad 16) y el
> cierre de la Actividad 17 dependen de la sede y quedan fuera.
>
> **Origen**: este plan recupera la hoja de ruta acordada con el equipo el
> 2026-11-04 ("todo lo que no requiere el piloto, por lotes"). Vive en el
> repositorio para que no dependa de la memoria de una sesión.

---

## Por qué existen estos lotes

El piloto es el último tramo del ciclo y necesita material que hoy no
existe: un documento de demostración con su respuesta, una propuesta de
registro, la verificación del frontend contra la API real, un kit que el
operador pueda seguir paso a paso y un ensayo completo contra el mock de
DSpace. Todo eso se puede preparar y verificar sin la sede.

Cada lote es pequeño, tiene una compuerta (gate) y sale en su propio PR.
Ninguno toca `master` directamente.

## Cerco de alcance

**Dentro de estos lotes:**

- puesta al día de la documentación;
- registro propuesto de documentos de la sede (Actividad 14);
- verificación del frontend (Actividad 15);
- kit del piloto y borrador de coordinación;
- ensayo completo contra el mock;
- cierre de las evidencias de la semana 10.

**Fuera de estos lotes:**

- piloto real con el operador (Actividad 16);
- cierre de hallazgos del piloto y versión final (Actividad 17);
- cableado de la API de IA (`docs/HANDOVER_API_IA.md`);
- exponer `formato` en `POST /validar` (backlog P3);
- correcciones de motor de Int3 y retiro de marcas `xfail`.

---

## Mapa de lotes

| Lote | Entrega | Estimación | Compuerta | Estado |
|---|---|---|---|---|
| 1 | Puesta al día de la documentación | 45 min | `nix flake check`, sin versiones viejas | **cerrado** (PR #76) |
| 2 | Registro propuesto de la sede (Act. 14) | 30 min | sin datos personales, enlaces resueltos | **cerrado** (PR #77) |
| 3 | Verificación del frontend (Act. 15) | 1–2 h | tests, lint, build y checklist de navegador registrado | **cerrado** (PR #79) |
| 4 | Kit del piloto y borrador de coordinación | 1–2 h | checklist ejecutable, sin datos personales | **cerrado** (PR #80) |
| 5 | Ensayo completo contra el mock | 1–2 h | flujo completo OK, sin drift en `dist` | **cerrado** (PR #81) |
| 6 | Cierre de evidencias de la semana 10 | 30 min | registro de regresión y de PRs completo | **cerrado** (PR #82) |

---

## Lote 1 — Puesta al día de la documentación

**Objetivo:** que la documentación describa el producto actual antes de que la
sede la lea.

**Archivos:** `README.md`, `docs/CONTRATO_API.md`,
`docs/HANDOVER_API_TIPO_DOCUMENTO.md`,
`docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md`,
`docs/diseno/00_indice_diseno.md`, `docs/FLUJO_API.md`,
`docs/HANDOVER_AUDITORIA_2026-10-26.md`, `docs/PLAN_FICHA_DEPOSITO.md`.

**No tocar** `AGENTS.md` sin aprobación del responsable del repositorio.

**Compuerta:**

```bash
git diff --check
rg -n "547 tests|693 tests|contrato v1\.7\.0|checklist de 10 pasos" README.md docs/
nix flake check
```

**Estado:** cerrado. PR #76 (`931644e`, `707dc6f`), mergeado el 2026-11-04.

---

## Lote 2 — Registro propuesto de la sede (Actividad 14)

**Archivo nuevo:** `docs/REGISTRO_DOCUMENTOS_SEDE.md`.

La actividad 14 pide una **propuesta de estructura** para registrar los
documentos que aporte la sede, no el registro lleno. El par de demostración
ya existía (`docs/ejemplos/`).

Columnas propuestas: `id`, `fecha_recepcion`, `tipo_documento`, `programa`,
`referencia_autores`, `origen`, `sha256`, `fecha_validacion`, `commit_motor`,
`semaforo`, `errores`, `warnings`, `reglas_fallidas`, `uso`, `autorizacion`,
`observaciones`.

Reglas:

- solo un ejemplo de relleno, sin nombres, DNI, matrículas ni identificadores;
- los documentos reales viven fuera del repositorio;
- el registro oficial queda con la sede.

**Compuerta:** sin datos personales, enlaces resueltos, `git diff --check`.

**Estado:** cerrado. PR #77 (`d06284f`, `e836f82`, `3929968`).

---

## Lote 3 — Verificación del frontend (Actividad 15)

**Objetivo:** comprobar que la pantalla de ficha de depósito funciona de
punta a punta contra la API local y el mock de DSpace, y dejar la evidencia
escrita. No se espera reescribir el frontend: los tests y el cableado del
token ya existen.

**Comandos automáticos:**

```bash
cd frontend
npm ci
npm test
npm run lint
npm run build
```

**Checklist manual contra la API local y el mock:**

1. Subir `docs/ejemplos/doc_bueno.docx`.
2. Confirmar semáforo verde y que aparezca la pantalla de ficha.
3. Editar título, autores, asesor, año y palabras clave.
4. Completar los campos manuales con datos ficticios.
5. Pulsar «Preparar depósito».
6. Confirmar el panel de espera y el viaje al buzón.
7. Aceptar el handle reportado.
8. Descargar una constancia y la fila del registro.
9. Confirmar la cabecera de token cuando `VITE_API_TOKEN` está definido.
10. Limpiar la clave `vb-ficha-deposito` de `localStorage` al terminar.

**Evidencia a registrar en:**

- `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md`;
- `docs/semana10_trabajo_retblast.md`.

Si aparece un hueco real, se corrige en este lote y se agrega un test a
`frontend/src/ficha.test.js` o al test del componente afectado.

**Compuerta:** tests, lint, build y checklist de navegador registrados.

**Estado:** cerrado (2026-11-04, PR #79). El checklist se ejecutó contra la API
real; el detalle está en `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md` §8. La
pantalla no tenía ninguna prueba de componente: se agregó
`frontend/src/components/FichaDeposito.test.jsx` (8 casos, verificados con
mutaciones). La verificación también destapó que las respuestas versionadas
del par de ejemplo quedaron desfasadas con el cambio de AUD-03 (PR #78):
se regeneraron y se agregó `tests/test_ejemplos_versionados.py` como guarda.

El clic manual en un navegador real queda para el piloto (lote 4).

---

## Lote 4 — Kit del piloto y borrador de coordinación

**Archivo nuevo:** `docs/PILOTO_OPERADOR.md`.

Secciones: propósito y alcance; roles (Integrante 1, operador, contacto de
la sede); tabla de estado; precondiciones; checklist de ejecución de 11
pasos; limitaciones conocidas; tabla de hallazgos; reglas de datos
personales y datos locales; reversión; cierre.

El checklist cubre:

1. API en `127.0.0.1:8000`, un worker, sin cabeceras de proxy.
2. `/docs` responde 200; un `Host` ajeno responde 400.
3. Userscript 1.1.0 instalado, con la versión confirmada.
4. `VISTOBUENO_FIRMA` y la plantilla del Modelo B presentes.
5. Tesis real o demostración corregida; nunca una plantilla oficial vacía.
6. Revisión de la ficha y de los campos manuales.
7. Preparación del depósito; viaje al buzón.
8. Relleno del formulario de DSpace; adjuntar el DOCX; licencia; enviar.
9. Reporte del handle y hora de Lima.
10. Constancia y fila del registro.
11. Un caso límite: ficha expirada, título que no coincide o colección
    equivocada.

**Limitaciones conocidas a documentar:**

- `palabras_clave_minimo` vuelve roja a las plantillas oficiales vacías
  (decisión del 2026-11-08, intencional).
- `renati.juror` no se captura de forma fiable.
- Limitaciones de infraestructura del piloto (16 campos, DSpace y buzón).

> **Actualización (2026-11-11)**: AUD-24 a AUD-27 y el prefijo de
> `dc.title` quedaron cerrados en el PR #75. El kit del operador
> (`docs/PILOTO_OPERADOR.md` §7) ya no los lista como abiertos; solo quedan
> el jurado no capturado, las plantillas vacías y las limitaciones de
> infraestructura (16 campos, DSpace y buzón).

También: enlace desde `README.md`, enlace desde
`docs/HANDOVER_DESPLIEGUE_MAQUINA_OPERADOR.md` y actualización de
`docs/semana10_trabajo_retblast.md`.

**Borrador de coordinación:** neutral, con marcadores de posición. El
responsable lo revisa y lo envía; el equipo no envía nada en su nombre.

**Compuerta:** checklist ejecutable, sin datos personales.

**Estado:** cerrado (2026-11-04, PR #80). El kit quedó en `docs/PILOTO_OPERADOR.md`,
con el checklist de 11 pasos, las limitaciones conocidas (AUD-24 a AUD-27
y el prefijo de `dc.title`), la tabla de hallazgos, las reglas de datos
personales, la reversión y el cierre de sesión. El borrador de
coordinación va en el Anexo B: es neutral, con marcadores entre
corchetes, y el contacto de la sede lo revisa y lo envía.

Una diferencia con lo planificado: el checklist se escribió con **once**
pasos de ejecución (los mismos once que la lista de arriba) más una
sección de precondiciones que va antes, porque varias de las
precondiciones solo se pueden comprobar con la API levantada.

---

## Lote 5 — Ensayo completo contra el mock

**Objetivo:** última compuerta antes de agendar el piloto.

```bash
nix run .#test-ficha-deposito
nix run .#test-local
```

**Compuerta:** «FLUJO COMPLETO OK», sin drift en `dist`, sin datos
personales en el repositorio.

**Estado:** cerrado (2026-11-04). Los dos comandos pasan y la evidencia
está en `docs/semana10_trabajo_retblast.md`.

Antes de correrlos hubo que arreglar tres cosas, porque en su estado
anterior no se podían usar sin romper el trabajo de otra sesión:

- `test-ficha-deposito` y `test-local` levantan su propia API y su propio
  dev server. Los puertos ahora son configurables
  (`VISTOBUENO_API_PUERTO`, `VISTOBUENO_MOCK_PUERTO`,
  `VISTOBUENO_FRONTEND_PUERTO`) y ambos comandos **comprueban que estén
  libres antes de arrancar**: si el puerto está ocupado, se detienen con
  un mensaje claro. Antes, el `uvicorn` del ensayo no lograba hacer bind
  y el chequeo de arranque respondía contra la API que ya estaba
  escuchando: el ensayo daba verde sin haber probado nada.
- Los dos scripts detenían **cualquier** `uvicorn` y **cualquier** `vite`
  del sistema al terminar. Ahora detienen solo los procesos que ellos
  mismos levantaron, por PID.
- `nix run .#test-local` fallaba de arranque con «python3: command not
  found»: la app del flake no ponía `pythonEnv` ni `nodejs` en el
  `PATH`, como sí hacía su hermana `test-ficha-deposito`.

También: `test-local` levantaba la API en `0.0.0.0`, en contra del
despliegue documentado (loopback). Ahora usa `127.0.0.1`, y el proxy del
dev server de Vite apunta a un destino configurable
(`VISTOBUENO_API_URL`).

El ensayo con navegador real no se hizo en este lote: el clic manual
contra la instancia de la sede es parte del piloto (Actividad 16).

---

## Lote 6 — Cierre de evidencias de la semana 10

Actualizar `docs/semana10_trabajo_retblast.md` con:

- suite actual: 730 recolectados, 724 pasan, 6 `xfail`;
- frontend: 66 tests;
- ruff, mypy y verificación de OpenAPI;
- evidencia de la Actividad 14;
- evidencia de navegador de la Actividad 15;
- fila de regresión semanal de la Actividad 18;
- registro de PRs de la Actividad 19 con los PRs revisados y mergeados
  reales.

Actualizar también el informe y el portafolio de prácticas (fuera del
repositorio) para que no digan que la Actividad 14 sigue pendiente.

**Compuerta:** `git status` limpio salvo los archivos locales conocidos;
registro completo.

**Cifras reales al 2026-11-04** (las del enunciado del lote quedaron
desfasadas al escribirse el plan):

- suite: **742 recolectados, 736 pasan, 6 `xfail`**;
- frontend: **76 tests en 9 archivos**;
- PRs: **64 mergeados en `master`**, 35 propios y 29 de compañeros
  revisados e integrados. El repositorio suma el PR #10, pero su commit de
  merge no está en el historial de `master`: se integró a una rama de
  trabajo, así que no cuenta como mergeado en `master`. El conteo tiene que
  cubrir los dos formatos de integración: los commits de merge y los
  commits squash (`<título> (#N)`), que no dejan commit de merge;
- contrato de la ficha: **v1.12.0**;
- Actividad 14: **concluida** el 2026-11-04 (PR #77). La actividad entrega la
  estructura del registro, no los documentos reales de la sede: eso se
  completa en el piloto;
- Actividad 15: **en ejecución** (PR #79). La verificación contra la API real
  está hecha; falta el clic manual en un navegador real contra la instancia
  de la sede, que es parte del piloto.

> **Actualización al 2026-11-09**: la suite creció a **755 recolectados**
> (749 pasan y 6 `xfail` con `recursos/` y `frontend/dist`; 745 pasan y 4 se
> omiten en un clon limpio). Las cifras de arriba son la foto del 2026-11-04.

El informe y el portafolio de prácticas viven fuera del repositorio, en
`~/Documents/University/2026-II/PRAPRE`. Ahí se actualizaron el estado de las
actividades, las rutas de la columna de evidencia (que apuntaban a una
estructura de carpetas que ya no existe) y el conteo de PRs.

**Estado:** cerrado (2026-11-04, PR #82; correcciones de registro en el PR
#85). La bitácora de la semana 10
registra la fila de regresión de la suite (Actividad 18), el registro de pull
requests (Actividad 19) y el cierre del lote. El informe y el portafolio
quedaron regenerados: 258 archivos, índice de 10 páginas, escaneo de secretos
limpio.

---

## Notas de coordinación

- Los hallazgos de auditoría que siguen abiertos pertenecen a Int3. Int3
  corrigió AUD-24 a AUD-27 en el PR #75 y retiró las marcas `xfail`.
- El bloque de aviso de `AGENTS.md` no se borra hasta que todos los
  hallazgos de la tabla §11 del handover estén cerrados o decididos.
- `AGENTS.md` solo se modifica con aprobación explícita del responsable del
  repositorio.
- Los dos comandos de ensayo (lote 5) ya no detienen procesos ajenos:
  comprueban sus puertos y se detienen solos si están ocupados. Aun así,
  conviene elegirlos libres: el default es 8000 para la API, 8080 para el
  mock y 5173 para el dev server.
