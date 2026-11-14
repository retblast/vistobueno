# Handover: remediación de la auditoría de comportamiento (2026-10-26)

**Origen:** `docs/AUDIT_COMPORTAMIENTO_VISTOBUENO_2026-10-26.md` (27 hallazgos).
**Estado:** abierto. Queda trabajo pendiente en el motor (Int3); la parte de
frontend (Int2) está cerrada (AUD-16 a AUD-18, PR #68).
**Alcance de este documento:** evidencia medida, pendientes con criterio de
aceptación, decisiones ya tomadas y decisiones de dominio que el equipo
todavía no ha cerrado.

**Datos personales:** la verificación se hizo contra una tesis real que vive
en una copia local **fuera del repo**. Este documento usa **placeholders**
(`Apellido, Nombre`, `2026`): los nombres, ORCID y DNI reales no se versionan.

---

## 1. Por qué existe este documento

La auditoría leyó el código y ejecutó el motor contra documentos reales.
La suite de tests pasaba en verde **antes y después** de los hallazgos:
el factory de tests no replica la estructura de las plantillas oficiales
(AUD-20). Por eso el trabajo pendiente **no se detecta con `pytest`**: hace
falta un documento real.

Este handover es la lista de trabajo compartida. Al cerrar una parte,
actualiza la tabla de estado (§11) y el bloque de aviso de `AGENTS.md`.

---

## 2. Evidencia medida (2026-10-28)

Ejecución del motor DSL (`reglas_unt.yaml`, 49 reglas) con las capturas de
la ficha (`reglas_ficha.yaml`):

| Documento | Semáforo | Resultado |
|-----------|----------|-----------|
| Tesis real (copia local con PII) | **verde** | 43 de 49 reglas evaluadas, 6 no aplicables, 0 errores, **5 warnings** |
| Tesis real, versión anterior (copia local con PII) | **rojo** | 1 error (`estructura_tinv_cuantitativo`: faltan 5 headings) + los mismos 5 warnings |
| `EDUCACION INICIAL-PLANTILLA INVESTIGACIÓN CUANTITATIVA.docx` | **rojo** | 1 error (`palabras_clave_minimo`) + 6 warnings |
| `PROGRAMA DE SEGUNDA ESPECIALIDAD EN EDUCACION TEMPRANA-PLANTILLA.docx` | **rojo** | 1 error (`palabras_clave_minimo`) + 6 warnings |
| `PROGRAMA DE SEGUNDA ESPECIALIDAD EN ESTIMULACIÓN-PLANTILLA.docx` | **rojo** | 1 error (`palabras_clave_minimo`) + 6 warnings |
| `TECNOLOGIA EDUCATIVA-ADMINISTRACION Y GERENCIA EDUCATIVA-PLANTILLA.docx` | **rojo** | 1 error (`palabras_clave_minimo`) + 6 warnings |
| `TECNOLOGIA EDUCATIVA-INFORMATICA EDUCATIVA-PLANTILLA.docx` | **rojo** | 1 error (`palabras_clave_minimo`) + 6 warnings |

Los 5 warnings de la tesis real (los mismos de la auditoría):

```
caratula_titulo_trabajo_tamano   @w:val=['26'] esperado=28
caratula_optar_grado_tamano      @w:val=['24'] esperado=26
sangria_parrafo                  @w:firstLine=['708','708','708'] esperado=720; incumplen=[#200=567,#202=567,#209=284]
anexos_minimos_cuantitativo      items_obligatorios=9 faltan=[...9...]
indice_apunta_secciones          entrada_sin_seccion=['1.2.1.General18','1.3.1.General19']
```

---

## 3. Estructura real de la carátula

Es la estructura que el motor debe leer. Es **idéntica** en la plantilla
oficial y en la tesis real (cambian los textos). Los párrafos relevantes,
en orden:

| # | Contenido | Nota |
|---|-----------|------|
| 4 | `Título del trabajo: ...` | en la tesis real el título **termina en ", Trujillo 2024"** (año que NO es el de portada) |
| 6 | `TESIS` | |
| 7 | `Para Optar el Título Profesional de Licenciado en ...` | |
| 9 | `AUTORES:` / `AUTORA:` | **la etiqueta va en su propio párrafo** |
| 10 | `Br. Apellido, Nombre` | **un autor por párrafo**; el nombre es "Apellidos, Nombres" (coma interna) |
| 11 | `https://orcid.org/0000-0000-0000-0000` | línea de ORCID intercalada |
| 12 | `Br. Apellido2, Nombre2` | segundo autor (en la plantilla: texto de ayuda) |
| 13 | `https://orcid.org/...` | |
| 15 | `ASESORA:` / `ASESOR:` | **la etiqueta va en su propio párrafo** |
| 16 | `Dra. Apellido, Nombre` | el nombre va **después** de la etiqueta |
| 17 | `https://orcid.org/...` | |
| 19-20 | `Línea de Investigación:` + valor | |
| 22 | `Trujillo – Perú` | línea de ciudad, sin año |
| 23 | `2026` | **el año real**: es el párrafo que porta el `w:sectPr` → hoy queda fuera del contexto `caratula` |

Consecuencia: el `w:sectPr` de la portada se apoya en el **último** párrafo
del cover (el año). `extractor._caratula_paras` corta **justo antes** de ese
párrafo, así que el año es invisible para cualquier regla con
`contexto: caratula`.

---

## 4. Pendientes de Int3 (motor)

### AUD-01 — `indice_apunta_secciones`: falso positivo (alta)

`_norm_indice` (`validator/analizadores.py`) borra del final del texto un
supuesto número de página en romano minúscula (`[ivxlc]{1,5}`). Los títulos
del **cuerpo** no llevan página, así que pierden la última letra cuando es
`i`, `l`, `v`, `x` o `c`: `General` → `GENERA`. Las entradas del índice sí
llevan página arábiga, que protege la palabra.

**Criterio de aceptación:** con un título `General` en el cuerpo y su
entrada de índice `1.2.1. General 18`, la regla **pasa**. Implementación
sugerida: dos variantes de normalización — los títulos del cuerpo **no**
borran páginas; las entradas del índice sí.

### AUD-02 — `anexos_minimos_*`: los anexos reales no se ven (alta)

Tres defectos apilados:

1. La sección se declara `inicio: anexo` **sin `fin`** y `seccion()` corta en
   el PRIMER título posterior. La estructura real es `Anexos` (Ttulo1)
   seguido de `Anexo 1. ...` (Ttulo1) → el slice queda **vacío**.
2. `AnalizadorListaObligatoria._texto()` solo junta tokens `PARRAFO`: los
   textos de los títulos `Anexo N. <ítem>` nunca se buscan.
3. `faltan[:8]` oculta el noveno ítem cuando faltan 9.

**Criterio de aceptación:** con la estructura real (`Anexos` + `Anexo N.` como
título), la regla encuentra los ítems que existen y lista **todos** los que
faltan, con conteo de hallados. La extensión `hasta_final: true` para
`seccion()` debe quedar registrada en `validator/dsl_check.py` y en
`docs/DSL.md`.

### AUD-03 — El texto `encontrado` es ilegible y señala mal (media)

`AnalizadorXML` arma `@w:val=['26'] esperado=28` y, en `all_eq` fallido,
muestra **primero los valores conformes** y después los culpables, sin
página. La "página N" de `ubicacion` sale del **primer** nodo del xpath, no
del que falla.

**Decisión del equipo (2026-10-28): opción 1 — una sola fuente de verdad del
mensaje.** Crear `validator/detalle.py` con una función por tipo de detalle
(`detalle_xml_atributo`, etc.) e importarla desde **los dos motores**
(`validator/checks.py` y `validator/analizadores.py`). Así la paridad
legacy↔DSL se mantiene **literal** (el test compara el texto) sin duplicar
el formateo en dos archivos.

Formato esperado del detalle (culpables primero, con página, tolerancia y
unidades):

```
incumplen: #200=567 (pág. 49), #202=567 (pág. 49), #209=284 (pág. 50); tolerancia ±12 twips; esperado=720
```

Para `w:sz`: `13pt (se esperaba 14pt)`.

Además, `validator/compilador.py` debe reportar la página del nodo
**culpable**, no la del primero.

**Implementado en el PR #78** (formato final, con el nombre del atributo y
el conteo de valores evaluados; los incumplimientos van primero y el detalle
nunca dice "0 incumplen" en una regla que falla):

