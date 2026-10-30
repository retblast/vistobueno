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
| AUD-28 | Int1 | **cerrado** (Host / DNS rebinding) | `8efffd7` (PR pendiente) |
| AUD-29 | Int1 | **cerrado** (fórmulas en JSON) | `8efffd7` (PR pendiente) |
| AUD-30 | Int1 | **cerrado** (acceso al papeleo) | `8efffd7` (PR pendiente) |
| AUD-31 | Int1 | **cerrado** (cupo adaptativo por CPU) | `8efffd7` (PR pendiente) |
| AUD-32 | Int1 | **cerrado** (hora de Perú) | `f0ba1f0` (PR pendiente) |
| AUD-33 | Int1 | **cerrado** (botón "+" del userscript) | `22e6a19` (PR pendiente) |
| AUD-34 | Int1 | **cerrado** (claves entre comillas en el escáner) | `efca435` (PR pendiente) |
| Nuevo: cache compilado por hilo | Int3 | pendiente (propuesta de Int1, §12.3) | — |

---

## 12. Propuestas de Int1 para el área de Int3 (NO aplicadas)

Estas propuestas se escribieron desde Int1 (API) y se **revirtieron antes
de commitear**: `engine.py`, `compilador.py`, `analizadores.py`,
`exportador.py` y los YAML de reglas son área de Int3 (motor), según la
tabla de responsabilidades de `AGENTS.md`. Quedan documentadas acá, con el
diff exacto, para que Int3 las implemente, las descarte o las aplique.

> **Estado**: nada de esto está en el repo. Los archivos del motor están
> sin tocar. Los parches se transcriben tal cual se escribieron.

### 12.1 AUD-04 — notas `EVALUADO` para las dos reglas de carátula

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
