# Handover: remediación de la auditoría de comportamiento (2026-10-26)

**Origen:** `docs/AUDIT_COMPORTAMIENTO_VISTOBUENO_2026-10-26.md` (27 hallazgos).
**Estado:** abierto. Hay trabajo pendiente en el motor (Int3) y en el frontend (Int2).
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
actualizá la tabla de estado (§11) y el bloque de aviso de `AGENTS.md`.

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

## 8. Decisiones de dominio abiertas

Necesitan al equipo, no a un integrante:

1. **Sangría:** ¿la regla exime estilos de bloque tipo `Textoindependiente`?
   Los 4 párrafos marcados en la tesis real son legítimos según la letra de
   la regla; discutible según APA.
2. **Anexos:** ¿"Base de datos cuantitativa" debe matchear "Base de datos"?
   (AUD-02, ítem 5 de la lista de anexos).
3. **AUD-05:** ¿se endurecen los selectores de carátula (leer todos los runs
   con texto, validar todos los párrafos de autores) o se documenta la
   limitación en el YAML?
4. **AUD-06:** ¿se endurece la heurística del índice (palabra significativa de
   menos de 4 caracteres auto-pasa; el match por subcadena puede ocultar
   faltantes)?
5. **AUD-07:** ¿`caratula_optar_grado_tamano` se restringe a la línea del
   Bachiller o acepta 12pt para la variante "Título Profesional"?
6. **AUD-18 (Int2):** ¿el fallback al reporte de ejemplo sigue activo en
   producción?
7. **`palabras_clave_minimo`:** ¿`warning` o exclusión de placeholders? (§5)

---

## 9. Alcance nuevo, no resuelto

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

## 11. Estado de los hallazgos

Actualizar esta tabla al cerrar cada parte (y el bloque de aviso de
`AGENTS.md`).

> **Pendiente de una última pasada**: AUD-16, AUD-17 y AUD-18 los cierra
> el PR de frontend (se apoya en `master`, así que **no puede** tocar
> esta tabla). Cuando ese PR entre, hay que marcar esos tres aquí
> (con su número de PR) y recién después se borra el bloque de aviso de
> `AGENTS.md`, según la cláusula de cierre.

| ID | Responsable | Estado | PR / commit |
|----|-------------|--------|-------------|
| AUD-01 | Int3 | pendiente | — |
| AUD-02 | Int3 | pendiente | — |
| AUD-03 | Int3 | pendiente (opción 1 decidida) | — |
| AUD-04 | Int3 | pendiente | — |
| AUD-05 | Int3 | decisión de dominio | — |
| AUD-06 | Int3 | decisión de dominio | — |
| AUD-07 | Int3 | decisión de dominio | — |
| AUD-09 | Int1 | **cerrado** | PR #66 |
| AUD-10 | Int1 | **cerrado** | PR #66 |
| AUD-11 | Int1 | **cerrado: no aplica** (decisión 2026-10-28) | — |
| AUD-12 | Int1 | **cerrado** | PR #66 |
| AUD-13 | Int1 | **cerrado** | PR #65 |
| AUD-14 | Int1 | **cerrado** | PR #65 |
| AUD-15 | Int3 | pendiente | — |
| AUD-16 | Int2 | pendiente | — |
| AUD-17 | Int2 | pendiente | — |
| AUD-18 | Int2 | decisión de dominio | — |
| AUD-19 | Docs | **cerrado** | PR #64 |
| AUD-20 | Int3 | pendiente | — |
| AUD-21 | Int1 | **cerrado** | PR #67 |
| AUD-22 | Int1 | **cerrado** | PR #69 |
| AUD-23 | Int1 | **cerrado: los archivos quedan sin trackear** (decisión 2026-10-28) | — |
| AUD-24 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| AUD-25 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| AUD-26 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| AUD-27 | Int3 (criterio: Int1) | pendiente (Int3) — criterio de aceptación listo | PR #67 (test) |
| Nuevo: `palabras_clave_minimo` | Int3 | pendiente | — |
| Nuevo: plantillas no cuantitativas | Int3 | documentar | — |
| DSpace REST | Int1 | **cerrado: deprecado** | PR #65 |