```
@w:firstLine: 8 valores evaluados, 8 incumplen: #1=0.00 cm (pág. 1), #2=0.00 cm (pág. 1), ...; tolerancia ±0.02 cm; esperado=1.27 cm
```

**Decisión sobre las unidades (2026-11-04, revisión de retblast)**: se
mantienen **cm y puntos** en lugar de twips, porque es lo que entiende el
estudiante (Word guarda twips y medios puntos). La unidad se deduce del
**último paso del xpath** (el elemento que lleva el atributo: `w:ind`,
`w:pgMar`, `w:pgSz` → twips; `w:sz` → medios puntos), no de buscar
subcadenas en el xpath completo.

El conteo de incumplimientos sale de la misma función que produce el
veredicto (`evaluar_atributo` en `validator/detalle.py`), así que una regla
en rojo **siempre** nombra a su culpable o dice que no había valores que
comparar.

### AUD-04 — Desvíos manual-vs-plantilla sin nota `EVALUADO` (media)

`caratula_titulo_trabajo_tamano` (14pt) y `caratula_optar_grado_tamano`
(13pt) son `warning` por un desvío real: la plantilla oficial usa 13pt y
12pt. El YAML no lleva nota `# EVALUADO:`.

**Criterio de aceptación:** nota `EVALUADO` con fecha y decisión en
`reglas_unt.yaml`, como la tiene `sangria_parrafo`.

### AUD-05 / AUD-06 / AUD-07 — Decisiones de dominio (media/baja)

Ver §8. El motor no se toca hasta que el equipo decida.

### AUD-15 — El exportador inyecta texto sin escapar (media, Int3)

`validator/exportador.py` interpola `message/found/expected` en una tabla
Markdown sin escapar, y `reporte_a_pdf` pasa el resultado por
python-markdown sin escape (HTML crudo). Un `|` en un título rompe la tabla.

**Criterio de aceptación:** escapar `|`, `<`, `>` y `&` antes de armar el
Markdown, con test.

**Implementado en el PR #78**: `_escapar()` escapa `&`, `<`, `>` y `|` en
todos los valores que vienen del reporte (tabla, detalle y encabezados) y
hay un test que comprueba que un `<b>` del documento no llega como HTML
crudo al Markdown. Los prompts de IA van dentro de un bloque de código, que
no se interpreta como Markdown.

### AUD-20 — Brecha factory-vs-realidad (media, Int3)

El doc bueno codifica los anexos como párrafos planos y no ejercita títulos
terminados en `i/l/v/x/c` ni entradas de índice con página arábiga: por eso
AUD-01 y AUD-02 pasaron con la suite en verde.

**Criterio de aceptación:** el factory replica la estructura real
(`Anexos` + `Anexo N.` como título) y agrega el caso `General`.

### AUD-24 — La captura de autores parte un autor en dos (alta)

`reglas_ficha.yaml` muestrea **un** párrafo y parte por la coma de
"Apellidos, Nombres". Resultado actual sobre la tesis real:
`['Br. Linares Azañero', 'Angie Lizbeth']` → **dos autores falsos**, y el
segundo autor real nunca se captura.

**Criterio de aceptación:** capturar **todos** los párrafos de autor
(iterando después de la etiqueta `AUTORES:`/`AUTORA:`, saltando las líneas
de ORCID y parando en la siguiente etiqueta conocida) y partir la lista
**solo entre párrafos**, nunca dentro de uno.

**Valor esperado** (con placeholders): `['Br. Apellido, Nombre', 'Br. Apellido2, Nombre2']`
→ **2 autores**, no 4.

### AUD-25 — La captura del asesor llega vacía marcada como detectada (media)

La etiqueta `ASESORA:` va en su propio párrafo y el nombre en el siguiente.
El `quitar_prefijo` borra la etiqueta completa y el resultado es `''`, pero
`compilador._ficha` publica `detectado: True` para cualquier item capturado.

**Criterio de aceptación:** preferir el párrafo siguiente a la etiqueta (o
exigir contenido no vacío tras limpiar) y publicar `detectado=False` cuando
el valor quede vacío.

### AUD-26 — La captura del año lee el año del título (media)

El título real termina en `", Trujillo 2024"` y el ancla `trujillo` casa ese
párrafo antes que la línea de ciudad. Además, el año de portada (`2026`)
vive en el párrafo que porta el `w:sectPr` y queda fuera del contexto
`caratula` (§3).

