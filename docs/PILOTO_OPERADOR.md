# Kit del piloto — operador de la biblioteca

Guía paso a paso para la primera prueba de VistoBueno con la instancia real
de DSpace de la UNT. La sigue el operador de la biblioteca con un
integrante del equipo presente.

Complementa tres documentos:

- `docs/HANDOVER_DESPLIEGUE_MAQUINA_OPERADOR.md`: instalación y
  endurecimiento de la API en la máquina del operador.
- `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md`: detalle de la pantalla de
  ficha y de sus limitaciones.
- `docs/CONTRATO_API.md`: contrato de los endpoints que usa el flujo.

---

## 1. Propósito y alcance

**Propósito:** comprobar, con un documento real, que el flujo completo
—validar, completar la ficha, rellenar el formulario oficial de DSpace,
adjuntar el archivo y generar el papeleo— funciona en la máquina de la
biblioteca.

**Alcance del piloto:** una sesión de entre 60 y 90 minutos con un
integrante del equipo y el operador. Se trabaja sobre **un** documento y,
si da tiempo, **un** caso límite.

**Fuera del piloto:**

- La app no escribe en la API de DSpace. El archivo lo adjunta el
  operador en el formulario oficial; el userscript solo rellena los
  metadatos.
- El camino REST automático (`POST /validar` con `depositar=true`) está
  **deprecado** desde la decisión del 2026-10-28 y no se usa.
- No se migra el registro oficial. La fila que genera la app es una
  ayuda para pegar; la numeración y el archivo definitivo son de la
  biblioteca.
- No se corrigen fallos del motor durante la sesión. Si aparece uno, se
  anota en la tabla de hallazgos (§8) y se sigue.

---

## 2. Roles

| Rol | Quién | Qué hace durante el piloto |
|-----|-------|----------------------------|
| Operador | Personal de la biblioteca | Sube el documento, completa la ficha, rellena el formulario oficial, adjunta el `.docx` y confirma el depósito |
| Integrante 1 (backend/API) | Equipo de desarrollo | Acompaña, verifica los estados de la API, toma notas de los hallazgos y decide la reversión |
| Contacto de la sede | Persona designada por la biblioteca | Autoriza el uso del documento de prueba y recibe el resultado de la sesión |

El equipo **no** envía comunicaciones en nombre de la biblioteca. El
borrador de coordination del Anexo B lo revisa y lo envía el contacto de
la sede.

---

## 3. Estado de la entrega

| Componente | Estado | Nota |
|---|---|---|
| API de validación | Listo | Contrato v1.14.0 |
| Pantalla de ficha de depósito | Listo | Verificada contra la API real el 2026-11-04 |
| Buzón de una ranura | Listo | "Última gana", un solo worker; 1 h de autorrelleno y 24 h de retención del trámite |
| Userscript de relleno | Listo | Protocolo 2, `@connect localhost` |
| Mock de DSpace | Listo | Para ensayo sin tocar la instancia real |
| Constancia (Modelo B) y fila del registro | Listo | Requiere la firma y la plantilla oficial que ya tiene el operador |
| Hallazgos AUD-24 a AUD-27 del motor | **Cerrados** | PR #75: autores completos, asesora, año de portada y palabras clave limpias; ver §7 |
| Pruebas automatizadas | En verde, sin `xfail` | `pytest tests/ -q` en un clon sin `recursos/` ni `frontend/dist`: los `skipped` son esperados y no son fallos |

---

## 4. Precondiciones

Deben cumplirse **antes** de empezar la sesión. Si algo falla, se
resuelve o se pospone el piloto; no se improvisa durante el ensayo.