**Criterio de aceptación:** `dc.date.issued` vale el año de portada
(`2026`), nunca el del título. Requiere decidir si el párrafo portador del
`sectPr` cuenta como carátula cuando es la última línea de la portada.

### AUD-27 — Palabras clave con puntuación final (baja)

`dc.subject` capturó `['Educación', 'Cultura', 'Identidad cultural.']`: el
punto de cierre de la línea APA queda pegado a la última clave.

**Criterio de aceptación:** quitar la puntuación final al partir.

---

## 5. Hallazgo nuevo (no estaba en la auditoría)

**`palabras_clave_minimo` es `error` y hace fallar las 5 plantillas
oficiales.** La plantilla trae el placeholder `(mínimo 03 palabras clave)`,
que el motor cuenta como **una** entrada → `entradas=1 minimo=3` → error
bloqueante. Una plantilla vacía no debería poder entregar tesis, pero
**tampoco debería reprobar por un texto de ayuda**.

Decisión pendiente del equipo: ¿`palabras_clave_minimo` pasa a `warning`, o
el motor excluye los placeholders entre paréntesis?

**Las 4 plantillas no cuantitativas se evalúan contra el esquema
`tinv_cuantitativo`.** Los programas de segunda especialidad y las
licenciaturas en tecnología educativa no se detectan como otro tipo: se
evalúan con el esquema de tesis cuantitativa (43 reglas evaluadas, 6 no
aplicables). Hoy la app solo soporta el esquema cuantitativo; conviene
dejarlo dicho en la documentación.

---

## 6. Contrato que Int1 exige (y sus tests)

Int1 (**API**) escribe los tests; Int3 (**motor**) los hace pasar. Los tests
con `xfail(strict=True)` marcan los criterios de aceptación: cuando el
motor los cumpla, el `XPASS` estricto pone el CI en rojo hasta que se quite
la marca.

| Contrato | Dónde | Criterio |
|----------|-------|----------|
| Ficha utilizable | `tests/test_api_contract.py` (`TestContratoFichaUtilizable`) | todo `extraidos` con `detectado=True` trae un valor **no vacío** |
| Año válido | `tests/test_api_contract.py` | `dc.date.issued` con `detectado=True` es un año (`\b(19\|20)\d{2}\b`) |
| Autores completos | `tests/test_captura_ficha.py` (`xfail`) | `dc.contributor.author` trae **un autor por párrafo**, con el formato "Apellido, Nombre" (sin partir por la coma) |
| Asesor presente | `tests/test_captura_ficha.py` (`xfail`) | `dc.contributor.advisor` con `detectado=True` trae texto |
| Palabras clave limpias | `tests/test_captura_ficha.py` (`xfail`) | `dc.subject` sin puntuación final (AUD-27) |
| Una constancia por autor | `tests/test_constancia.py` (`TestConstanciasConCapturaReal`, `xfail`) | 2 autores reales → 2 constancias + 2 filas, cada una con su matrícula |
| Paridad real | `tests/test_paridad_formatos.py` | sin aserciones vacías; caso "detectado pero incompleto" comparando `passed` con legacy |

El DOCX de la carátula real (con placeholders) lo construye
`tests/_caratula_real.py`: etiqueta `AUTORES:` en párrafo propio, un autor
por párrafo con ORCID intercalado, etiqueta `ASESORA:` en párrafo propio y
el año en la línea de portada.

---

## 7. Decisiones tomadas por el equipo (2026-10-28)

| Decisión | Elección | Efecto |
|----------|----------|--------|
| AUD-03 | **Opción 1**: módulo único de mensajes (`validator/detalle.py`) usado por los dos motores | la paridad literal se mantiene; no hay dos copias del formateo |
| AUD-09 | **Opción C**: loopback por defecto + token compartido opt-in | el buzón solo se sirve desde la máquina donde corre la app |
| AUD-12 | **Limitador in-app** (cubo de tokens por IP) | protege el CPU del motor sin depender de un proxy |
| AUD-11 | **No aplica**: el archivo lo adjunta el encargado en el formulario oficial | el nombre del bitstream lo pone el selector de archivos, no la app |
| DSpace REST | **Deprecado** (`depositar=true` ya no llama a la red) | la app no escribe en la API de DSpace; el flujo vigente es ficha → buzón → userscript |
| AUD-19 | El bloque de aviso de `AGENTS.md` se actualiza al cerrar cada parte | este documento + `AGENTS.md` son la fuente del estado |

---

## 8. Decisiones de dominio (resueltas el 2026-11-08)

Quedaron resueltas todas las decisiones que estaban abiertas. La evidencia
está medida contra la tesis real de la auditoría y las 5 plantillas
oficiales.

| # | Tema | Decisión | Consecuencia |
|---|------|----------|--------------|
| 1 | Sangría (`sangria_parrafo`) | Se mantiene la regla literal. **No** se eximen estilos de cita en bloque. | Nota `EVALUADO` en el YAML. Las citas en bloque usan `w:left` sin `firstLine`, así que la comparación ya las ignora. Sin cambio de código. |
| 2 | Anexos (`anexos_minimos_cuantitativo`) | El ítem 5 pasa a «Base de datos». El manual dice «Base de datos cuantitativo» y la tesis real titula «Base de datos». | Cambio de dato en `reglas_unt.yaml` + nota `EVALUADO`. El efecto se ve cuando AUD-02 lea la sección de anexos. Sigue siendo `warning`. |
| 3 | AUD-05 (selectores de carátula) | Se endurece solo la regla `error` (`caratula_autores_tamano`): todos los runs con texto y todos los párrafos de autores hasta ASESOR/ORCID. Las dos reglas `warning` conservan el selector actual, con la limitación documentada. | Un falso positivo en una regla `error` pone el semáforo en rojo; en una `warning` solo agrega ruido. **Implementado en el PR #73**: XPath del bloque de autores (todos los runs con texto, desde «AUTORES:» hasta antes de «ASESOR(A):», con las líneas ORCID) y comparación `all_eq`. |
| 4 | AUD-06 (heurística del índice) | Igualdad del título normalizado; `_sigpalabra` queda como respaldo cuando el título normalizado tiene menos de 4 caracteres. | **Implementado en el PR #73** (con AUD-01 ya estable): el match por subcadena se sustituye por igualdad del título normalizado; `_sigpalabra` solo se usa para títulos de <4 caracteres. |
| 5 | AUD-07 (alcance de `caratula_optar_grado_tamano`) | El manual exige 13 pt en la línea «para optar» (párr. 1056 y 1076), pero la tesis aprobada de la auditoría y las 5 plantillas oficiales usan 12 pt. Se sigue el manual: el XPath queda amplio (`para optar`, sin acotar a «Bachiller») y el desvío se reporta como **warning**, sin cambiar el semáforo. | Se cierra AUD-07 en el PR #73. `n_a_si_sin_nodos` solo cubre los documentos que no tienen esa línea. El desvío de la tesis/plantillas se documenta en la nota `EVALUADO` de AUD-04. |
| 6 | `palabras_clave_minimo` | Se mantiene `error`. | Las 5 plantillas oficiales siguen en rojo. Es intencional: sus palabras clave no cumplen el mínimo. No es un bug del motor ni del frontend. |
| 7 | Cache compilado por hilo (§12.3) | **No se implementa.** Medición del 2026-11-08: compilar tarda 5.6 ms de 5.0 s (0.1 %) con la tesis real, y 4.9 ms de 89 ms (5.6 %) con el documento del factory. | Se retira de pendientes. Si se retoma el rendimiento, el objetivo es `tokenizar()`: 6 llamadas, 1.64 s de 4.24 s, no la compilación. |
| 8 | `formato` en `POST /validar` | **No se agrega.** `/validar` sigue devolviendo solo JSON. | El ítem 16 de `docs/PLAN_BACKLOG_FUTURO.md` queda rechazado para el piloto. Si se retoma, va en `POST /reporte` (`md`/`pdf`), con `run_in_threadpool` y medidor de CPU. |
| 9 | Subir el `.docx` a DSpace desde el userscript (§9) | **Descartado.** | El archivo lo adjunta el encargado en el formulario oficial. El userscript solo completa metadatos. |

Notas de evidencia:

- **Sangría**: 16 de 129 párrafos evaluados incumplen, todos a 1.00 cm, en
  «Población, muestra y muestreo». Son prosa normal (`Body Text`,
  justificados); ninguno es una cita en bloque. Ninguno de los 9 documentos
  del corpus usa un estilo de cita.
- **Anexos**: hoy la regla reporta 8 de 9 faltantes por AUD-02, no por el
  nombre. La tesis real tiene 8 anexos; los que de verdad faltan son
  Reporte de similitud, Carta de autorización institucional, Declaración
  jurada y Carta de autorización de publicación.
- **AUD-07**: la cita del párr. 178 es de la línea del Bachiller, pero el
  manual fija 13 pt para toda la línea «para optar» (párr. 1056 y 1076). La
  tesis aprobada y las 5 plantillas usan 12 pt: se reporta como warning.

**AUD-18** ya estaba decidido el 2026-10-28 (Int2, PR #68): el fallback al
reporte de ejemplo queda solo en el build de desarrollo; en producción se
muestra el error real con la opción de reintentar.

---

## 9. Alcance nuevo (descartado el 2026-11-08)

> **Descartado el 2026-11-08**: no se implementa. El archivo lo adjunta el
> encargado en el formulario oficial.

**Subir el `.docx` a DSpace desde el userscript.** Hoy el script solo
rellena metadatos: el archivo lo adjunta el encargado con el selector de
archivos del formulario oficial (es lo que modela el mock de DSpace).

Subirlo automáticamente **es posible pero frágil**: en Chrome un userscript
no puede asignar `input.files` desde su mundo aislado (habría que inyectar
un script en el contexto de la página y usar `DataTransfer`), y haría falta
un endpoint nuevo que sirva los bytes del documento validado. Además, el
flujo real de subida de DSpace **no está validado contra la instancia**
(los TODO de `validator/dspace.py` sobre el endpoint de licencia y el
payload del workflow siguen abiertos).

**No es parte de la remediación de la auditoría.** Si el equipo lo quiere,
es un diseño nuevo.

---

## 10. Cómo reproducir la evidencia

```bash
# La tesis real NO se commitea: contiene datos personales de estudiantes.
# Copia de trabajo (ajustar la ruta):
cp "/ruta/local/TESIS_... (1).docx" /tmp/auditoria/tesis.docx

# Reporte completo (motor DSL + capturas de la ficha):
nix develop -c python3 -m validator.cli /tmp/auditoria/tesis.docx reglas_unt.yaml --json

# Evaluación batch contra las plantillas oficiales:
nix develop -c python3 scripts/eval_contra_plantillas.py recursos/
```

Los scripts de sonda usados en la auditoría (`dump_doc.py`, `manual_dump.py`,
`trace_motor.py`, `probe_ficha.py`) vivían en `/tmp/auditoria/` y no se
versionan: son de un solo uso.

---

### AUD-28 a AUD-31 — revisión de seguridad de la API (alta/media, Int1)

Hallazgos de la revisión de 2026-10-30 sobre el área de Int1 (backend).
Los cuatro quedaron cerrados en la rama `fix/api-hardening-b0-b1`.

- **AUD-28 (alta) — DNS rebinding**: el control de acceso miraba solo
  `request.client.host`; una página servida desde un dominio del atacante
  cuyo DNS resuelve a `127.0.0.1` queda en el mismo origen y podía leer
  el buzón. En Chrome lo frena Private Network Access; Firefox y WebKit
  no lo implementan. Además, uvicorn reescribe el peer con
  `X-Forwarded-For` (proxy headers habilitados por defecto). **Cierre**:
  chequeo del header `Host` (400) + `--no-proxy-headers` en el arranque
  documentado y en la app `serve`.
- **AUD-29 (alta) — inyección de fórmulas en el JSON**: `POST
  /fila-registro` neutralizaba las fórmulas en tsv/csv/xlsx, pero el
  formato `json` por defecto devolvía la fila cruda. Un título
  `=WEBSERVICE(...)` capturado del DOCX llegaba a Excel. **Cierre**: la
  neutralización se movió a `DatosConstancia.fila_registro`, la fuente de
  todos los formatos.
- **AUD-30 (media) — papeleo abierto**: `POST /constancia` y `POST
  /fila-registro` no tenían control de acceso ni límite; un peer remoto
  podía generar constancias oficiales con datos arbitrarios y consumir
  CPU. **Cierre**: dependency de acceso en toda la API + cupo adaptativo
  propio para el papeleo.
- **AUD-31 (media) — límite no adaptativo**: la ventana fija de 60
  peticiones/minuto asumía un coste por petición; medido en este equipo,
  una validación tarda ~58 ms (~33/min con 2 s de CPU por minuto), y en
  un equipo 4× más lento el mismo número permite 4× más presión de CPU.
  **Cierre**: cupo adaptativo que acumula los segundos de trabajo reales
  y se fuga a 2 s por minuto.

### AUD-33 — el botón "+" del formulario no se encontraba (media, Int1)

La lista `BOTONES_AGREGAR` del userscript (`ds-add-button button`,
`button.add-button`, …) no coincide con ninguna clase del formulario
real: en el DOM guardado de "Editar envío" el botón es
`button.ds-form-add-more` (24 veces) y cada fila repetible vive en un
contenedor `[id$="_array"]` (11, 13, 15, 43…). Como los selectores no
existían, las filas extra se llenaban solo si el operador las agregaba a
mano, y el resumen lo reportaba como pendiente. **Cierre**: el ejecutor
busca `button.ds-form-add-more` dentro del contenedor `[id$="_array"]`
del propio campo (nunca a nivel global, que agregaría la fila de otro
campo). Además: la página del ítem se reconoce por
`meta[name="citation_title"]` (antes cualquier enlace
`hdl.handle.net` de una búsqueda podía reportar un handle ajeno), el
estado de auto-relleno se recalcula por ruta (una segunda tesis ya no
queda bloqueada) y el reporte exige que el título del ítem coincida con
la ficha preparada.

### AUD-32 — hora UTC en el registro y la constancia (media, Int1)

El userscript fechaba el clic en Depositar con
`new Date().toISOString().slice(0, 19)`, que devuelve **UTC**. En Lima
(UTC-5) la HORA del registro y de la constancia salía 5 horas adelantada
y, después de las 19:00, el DD/MM/AA saltaba al día siguiente. **Cierre**:
el userscript formatea el instante en `America/Lima` con `Intl`
(`src/reloj.js`) y la API normaliza el `timestamp`: sin offset se
interpreta como Lima, con offset se convierte a Lima. El documento ya no
depende de la zona del navegador ni del servidor.

### AUD-34 — el escáner de secretos dejaba pasar claves entre comillas (baja, Int1)

`PATRON_ASIGNACION` exigía que el nombre del secreto empezara la cadena o
un separador. Una clave JSON/YAML entre comillas
(`"VISTOBUENO_SMTP_PASSWORD": "<valor>"`) no casaba, así que una credencial
real pasaba el pre-commit y el escaneo de la CI. **Cierre**: el patrón
acepta comillas opcionales alrededor del nombre. Tres tests cubren clave
JSON, clave con comillas simples y el falso positivo
`"CABECERA_TOKEN_BUZON"`.

---

## 11. Estado de los hallazgos

Actualizar esta tabla al cerrar cada parte (y el bloque de aviso de
`AGENTS.md`).

> **Actualizado por Int2 (2026-10-28)**: la parte de frontend queda cerrada
> en el PR #68 (`auditoria-2026-10-26-int2`):
> - **AUD-16** — cerrado: pantalla de ficha de depósito en la SPA
>   (`frontend/src/components/FichaDeposito.jsx` + `frontend/src/ficha.js`).
> - **AUD-17** — cerrado: `frontend/src/mocks.js` regenerado desde una
>   respuesta real de `POST /validar`, con la procedencia escrita en el
>   archivo.
> - **AUD-18** — decidido y cerrado: el fallback al reporte de ejemplo queda
>   **solo en desarrollo** (`import.meta.env.DEV`); en producción se muestra
>   el error real con la opción de reintentar. La decisión de dominio
>   quedaba abierta en §8 y la toma el frontend.
>
> El bloque de aviso de `AGENTS.md` **no se borra todavía**: faltan los
> hallazgos de Int3 (AUD-01 a AUD-07, AUD-15, AUD-20, AUD-24 a AUD-27 y los
> dos nuevos).
>
> **Actualizado por Int2 (2026-11-04)**: el bug reportado de «el frontend solo
> muestra las primeras 3 líneas de cada error» estaba en el truncamiento del
> detalle en el motor (`vals[:3]`, `incumplen[:3]`), no en el frontend. Se
> implementó la opción 1 de AUD-03 en el **PR #78** (módulo único
> `validator/detalle.py`, usado por los dos motores): ahora el detalle
> enumera **todos** los incumplimientos con posición, valor y página, y el
> conteo sale de la misma comparación que produce el veredicto (una regla en
> rojo nunca dice "0 incumplen"). El mismo PR implementa el escape del
> exportador (AUD-15). Toca `validator/` (área de Int3), así que el PR queda
> abierto para que lo revise y lo mergee.