| # | Precondición | Cómo se comprueba |
|---|---|---|
| 1 | La API está levantada en `127.0.0.1:8000`, con **un solo worker** y sin cabeceras de proxy | `ss -ltnp` muestra `127.0.0.1:8000`; la app `serve` ya agrega `--no-proxy-headers` y no pasa `--workers` |
| 2 | La API responde en `/docs` | `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs` → **200** |
| 3 | Un `Host` ajeno se rechaza | `curl -s -o /dev/null -w "%{http_code}\n" -H "Host: atacante.example" http://127.0.0.1:8000/docs` → **400** |
| 4 | La plantilla del Modelo B está en `recursos/` | Existe `recursos/TESIS DIGITAL MODELO B-2026.docx`, o `VISTOBUENO_PLANTILLA_CONSTANCIA` apunta a ella |
| 5 | Se configuró la firma según [§3.5](INSTALACION.md#35-preparar-la-constancia-y-el-registro) | Una constancia de prueba se descarga y la fila del registro muestra el nombre en **FIRMA** |
| 6 | El userscript está instalado en Tampermonkey en su versión actual | La versión de Tampermonkey coincide con `@version` del archivo de la entrega en `tools/dspace-fill/dist/` |
| 7 | La SPA está levantada y apuntando a la API local | La pantalla de carga abre y el botón de subir documento responde |
| 8 | Hay un documento de prueba aprobado | Una tesis real del operador o `docs/ejemplos/doc_bueno.docx`. **Nunca** una plantilla oficial vacía |
| 9 | El navegador no tiene una ficha de una sesión anterior | La clave `vb-ficha-deposito` de `localStorage` está limpia |

> La precondición 8 importa: la plantilla oficial vacía tiene
> `palabras_clave_minimo` como error y el semáforo sale **rojo** sin que
> haya un fallo real de formato (§7).

---

## 5. Checklist de ejecución

Cada paso tiene una comprobación objetiva. Un paso no se da por bueno
porque "parece que funcionó": se marca con la evidencia.

### Paso 1 — Confirmar la API

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
```

**Esperado:** `200`. Si devuelve `400`, el `Host` que llega no es el
propio: ver `docs/HANDOVER_DESPLIEGUE_MAQUINA_OPERADOR.md` §2.

### Paso 2 — Abrir la SPA y subir el documento

Se sube el documento de prueba en la pantalla principal.

**Esperado:** la respuesta trae `semaforo: "verde"`, el resumen de reglas
y un objeto `ficha_deposito` **no nulo**.

> La ficha solo viaja con semáforo verde. Con rojo viene `null`: es el
> invariante del contrato, no un fallo.

### Paso 3 — Revisar los valores extraídos

La pantalla de ficha muestra título, autores, asesor, resumen, palabras
clave, año, escuela y jurado. El operador compara cada campo con
el documento original.

**Esperado:** los valores coinciden con el documento. Los campos que
lleguen con `detectado: false` se teclean a mano (§7).

### Paso 4 — Completar los campos manuales

Matrícula, DNI del autor, DNI del asesor y ORCID. Son datos que no salen
del `.docx`.

**Esperado:** la matrícula y el DNI se alinean **por posición** con la
lista de autores. En una tesis de dos autores se escriben dos valores de
cada uno, en el mismo orden.

### Paso 5 — Corregir los valores y preparar el depósito

Se corrige lo que haga falta y se pulsa **«Preparar depósito»**.

**Esperado:** la pantalla entra en el panel de espera y la API responde
**`201`** `POST /ficha-pendiente` con `{tramite_id, revision,
autofill_hasta, retenido_hasta, vence_en}`. La SPA conserva esa identidad y
solo acepta un depósito del mismo trámite.

Comprobación por terminal:

```bash
curl -s http://127.0.0.1:8000/ficha-pendiente | head -c 400
```

**Esperado:** el sobre `{ficha, tramite_id, revision, ...}`. La ficha
contiene los valores corregidos del paso 4.

El trámite tiene dos ventanas: 1 hora para el **autorrelleno** y 24 horas
de **retención** del trámite completo. Vencer la primera no borra la
ficha: el trámite sigue en `GET /tramite`.

### Paso 6 — Rellenar el formulario de DSpace

En la pestaña de DSpace, el botón del userscript consulta el buzón y
rellena el formulario oficial.

**Esperado:** el toast del userscript resume qué se llenó, qué quedó
"a mano" y qué no encontró. Si un campo no se llena, el toast lo nombra:
es el comportamiento correcto, no un fallo.

### Paso 7 — Adjuntar el archivo y confirmar la licencia

El userscript **no** toca el selector de archivos. El operador adjunta el
`.docx` a mano y marca la casilla de la licencia.

**Esperado:** el botón **Depositar** queda habilitado.

### Paso 8 — Enviar y registrar la hora del clic

Se pulsa **Depositar**.

**Esperado:** el clic queda registrado como la hora del envío (ISO 8601,
hora de Perú). **Todavía no hay depósito confirmado**: el clic en
"Depositar" no prueba que el ítem exista.

Comprobación por terminal:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/deposito
```

**Esperado:** `404` para un trámite nuevo. Si devuelve `200` para el
trámite actual antes de confirmarlo, pausa la prueba y revisa la versión
del userscript instalada y el estado del trámite.

### Paso 9 — Confirmar el ítem archivado

En la página del ítem (`/items/<uuid>`), el userscript muestra un panel
con el handle, el título y los autores observados. El operador compara
esos datos con la ficha y pulsa **«Confirmar depósito archivado»**.

**Esperado:** el panel queda en "Confirmado por el operador" y el buzón
devuelve la confirmación:

```bash
curl -s http://127.0.0.1:8000/deposito
```

**Esperado:** `handle`, `tramite_id`, `titulo_observado`, `timestamp`,
`revision_confirmada`, `confirmado_en`, `confirmado_por: "operador"` y
`confirmacion_vigente: true`.

- Si el título no coincide, el panel no deja confirmar y la API responde
  `409`. La coincidencia por inclusión no basta.
- Si la página no publica autores, la confirmación queda con
  `autores_verificados: false`: el panel dice "autores no verificados",
  nunca "coinciden".
- El estado "archivado" es una **atestación del operador**. La API no
  consulta DSpace.

### Paso 10 — Generar la constancia

Desde la pantalla de la ficha, la descarga de constancia.

**Esperado:** un `.docx` con el Modelo B y **ningún** MERGEFIELD sin
reemplazar (el texto se ve como texto plano, no como campos de Word).

Con `?formato=zip` la descarga trae la constancia **y** la fila del
registro del autor en `registro.csv`.

La API usa la ficha publicada y el depósito vigente del servidor. Si la
solicitud no coincide con ese estado, responde **409**: prepare y
deposite de nuevo en lugar de editar el timestamp o el handle.

> Si la API responde **500**, casi siempre es que falta la firma
> (`VISTOBUENO_FIRMA` o `recursos/firma.txt` con el lanzador) o la
> plantilla del Modelo B. El mensaje en el `detail` nombra cuál de las dos.

### Paso 11 — Generar la fila del registro

**Esperado:** una fila con las columnas del registro oficial, en orden:
N°, TESIS/TSP, BACHILLER/LICENCIADO, N° MATRIC., DD, MM, AA, HORA,
DIRECCION URL, FIRMA, FECHA DEL DOC., ESCUELAS, AÑO.

Formatos disponibles: `tsv`, `csv`, `xlsx` y `json`. El `csv` usa `;`
como separador y el `tsv` usa tabulaciones: los dos abren directo en
Excel o LibreOffice, sin errores de pegado.

La columna **N° va vacía**: la numeración es del registro oficial de la
biblioteca.

### Paso 12 — Un caso límite

Con la misma sesión, se prueba **uno** de estos tres:

| Caso | Cómo se provoca | Comportamiento esperado |
|---|---|---|
| Ficha expirada | Se deja pasar más de 1 hora desde «Preparar depósito» | `GET /ficha-pendiente` devuelve `404`; el userscript avisa que no hay ficha. El trámite sigue en `GET /tramite` hasta las 24 h |
| Título que no coincide | Se edita el título en la pantalla **después** de preparar el depósito | La SPA avisa la discrepancia y no usa el handle. Si hay un depósito confirmado, la conciliación incrementa la revisión y exige una reconfirmación |
| Colección equivocada | Se elige otra colección en el formulario de DSpace | El handle apunta a otra colección: se anota como hallazgo de la sede, no del software |

**Esperado:** en los tres casos el sistema no falla en silencio y el
operador tiene una señal visible.

---

## 6. Qué se anota durante la sesión

Por cada paso se anota:

- el **resultado**: correcto, con observación, o fallido;
- la **evidencia**: captura de pantalla, respuesta de `curl`, o el texto
  del toast;
- el **hallazgo**, si lo hay, en la tabla de §8.

Una observación sin evidencia no sirve: el equipo no puede reproducirla
después.

---

## 7. Limitaciones conocidas

**AUD-24 a AUD-27 quedaron cerrados en el PR #75**: el motor ya captura
todos los autores (sin partir por la coma), el asesor (etiqueta en párrafo
propio o junto al nombre), el año de portada (no el del título), el
abstract y las palabras clave sin puntuación final. El operador puede
seguir corrigiendo cualquier campo a mano en la pantalla.

Quedan estas limitaciones:

- El **jurado** no se captura (`renati.juror` no es confiable). Se teclea
  a mano o no se usa.
- `palabras_clave_minimo` marca `error` en las plantillas oficiales vacías;
  no es un fallo real: se sube una tesis, no una plantilla vacía.
- 16 campos del formulario oficial **no viajan** en la ficha: el servidor
  de DSpace los pre-llena según la colección destino.
- La app **no escribe** en la API de DSpace. Todo depósito pasa por el
  formulario oficial.
- El buzón es memoria del proceso: **reiniciar la API lo vacía**. Se
  re-valida y se vuelve a preparar la ficha.
- El buzón tiene dos ventanas: 1 hora para el **autorrelleno** y 24 horas
  de **retención** del trámite. Pasada la primera, el userscript ya no
  rellena el formulario, pero el trámite sigue disponible en
  `GET /tramite` para confirmar y para el papeleo.

---

## 8. Tabla de hallazgos

Se llena durante la sesión. El equipo la toma al cerrar el piloto.

| # | Paso | Descripción | Evidencia | Gravedad | Estado |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

**Gravedad:** alta (bloquea el flujo), media (el operador tiene que
trabajar alrededor), baja (molestia o texto).

**Estado:** abierto, ya corregido en el sitio, o derivado al backlog.

---

## 9. Datos personales y datos locales

La ficha de depósito contiene datos del estudiante: nombre, DNI,
matrícula, ORCID y el resumen de la tesis. Son datos personales.

Reglas durante el piloto:

- Los documentos de prueba **no se suben al repositorio**. `recursos/` y
  cualquier carpeta local de pruebas quedan fuera de Git.
- No se pega ningún dato personal en un ticket, un chat, un commit ni una
  captura que se comparta.
- Las capturas de pantalla se recortan o se tapan antes de compartirlas.
- La fila del registro y las constancias que se generan durante el
  ensayo **no se versionan**.
- Al terminar la sesión, se limpia el estado local: la clave
  `vb-ficha-deposito` del `localStorage` y la ficha del buzón (se reinicia
  la API o se publica otra).
- El escáner de secretos (`scripts/verificar_secretos.py`) corre en el
  CI y en el hook de pre-commit: bloquea credenciales de SMTP, DSpace y
  del buzón.

---

## 10. Reversión

El piloto **no deja cambios en la instancia de DSpace que no se puedan
deshacer**. El punto de reversión es el estado del navegador y el del
proceso de la API.

| Situación | Reversión |
|---|---|
| La API no responde | Detener el proceso y volver al commit anterior (`git checkout <commit-anterior>`), luego reiniciar. El buzón se pierde: se re-valida y se vuelve a preparar la ficha |
| La SPA no carga | Recargar con fuerza (`Ctrl+Shift+R`). Si sigue, reconstruir: `cd frontend && npm ci && npm run build` |
| El userscript no llena el formulario | En Tampermonkey, reemplazar el script por el `dist` actual (`tools/dspace-fill/dist/vistobueno-dspace-fill.user.js`) y recargar la página |
| Se publicó una ficha de prueba en DSpace | La borra el operador desde el panel de DSpace. El equipo **no** borra ítems de la biblioteca |
| El `Host` propio se rechaza | Revisar `VISTOBUENO_HOSTS`. Nunca usar `*` en producción: deja el DNS rebinding sin mitigación |

El documento de prueba del piloto debería ser un **borrador descartable**
del operador. Eso acota el daño de cualquier depósito de más.

---

## 11. Cierre de la sesión

1. Confirmar que el handle del paso 9 aparece en la ficha del buzón y en
   la fila del registro, con `confirmacion_vigente: true`.
2. Confirmar que la constancia del paso 10 no tiene MERGEFIELD sin
   reemplazar.
3. Anotar en la tabla de hallazgos todo lo que no salió como se esperaba.
4. Limpiar el estado local: `localStorage` y el buzón.
5. Dejar la API y la SPA como estaban, o detenerlas si la sesión terminó.
6. Entregar el documento de prueba al operador (o destruirlo — ver §9).

El equipo cierra con un resumen: pasos ejecutados, hallazgos, y si el
flujo queda **apto para uso diario** o necesita otra iteración.

---

## Anexo A — Glosario

| Término | Qué significa aquí |
|---|---|
| Ficha de depósito | El conjunto de metadatos que la SPA prepara y el userscript vuelca en el formulario de DSpace |
| Buzón | Una ranura en memoria de la API donde espera la ficha. "Última gana"; 1 h de autorrelleno y 24 h de retención del trámite |
| Handle | La URI que asigna DSpace al ítem depositado (`https://hdl.handle.net/…`) |
| Extraído | Un valor que la API leyó del `.docx` |
| Manual | Un valor que escribe el operador: matrícula, DNI, ORCID |
| MERGEFIELD | Un campo de Word de la plantilla que el papeleo reemplaza por texto plano |
| `detectado` | Indicador de si un valor extraído es utilizable. `false` = hay que teclearlo |

---

## Anexo B — Borrador de coordinación

Borrador **neutral**, con marcadores de posición. El contacto de la sede
lo revisa, lo completa y lo envía. El equipo no lo envía en su nombre.

---

**Asunto:** Sesión de prueba de VistoBueno con la biblioteca — [FECHA]

Estimado/a [NOMBRE], junto a [NOMBRE 2]:

Le confirmamos la fecha y hora de la sesión de prueba de VistoBueno en
la biblioteca:

- **Fecha:** [FECHA]
- **Hora:** [HORA INICIO]–[HORA FIN]
- **Lugar:** [LUGAR]

La sesión es de tipo práctico: acompañamos al operador en el flujo real
de validación y depósito de una tesis. No se instala nada en los
equipos de la biblioteca ni se modifican datos del repositorio.

Para la sesión necesitamos:

1. Un documento de prueba en formato `.docx` (una tesis o un borrador
   descartable). No hace falta que sea una tesis definitiva.
2. Acceso a la máquina donde se hizo la instalación, o la posibilidad
   de entrar a ella ese día.
3. La copia vigente del Modelo B que ya tiene el operador.

La sesión no altera el registro oficial de la biblioteca ni publica
ítems definitivos: el depósito de prueba se hace sobre un borrador
descartable.

Quedamos a la espera de confirmar la fecha.

Atentamente,
[CARGO]
[NOMBRE]
[DATOS DE CONTACTO]

---

### Anexo B.1 — Notas de uso del borrador

- Reemplazar todos los marcadores entre corchetes.
- El texto no promete fechas que el equipo no haya confirmado con la
  sede.
- Si la sede prefiere otro canal, se adapta el formato pero se conserva
  el contenido.
- No se envía desde una cuenta personal del equipo.