> **Actualizado (2026-11-08, Int1)**: el PR #78 está mergeado en `master`
> (`validator/detalle.py` presente). Las filas AUD-03 y AUD-15 quedan
> cerradas. Las decisiones de dominio quedaron resueltas en §8.
>
> **Actualizado (2026-11-10, Int3)**: el **PR #73** cierra AUD-01 (índice con
> tabuladores y página pegada), AUD-02 (`hasta_final` documentado, validado
> por el linter y con conteo `encontrados=N/M`), AUD-04 (notas `EVALUADO` con
> fecha) y AUD-20 (fixture con `w:tab` y regresión). **AUD-05 y AUD-06
> quedan cerrados** en este PR (revisión 2026-11-11): `caratula_autores_tamano`
> valida todos los runs con texto del bloque de autores con `all_eq`, y
> `indice_apunta_secciones` usa igualdad del título normalizado (con
> `_sigpalabra` solo como respaldo para títulos de <4 caracteres). AUD-07
> sigue la decisión del 2026-11-08: XPath amplio de «para optar» y warning en
> la línea de 12 pt; `n_a_si_sin_nodos` solo para documentos sin esa línea.

| ID | Responsable | Estado | PR / commit |
|----|-------------|--------|-------------|
| AUD-01 | Int3 | **cerrado** (`_norm_titulo_cuerpo` + `_norm_indice` híbrido; `w:tab` preservado) | PR #73 |
| AUD-02 | Int3 | **cerrado** (`hasta_final` en DSL/linter + `encontrados=N/M`) | PR #73 |
| AUD-03 | Int3 | **cerrado** (opción 1: módulo único `validator/detalle.py`) | PR #78 |
| AUD-04 | Int3 | **cerrado** (notas `EVALUADO` con fecha y decisión) | PR #73 |
| AUD-05 | Int3 | **cerrado**: todos los runs con texto y todos los párrafos de autores (hasta ASESOR/ORCID) con `all_eq`; las reglas `warning` conservan su selector | PR #73 |
| AUD-06 | Int3 | **cerrado**: igualdad del título normalizado; `_sigpalabra` solo como respaldo para títulos de <4 caracteres | PR #73 |
| AUD-07 | Int3 | **cerrado**: XPath amplio de «para optar» y warning del desvío 12 vs 13 pt; n/a solo si falta la línea | PR #73 |
| AUD-09 | Int1 | **cerrado** | PR #66 |
| AUD-10 | Int1 | **cerrado** | PR #66 |
| AUD-11 | Int1 | **cerrado: no aplica** (decisión 2026-10-28) | — |
| AUD-12 | Int1 | **cerrado** | PR #66 |
| AUD-13 | Int1 | **cerrado** | PR #65 |
| AUD-14 | Int1 | **cerrado** | PR #65 |
| AUD-15 | Int3 | **cerrado** (escape del Markdown) | PR #78 |
| AUD-16 | Int2 | **cerrado** | PR #68 |
| AUD-17 | Int2 | **cerrado** | PR #68 |
| AUD-18 | Int2 | **decidido y cerrado** (fallback solo en desarrollo, 2026-10-28) | PR #68 |
| AUD-19 | Docs | **cerrado** | PR #64 |
| AUD-20 | Int3 | **cerrado** (fixture con `w:tab` y página pegada + regresión) | PR #73 |
| AUD-21 | Int1 | **cerrado** | PR #67 |
| AUD-22 | Int1 | **cerrado** | PR #69 |
| AUD-23 | Int1 | **cerrado: los archivos quedan sin trackear** (decisión 2026-10-28) | — |
| AUD-24 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| AUD-25 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| AUD-26 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| AUD-27 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| Nuevo: `palabras_clave_minimo` | Int3 | **decidido: se mantiene `error`** (intencional; las 5 plantillas fallan a propósito) | — |
| Nuevo: plantillas no cuantitativas | Int3 | documentar | — |
| DSpace REST | Int1 | **cerrado: deprecado** | PR #65 |
| AUD-28 | Int1 | **cerrado** (Host / DNS rebinding) | `8efffd7` (PR #71) |
| AUD-29 | Int1 | **cerrado** (fórmulas en JSON) | `8efffd7` (PR #71) |
| AUD-30 | Int1 | **cerrado** (acceso al papeleo) | `8efffd7` (PR #71) |
| AUD-31 | Int1 | **cerrado** (cupo adaptativo por CPU) | `8efffd7` (PR #71) |
| AUD-32 | Int1 | **cerrado** (hora de Perú) | `f0ba1f0` (PR #71) |
| AUD-33 | Int1 | **cerrado** (botón "+" del userscript) | `22e6a19` (PR #71) |
| AUD-34 | Int1 | **cerrado** (claves entre comillas en el escáner) | `efca435` (PR #71) |
| Nuevo: cache compilado por hilo | Int3 | **decidido: no se implementa** (0.1 % de mejora medida; §12.3) | — |

### Seguimiento de correctitud — 2026-11-12

Tareas, dependencias y aceptación para los tres integrantes en
[`HANDOVER_CORRECTITUD_2026-11-12.md`](HANDOVER_CORRECTITUD_2026-11-12.md).
Los ID `VA` no reemplazan los `AUD`. Esta documentación no cierra los defectos.
VA-13 corresponde a AUD-24 a AUD-27; PR #75 sigue abierto y con conflictos en
la consulta del 2026-11-12. VA-20 añade la verificación del relleno Angular.
VA-21 es un riesgo de restauración/autofill reportado por el usuario y pendiente
de comprobar en el navegador real. retblast implementa solo la parte de Int1.

| ID | Responsable | Estado | Tarea del nuevo handover |
|----|-------------|--------|-------------------------|
| VA-01 | Int3 | pendiente | M1: todos los runs |
| VA-02 | Int3 | pendiente | M1: formato efectivo |
| VA-03 | Int3 | pendiente | M2: A4 en secciones |
| VA-04 | Int3 | pendiente | M3: paginación |
| VA-05 | Int3 | pendiente | M4: declaraciones múltiples |
| VA-06 | Int3 | pendiente | M5: límites del Resumen |
| VA-07 | Int3 | pendiente | M5: Abstract y palabras clave |
| VA-08 | Int1 | pendiente | B4: filas sobrantes |
| VA-09 | Int1 + Int2 | pendiente | B2 + F2: identidad de trámite |
| VA-10 | Int2 | pendiente | F1: identidad del resguardo |
| VA-11 | Int3 + Int1 | M1a corregido (PR 12.2, `3d3e24c`); B5 pendiente | M1a + B5: documento inválido |
| VA-12 | Int3 | pendiente | M9: PDF sin recursos no permitidos |
| VA-13 | Int3 | pendiente de integración | M0: PR #75, AUD-24 a AUD-27 |
| VA-14 | Int3 | pendiente | M6: «Base de datos» |
| VA-15 | Int3 | pendiente | M7: alcance de la regla del logo |
| VA-16 | Int3 | pendiente | M8: ORCID |
| VA-17 | Int1 + Int3 | M11 corregido (PR 12.1, `85690c5`): factory OPC; B6 pendiente | B6: ejemplos; M11: factory |
| VA-18 | Int1 + Int3 | pendiente | B7 + M10: conteos |
| VA-19 | Int1 + Int2 | pendiente | B1 + F4: límite y reintento |
| VA-20 | Int1 | pendiente | B3 y puerta Angular de Int1: antes del piloto |
| VA-21 | Int1 + Int2 | riesgo pendiente de verificar | B8 + F5: autofill y restauración |

### Ampliación normativa — 2026-11-12

Evidencia y fuentes en [AUDITORIA_NORMATIVA_2026-11-12.md](AUDITORIA_NORMATIVA_2026-11-12.md).
No se cerraron defectos con esta documentación. Los detalles están en M12 de Int3.

| ID | Responsable | Estado | Trabajo |
|---|---|---|---|
| NM-01 | Int3 | pendiente | M12a: numeración y pies |
| NM-02 | Int3 | pendiente | M12b: bloques de carátula |
| NM-03 | Int3; Int2 comunica límites | pendiente | M12c y F3: esquemas y alcance |
| NM-04 | Int3 + decisión del encargado | pendiente | M12d: título y autores |
| NM-05 | Int3 | pendiente | M12e: referencias por ámbito |
| NM-06 | Int3 + decisión del encargado | pendiente | M12f: anexos |
| NM-07 | Int3 | pendiente | M12g: origen de las reglas |
| NM-08 | Int1 | decidido por usuario 2026-11-12 | Emular acceso abierto; B3 comprueba persistencia |

---

## 12. Propuestas de Int1 para el área de Int3

Estas propuestas se escribieron desde Int1 (API) y se **revirtieron antes
de commitear**: `engine.py`, `compilador.py`, `analizadores.py`,
`exportador.py` y los YAML de reglas son área de Int3 (motor), según la
tabla de responsabilidades de `AGENTS.md`. Quedaron documentadas aquí, con
el diff exacto, para que Int3 las implemente, las descarte o las aplique.

> **Estado al 2026-11-08**: §12.1 (AUD-04) **se aplica** e incluye la nota
> de AUD-07. §12.2 (AUD-15) está **aplicada y mergeada** (PR #78). §12.3
> (cache por hilo) **no se implementa** (decisión del 2026-11-08).

### 12.1 AUD-04 — notas `EVALUADO` para las dos reglas de carátula

> **Aplicada en el PR #73.** Las notas `EVALUADO` incluyen fecha y decisión.
> AUD-07 se mantiene con el XPath amplio de «para optar» y reporta warning
> cuando la línea está en 12 pt: la nota documenta que el manual exige 13 pt
> (párr. 1056 y 1076) y que la tesis aprobada y las 5 plantillas usan 12 pt,
> así que el desvío es sistémico y visible, no silenciado como n/a.

**Criterio de aceptación**: nota `EVALUADO` con fecha y decisión en
`reglas_unt.yaml`, como la tiene `sangria_parrafo`.

Diff propuesto (`reglas_unt.yaml`):

```diff
@@ -225,6 +225,10 @@ reglas:
   descripcion: Tamaño de letra del título del trabajo en carátula
   valor_esperado: 14pt
   severidad: warning
+  # EVALUADO: el manual pide 14pt (sz val 28, párr. 177) pero la plantilla
+  # oficial usa 13pt (sz val 26). Se mantiene la regla del manual y se
+  # deja como warning: el desvío es de la plantilla, no del estudiante.
+  # Decisión 2026-10-30 (auditoría AUD-04).
   ubicacion: Carátula, especificaciones (párr. 177)
   fuente: MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx
@@ -242,6 +246,10 @@ reglas:
     en..."
   valor_esperado: 13pt
   severidad: warning
+  # EVALUADO: el manual pide 13pt (sz val 26, párr. 178) pero la plantilla
+  # oficial usa 12pt (sz val 24). Se mantiene la regla del manual y se
+  # deja como warning: el desvío es de la plantilla, no del estudiante.
+  # Decisión 2026-10-30 (auditoría AUD-04).
   ubicacion: Carátula, especificaciones (párr. 178)
   fuente: MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx
```

Nota: el texto de las notas es una propuesta de redacción. Si Int3 prefiere
otra formulación, lo decide quien conoce el manual.

### 12.2 AUD-15 — escape del texto antes de armar el Markdown

> **Aplicada y mergeada** (PR #78). El diff queda como registro.

**Criterio de aceptación**: escapar `|`, `<`, `>` y `&` antes de armar el
Markdown, con test.

Diff propuesto (`validator/exportador.py`):

```diff
@@ -29,6 +29,24 @@ import markdown
 _EMOJIS = {"rojo": "🔴", "verde": "🟢"}

+def _escapar_md(texto: object) -> str:
+    """Escapa el texto que viene del documento antes de interpolarlo.
+
+    Sin este escape, un `|` en la descripción de una regla rompe la tabla
+    Markdown (la fila se parte en dos) y un `<` abre HTML crudo en el PDF
+    (python-markdown no escapa el HTML que recibe). El orden importa: `&`
+    va primero para no escapar dos veces las entidades que se crean
+    después.
+    """
+    return (
+        str(texto)
+        .replace("&", "&amp;")
+        .replace("<", "&lt;")
+        .replace(">", "&gt;")
+        .replace("|", "\\|")
+    )
+
+
 def reporte_a_markdown(reporte: dict) -> str:
@@ -52,7 +70,9 @@ def reporte_a_markdown(reporte: dict) -> str:
     for r in reporte["resultados"]:
         estado = "✅ cumple" if r["passed"] else "❌ **falla**"
-        linea = f"| `{r['rule_id']}` | {estado} | `{r['severity']}` | {r['message']} |"
+        linea = (
+            f"| `{r['rule_id']}` | {estado} | `{r['severity']}` | {_escapar_md(r['message'])} |"
+        )
         lineas.append(linea)
@@ -60,17 +80,17 @@ def reporte_a_markdown(reporte: dict) -> str:
         if r["passed"]:
             continue
         lineas += [
-            f"#### `{r['rule_id']}` — {r['message']}",
+            f"#### `{r['rule_id']}` — {_escapar_md(r['message'])}",
             "",
-            f"- **Esperado:** {r['expected']}",
-            f"- **Encontrado:** {r['found']}",
+            f"- **Esperado:** {_escapar_md(r['expected'])}",
+            f"- **Encontrado:** {_escapar_md(r['found'])}",
         ]
         if r.get("location"):
-            lineas.append(f"- **Ubicación:** {r['location']}")
+            lineas.append(f"- **Ubicación:** {_escapar_md(r['location'])}")
         if r.get("fuente"):
-            lineas.append(f"- **Fuente:** {r['fuente']}")
+            lineas.append(f"- **Fuente:** {_escapar_md(r['fuente'])}")
         if r.get("cita"):
-            lineas.append(f"- **Cita:** {r['cita']}")
+            lineas.append(f"- **Cita:** {_escapar_md(r['cita'])}")
         lineas.append("")
```

Tests sugeridos (`tests/test_exportador.py`):

1. Un `|` en `message` no rompe la tabla: la fila del resultado conserva
   sus cuatro columnas (contar `|` sin escapar).
2. Un `<script>` en `message` sale escapado en el Markdown (`<script>`)
   y no como HTML crudo en el HTML que produce `markdown.markdown`.

Nota: el escape no cubre el prompt de "Cómo preguntar a una IA" (va dentro
de un bloque de código, donde el contenido es literal).

### 12.3 Propuesta: cache compilado por hilo (rendimiento y thread-safety)

> **No se implementa (decisión del 2026-11-08).** Medición en este equipo:
> compilar tarda 5.6 ms de 5.0 s (0.1 %) con la tesis real y 4.9 ms de
> 89 ms (5.6 %) con el documento del factory. El costo real está en
> `tokenizar()`: 6 llamadas, 1.64 s de 4.24 s de ejecución. Se deja como
> análisis histórico.

**Motivo**: `validate_docx` recompila el DSL en cada petición. Medido en
este equipo, la validación síncrona tarda ~58 ms (compilación ~2,7 ms).

**Ojo con el estado mutable**: los analizadores guardan estado entre
llamadas (`analizadores.py:58,63`: `ultimo_nodo`, `valor`) y la lista
`ficha` **se acumula** si no se limpia (`AnalizadorExtraccion` hace
`append`). Por eso un cache necesita (a) ser por hilo
(`threading.local()`) y (b) reiniciar ese estado antes de cada ejecución.

Diff propuesto (`validator/compilador.py`) — reinicio del estado:

```diff
@@ -585,6 +585,16 @@ class ReglaCompilada:
         return ""

     def ejecutar(self, extracted: ExtractedDocx) -> RuleResult:
+        # Reinicializamos el estado mutable de los analizadores para evitar
+        # contaminación entre ejecuciones consecutivas (ficha, ultimo_nodo,
+        # valor). Esto es necesario cuando el mismo CompilerDSL se reutiliza
+        # en varias llamadas dentro del mismo hilo (cache compilado).
+        for an in self.analizadores:
+            an.ficha = []
+            if an.valor is not None:
+                an.valor = None
+            an.ultimo_nodo = None
+
         fallos: list[str] = []
```

Diff propuesto (`validator/engine.py`) — cache por hilo y ejecución en dos
fases (el cuerpo de `CompilerDSL.ejecutar` sin la recompilación):

```diff
+import threading
 from collections.abc import Iterable
 from pathlib import Path
@@
-from .compilador import CompilerDSL
-from .extractor import extract
+from .compilador import CompilerDSL, _con_sentinel
+from .extractor import ExtractedDocx, extract
 from .models import RuleResult, Severity
+
+# Cache compilado por hilo (thread-safety): el mismo CompilerDSL se
+# reutiliza entre peticiones consecutivas dentro de un hilo, evitando
+# re-parsear el YAML en cada validación. El estado mutable de los
+# analizadores se reinicia en ReglaCompilada.ejecutar() antes de cada
+# ejecución, así que un analizador compartido no contamina la salida.
+_thread_local = threading.local()
+
+
+def _reglas_compiladas(rules_data: dict) -> list:
+    """Devuelve la lista de `ReglaCompilada` cacheada por hilo.
+
+    Compila una vez por hilo y por objeto ``rules_data`` (clave ``id``).
+    """
+    cache = getattr(_thread_local, "compilados", None)
+    if cache is None:
+        cache = {}
+        _thread_local.compilados = cache
+    clave = id(rules_data)
+    if clave in cache:
+        return cache[clave]
+    reglas = CompilerDSL().compilar(rules_data)
+    cache[clave] = reglas
+    return reglas
+
+
+def _ejecutar_compilado(reglas: list, extracted: ExtractedDocx) -> list[RuleResult]:
+    """Ejecuta reglas ya compiladas en dos fases (ver CompilerDSL.ejecutar)."""
+    contexto: dict[str, str] = {}
+    resultados: list[RuleResult | None] = [None] * len(reglas)
+
+    for i, r in enumerate(reglas):
+        if r.aplicar_si is None:
+            res = r.ejecutar(extracted)
+            resultados[i] = res
+            if r.expone:
+                contexto[r.expone] = r.valor_para_contexto()
+
+    for i, r in enumerate(reglas):
+        if r.aplicar_si is None:
+            continue
+        resultados[i] = r.ejecutar(extracted) if r.aplica_en(contexto) else r.no_aplicable()
+
+    return _con_sentinel(resultados, contexto)
```

Y en `validate_docx`:

```diff
     if "reglas" in rules_data:
-        resultados = CompilerDSL().ejecutar(rules_data, extracted)
+        resultados = _ejecutar_compilado(_reglas_compiladas(rules_data), extracted)
@@
     if ficha_data is not None:
-        resultados = resultados + CompilerDSL().ejecutar(ficha_data, extracted)
+        resultados = resultados + _ejecutar_compilado(_reglas_compiladas(ficha_data), extracted)
```

**Nota de Int1**: si Int3 prefiere el enfoque "analizadores sin estado"
(limpiar `ficha`, `valor` y `ultimo_nodo` dentro de cada `analizar`), el
reinicio explícito queda innecesario y el cache puede ser global, sin
`threading.local()`. Ese camino es más limpio a largo plazo y es decisión
del área del motor.

**Verificación realizada con el parche** (en la rama de Int1, ya revertida):
la suite completa pasó (693 passed, 6 xfailed) y `nix flake check` dio
"all checks passed".

---

## 13. Impacto por integrante (2026-11-08)

Resumen de lo que cambia para cada área después de las decisiones de §8.

| Integrante | Qué cambia | Qué no hacer |
|------------|------------|--------------|
| **Int1 (API)** | Documentar las decisiones (§8, §11, §13) y cerrar el ítem 16 del backlog. Mantener `/validar` en JSON. | No agregar `formato` a `/validar`. No tocar el contrato (sigue en v1.12.0). |
| **Int2 (frontend)** | Nada de código. Los reportes cambian de contenido cuando el motor cierre AUD-02, AUD-05 y AUD-06 (menos avisos falsos), pero la forma del JSON no cambia. | No construir descarga del reporte (decisión 8). No construir subida del `.docx` a DSpace (decisión 9). No tratar el rojo de las plantillas por `palabras_clave_minimo` como bug de UI (decisión 6). Actualizar `docs/semana10_trabajo_integrante2.md`: dice que el PR #78 está abierto y ya está mergeado. |
| **Int3 (motor)** | AUD-02 (leer los anexos reales y no truncar), AUD-05 (endurecer la regla `error`), AUD-06 (igualdad normalizada, después de AUD-01), AUD-04 (notas `EVALUADO`, incluido AUD-07). | No implementar el cache por hilo (decisión 7). No eximir estilos en sangría (decisión 1). No agregar `n_a_si_sin_nodos` para AUD-07: no hace falta. |
| **Documentación** | Handover actualizado, backlog sincronizado y bloque de aviso de `AGENTS.md` (aprobado el 2026-11-08). | No borrar el bloque de aviso hasta que todos los hallazgos estén en `cerrado` o `decidido`. |
