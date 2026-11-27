# Bitácora Semana 12 — ivanSanchezSil

- **Integrante**: ivanSanchezSil (Integrante 3 — Motor de reglas / Procesamiento)
- **Semana**: 12
- **Fechas**: 2026-11-12 → 2026-11-24 (semana en curso)
- **Rol**: extractor, motor, analizadores, reglas YAML, exportador/CLI y
  pruebas/factory del motor
- **Rama de trabajo**: `motor-orcid-asesor`
- **Base**: `upstream/master` `bbd5f80` (PR #118)
- **Plan**: [`PLAN_SEMANA12_MOTOR_CORRECTITUD.md`](PLAN_SEMANA12_MOTOR_CORRECTITUD.md)

---

## Objetivos de la semana

1. Ejecutar las tareas de correctitud del motor (`M1a`, `M1`–`M12`) en PRs
   pequeños, con regresión previa al arreglo.
2. Empezar por `M11` (paquete OPC del factory) y `M1a` (validación del
   extractor) porque desbloquean B6 y B5 de Int1.
3. Mantener intactos la API, la SPA, el userscript y `AGENTS.md`.

---

## Actividades realizadas

### 2026-11-12 — Plan de la Semana 12 (PR #97)

Se documentó el desglose de hallazgos `VA`/`NM` en tareas y PRs, con orden,
dependencias, criterios de aceptación, decisiones pendientes del encargado y
calendario de las semanas 12 y 13. El plan no declara corregido ningún
hallazgo.

### 2026-11-12 — M11 / VA-17: paquete OPC del factory (PR 12.1)

**Reproducción previa al arreglo**

```bash
PYTHONPATH=/home/ivan/pylibs:.:tests python3 - <<'PY'
import docx
from _docx_builder import compilar_docx, configuracion_base
docx.Document(compilar_docx(configuracion_base()))
PY
```

Resultado: `KeyError: "There is no item named 'media/logo.png' in the archive"`.
El ZIP solo tenía `[Content_Types].xml`, `_rels/.rels`, `word/document.xml`,
`word/header1.xml` y `word/footer1.xml`. Las relaciones de cabecera, pie,
imagen e hipervínculo estaban en `_rels/.rels` (raíz), no existía
`word/_rels/document.xml.rels` ni `word/_rels/header1.xml.rels`, y el PNG
nunca se escribía.

**Arreglo**

- `_rels/.rels` declara solo el documento principal.
- `word/_rels/document.xml.rels` declara cabecera, pie, imagen de portada e
  hipervínculo ORCID.
- `word/_rels/header1.xml.rels` declara el logo del membrete.
- Se escribe un PNG válido de 1×1 en `word/media/logo.png`.
- Si hay notas al pie, se agregan su relación y su `Override` en
  `[Content_Types].xml`; si no hay, no se declaran partes inexistentes.
- Regresión nueva en `tests/test_docx_factory_opc.py`: abre con
  `python-docx`, resuelve todos los destinos internos, comprueba que cada
  `r:id`/`r:embed` esté declarado en su parte, valida el PNG y exige tipo de
  contenido para cada parte.

**Verificación**

```bash
PYTHONPATH=/home/ivan/pylibs:.:tests python3 -m pytest tests/ -q
# 836 passed, 4 skipped, 6 xfailed

~/.local/bin/ruff check validator/ scripts/ tests/
~/.local/bin/ruff format --check validator/ scripts/ tests/
PYTHONPATH=/home/ivan/pylibs python3 -m mypy validator/ scripts/
# All checks passed / 81 files already formatted / Success
```

**Límites**

- No se regeneraron `docs/ejemplos/doc_bueno.docx` ni `doc_malo.docx`: B6 de
  Int1 es quien los regenera y refuerza la guardia. El comando es
  `python scripts/ejemplo_bueno_malo.py`.
- El PNG es un marcador de 1×1: las reglas solo cuentan nodos `a:blip`, no
  inspeccionan dimensiones ni píxeles.
- La medición real del logo sigue siendo M7 (VA-15), pendiente de decisión.

**Entrega a Int1**

- Commit `85690c5` (rama `semana12-m11-factory-opc`, PR 12.1).
- Comando de regeneración: `python scripts/ejemplo_bueno_malo.py`.

### 2026-11-13 a 2026-11-16 — M1 / VA-01, VA-02: formato efectivo y todo el texto (PR 12.3)

**Arreglo**

- `ResolvedorFormato` resuelve el formato efectivo con la precedencia de Word:
  formato directo → estilo de carácter → cadena `basedOn` del estilo de
  párrafo → `w:docDefaults`. Un ciclo de estilos se reporta como
  incumplimiento sin tumbar la validación, y `word/styles.xml` ausente o mal
  formado se trata como ausente.
- `AnalizadorFormato` (`formato_efectivo`) selecciona primero los párrafos y
  evalúa **todos** los runs con texto, incluidos los de hipervínculo. Una
  propiedad ausente se reporta como `(ausente)` y cuenta como incumplimiento.
- Se migran 16 reglas de fuente, tamaño, interlineado, alineación y negrita
  del cuerpo y de la carátula.
- El linter del DSL valida `parrafo_xpath` y `propiedad`.

**Corrección del alcance (`cuerpo_prosa`)**

`alineacion_cuerpo` con `contexto: cuerpo` ponía en rojo la tesis aprobada:
declaraba 270 valores evaluados y 19 incumplimientos, todos `(ausente)`. Los
19 no eran prosa: 5 ítems de lista, 13 títulos de tabla y figura y 1 línea de
leyenda de fórmula. Ninguno de esos estilos define `w:jc`, así que Word los
dibuja alineados a la izquierda.

- Se añade el contexto `cuerpo_prosa` sobre `_cuerpo_paras`: excluye los
  ítems de lista (`w:numPr` directo o estilo cuyo `w:name` sea `list
  paragraph`), los títulos de tabla y figura (estilo cuyo `w:name` contenga
  `caption`) y las líneas de nota o leyenda. La exclusión es por **nombre de
  estilo**, para que también funcione un Word en inglés.
- Solo `alineacion_cuerpo` cambia a ese contexto. `fuente_principal`,
  `tamano_cuerpo` e `interlineado` siguen con `contexto: cuerpo`, porque el
  texto de listas y títulos también debe revisarse en fuente, tamaño e
  interlineado.
- No se relaja `all_eq`: un párrafo de prosa sin `w:jc` sigue fallando.

**Corrección de integridad OPC**

La revisión de M11 señaló que `[Content_Types].xml` declaraba el `Override` de
`word/styles.xml` siempre, aunque el factory solo escribe esa parte cuando la
configuración trae `styles`. Un tipo de contenido que apunta a una parte
ausente rompe el paquete OPC.

- El `Override` de estilos se declara solo cuando la parte se escribe, igual
  que el de notas al pie.
- Regresión: `test_el_override_de_estilos_solo_se_declara_con_la_parte` y
  `test_cada_override_apunta_a_una_parte_existente`.

**Plantillas oficiales**

El resultado pasa de 1 error + 6 warnings a **2 errores + 6 warnings**: el
error nuevo es `caratula_titulo_negrita_mixta`, que se mantiene estricto por
decisión. La evaluación de plantillas es **orientativa** y un test
parametrizado fija ese resultado cuando `recursos/` está disponible.
`palabras_clave_minimo` se mantiene en `error` (decisión del 2026-11-08).

**Verificación**

```bash
PYTHONPATH=/home/ivan/pylibs:.:tests python3 -m pytest tests/ -q
# 863 passed, 9 skipped, 6 xfailed
```

**Límites**

- M1 queda como **implementado, pendiente de verificación**: el PR sigue
  abierto y la comprobación con la tesis aprobada y las cinco plantillas
  oficiales está en manos de la revisión.
- La heredad de estilos se resuelve por `basedOn`; los temas, la numeración,
  el formato condicional, los estilos de tabla y los cambios con seguimiento
  no se soportan (documentados en `ResolvedorFormato`).

**Entrega a Int1**

- Commits `8c63dcc`, `c3577f6` y `57073fd` (rama `semana12-m1-formato-efectivo`,
  PR 12.3).
### 2026-11-14 — M4 / VA-05: declaraciones múltiples (PR #103)

**Reproducción previa al arreglo:** los 6 casos nuevos de
`TestDeclaracionesMultiples` fallaban con el código anterior; las 3
declaraciones del mismo tipo ya pasaban.

**Arreglo:** `DeteccionTipo._tipo_declarado` devuelve todas las casillas
marcadas; `analizar` agrupa por tipo. Dos tipos distintos publican
`TIPO_CONTRADICTORIO` y el centinela `tipo_documento_contradictorio`; repetir
el mismo tipo no cambia la decisión. La evidencia queda ordenada por tipo.

**Verificación:** `924 passed, 4 skipped`; ruff, ruff format, mypy y linter
limpios; CI verde y PR `MERGEABLE`/`CLEAN`.

**Entrega:** commits `5fb2344` (código, tests y DSL) y `65c39f5` (handovers),
rama `semana12-m4-tipo-declarado`, PR #103 apilado sobre #75.

### 2026-11-15 — M5 / VA-06, VA-07: Resumen, Abstract y palabras clave

**Reproducción previa al arreglo:** `resumen_longitud` solo tenía mínimo 159 y
contaba la línea de palabras clave como prosa; `palabras_clave_minimo` solo
revisaba el Resumen, contaba tras el primer `:` global y no tenía máximo; no
existía ninguna regla que detectara un Abstract sin cuerpo.

**Arreglo:**

- `resumen_longitud`: 159–220 palabras; `excluir` descarta la línea de palabras
  clave antes de contar.
- `palabras_clave_minimo`: 3–5 claves; `secciones` cuenta Resumen y Abstract
  por separado; admite las etiquetas `Palabras clave` y `Keywords`.
- `abstract_contenido`: nuevo warning que exige al menos una palabra de cuerpo
  en el Abstract, sin contar su línea de claves.
- `patron_cantidad`: admite `secciones`, `excluir` y `cantidad_maxima`;
  `count_entries` cuenta por párrafo. El linter valida la forma nueva.

**Verificación:** `935 passed, 4 skipped`; 50 reglas (44 evaluadas en el
documento base); ruff, ruff format, mypy y linter limpios; ejemplos
regenerados.

**Decisiones ratificadas (2026-11-16):** la tokenización del Resumen es `\w+`;
`abstract_contenido` se queda en `warning`; Resumen y Abstract son
obligatorios los dos (3–5 palabras clave en cada uno) y se aceptan las dos
etiquetas, `Palabras clave` y `Keywords`. La ratificación confirma el
comportamiento ya implementado; el manual local no está en el repo.

**Entrega:** commit `feeab66`, rama `semana12-m5-resumen-abstract`, PR apilado
sobre #103.

### 2026-11-15 — M6 / VA-14: nombre del anexo «Base de datos»

**Reproducción previa al arreglo:** con la tesis real titulada «Base de datos»
(no «Base de datos cuantitativa»), `anexos_minimos_cuantitativo` reportaba el
ítem como faltante (`faltan=['Base de datos cuantitativa']`).

**Arreglo:** el ítem 5 de `anexos_minimos_cuantitativo` pasa a «Base de datos»
y se añade la nota `EVALUADO` con la decisión de 2026-11-08. La regla sigue en
`warning`. Se documenta que la detección es textual (un anexo escaneado como
imagen requiere revisión manual) y que la comparación por subcadena hace que
«Base de datos cualitativa» también satisfaga el ítem.

**Decisión ratificada (2026-11-16):** la comparación por **subcadena** se
mantiene; no se exige coincidencia de título completo. La ratificación confirma
el comportamiento ya implementado.

**Verificación:** `937 passed, 4 skipped`; regresión `test_m6_*` (título real
reconocido y ausencia informada); ruff, ruff format, mypy y linter limpios;
ejemplos regenerados con el valor esperado nuevo.

**Entrega:** commit `c2eb680`, rama `semana12-m6-anexo-base-datos`, PR apilado
sobre #104.

### 2026-11-15 — M7 / VA-15: medir el logo de la carátula

**Reproducción previa al arreglo:** `caratula_logotipo_tamano` anunciaba
«4,84 cm de alto x 6,73 cm de ancho» pero solo contaba blips: una imagen de
cualquier tamaño en el cuerpo o en la carátula pasaba la regla.

**Arreglo:** `AnalizadorImagen` mide el `wp:extent` del `wp:inline`/
`wp:anchor` que contiene cada blip (ancho = `cx`, alto = `cy`; 360000 EMU
por cm). La regla declara `contexto: caratula` (primera sección),
`ancho_cm: 6.73`, `alto_cm: 4.84` y `tolerancia_cm: 0.1` (1 mm), con nota
`EVALUADO`. Una imagen sin `wp:extent` falla (`tamanos=sin_dimensiones`):
no se da por buena en silencio. El linter valida claves y dimensiones de
`imagen`.

**Verificación:** `948 passed, 4 skipped`; regresión `test_m7_*` (3 casos:
tamaño correcto, tamaño incorrecto y logo solo en el cuerpo); linter con 5
pruebas (8 casos) para la forma de `imagen`; ruff, ruff format, mypy y
linter limpios; ejemplos regenerados.

**Decisión ratificada (2026-11-16):** la tolerancia de medición es de
**0,1 cm** (1 mm), la que ya se implementaba. El manual fija el tamaño del
logo pero no da tolerancia. La ratificación confirma el comportamiento ya
implementado.

**Entrega:** commit `b92f7f3`, rama `semana12-m7-logo`, PR apilado
sobre #105.

### 2026-11-23 — PR 1 del reparto ORCID: captura del ORCID del asesor

Retblast repartió el paso de ORCID del asesor a campo detectado en tres PR:
motor (Int3), API/userscript (Int1) y frontend (Int2). Este PR es solo el
motor: no cambia el contrato HTTP, no toca `api.py` ni `api_models.py`, y la
validación de checksum y la publicación en `ficha_deposito` quedan para el
PR 2 de Int1.

**Reproducción previa al arreglo** (`tests/_caratula_real.py`):

- asesor sin nombre y solo ORCID → `dc.contributor.advisor` con la URL;
- autor con ORCID en el mismo párrafo → el autor desaparecía de la ficha;
- asesor con ORCID pegado → el nombre publicaba el identificador.

**Arreglo en `reglas_ficha.yaml`:**

- regla nueva `ficha_orcid_asesor` (`renati.advisor.orcid`) sobre la etiqueta
  del asesor y los dos párrafos siguientes, con `filtro` y `patron` para ORCID
  con o sin `https://orcid.org/`;
- `ficha_asesor` pasa de `contains(..., 'asesor')` a `starts-with`, descarta
  la línea de ORCID pura y recorta el sufijo; el XPath se corta en «Línea de
  investigación:» para no publicar esa etiqueta como nombre cuando el asesor
  solo trae ORCID;
- `ficha_autores` deja de excluir párrafos por `contains(..., 'orcid.org')`:
  ahora filtra solo la línea pura y recorta el ORCID final.

**Verificación:** 32 pruebas entre `tests/test_ficha_extraccion.py` (8 claves
en el doc bueno, valor y página del ORCID) y `tests/test_captura_ficha.py`
(7 casos nuevos de aceptación). Semáforo y resumen intactos: son reglas de
captura. Los tests los escribe Int3 en este PR con autorización de retblast
para que se integre solo.

**Documentación:** nota de cambio con fecha en el diseño 17 §4 y en el
handover del motor §2; cierre de NM-02, NM-05 y NM-07 en la tabla §11 del
handover de auditoría; nota en el README para dejar claro que la API sigue
tratando el campo como manual hasta el PR 2.

**Entrega:** rama `motor-orcid-asesor`, PR abierto contra `upstream/master`;
sin fusión (retblast integra).

### 2026-11-24 — Ajustes de la revisión de retblast en el PR #124

Retblast revisó `ba9d755` en un clon aparte (suite 1149/9 frente a 1142/9 en
`bbd5f80`, linter del DSL, mypy y OpenAPI limpios) y pidió dos correcciones
antes de fusionar:

1. El predicado que cortaba en «Línea de investigación:» era absoluto: con la
   línea **antes** del bloque «ASESOR(A):», el nombre dejaba de detectarse. Se
   acotó a una línea con un párrafo de asesor precedente. El mismo patrón en
   `ficha_autores` también borraba los autores si la línea iba antes de
   «AUTORES:»; se acotó con un párrafo de autor precedente.
2. `quitar_sufijo` dejaba «ORCID:» pegado al nombre cuando el identificador no
   llevaba URL. El patrón acepta ahora el prefijo opcional «(Código) ORCID:»
   en asesor y autores.

**Cobertura nueva:** ORCID desnudo bajo la etiqueta, ORCID con etiqueta en
asesor y autor, y línea de investigación previa a cada bloque. Las 4 nuevas
fallaban antes del arreglo; la ficha queda en 37 pruebas verdes.

**Decisión confirmada:** retblast aceptó que la clave quede **ausente** en
`reporte["ficha"]` cuando no hay ORCID (la API fija la forma en el PR 2). No
se agregó el flag en `AnalizadorExtraccion`.

**Documentación:** notas fechadas en el diseño 17 §4 y en el handover del
motor §2 y §4 (lista de claves acordadas actualizada con `renati.advisor.orcid`).

### 2026-11-24 — RI-07: XPath de carátula acotado; RI-08 documentado

Tras la fusión del PR #124, retblast fusionó y no respondió el comentario con
las preguntas sobre RI-07/08/09. Se avanza con lo que no depende de evidencia
externa; RI-09 se entrega en el PR #125 y RI-07 en su propio PR.

- **RI-07:** `ExtractedDocx.xpath()` evalúa las consultas con contexto
  `caratula`/`caratula_ficha` en un árbol reducido a la carátula y devuelve
  los nodos originales mediante un mapa copia→original. Así los ejes
  `following/preceding-sibling::` no recorren el cuerpo completo. Los
  resultados no-elemento siguen por el camino anterior.
- **Regresión:** `tests/test_caratula_xpath.py` (35 pruebas) compara las 32
  expresiones de carátula del catálogo contra el filtro anterior y comprueba
  que semáforo, resumen, resultados y ficha sean idénticos con 200 párrafos
  de cuerpo y etiquetas engañosas. Se conservan el orden de autores, los
  cortes por asesor/línea y el ORCID separado del nombre.
- **Medición sintética local:** 0,204 s → 0,001 s en
  `caratula_autores_tamano` (×227) y 1,493 s → 0,002 s en `ficha_autores`
  (×792) con 250 párrafos de cuerpo.
- **Corpus real (mismo día, tras el mensaje del usuario):** aparecieron las
  dos tesis y las cinco plantillas en `proyectos/vistobueno_src/vistobueno/`.
  Se agregó `scripts/medir_caratula.py` para repetir la medición y se
  comparó el reporte antes/después en los siete documentos: 37,65 s → 2,63 s
  (aprobada, verde 0 errores/5 advertencias) y 37,20 s → 2,22 s (no
  aprobada, rojo 4 errores/5 advertencias), con 42/54 reglas evaluadas y
  ficha idéntica. Las plantillas dieron 2 y 4 errores con 9 advertencias,
  también sin cambios. Consultas críticas: 10,30 s → 0,007 s y 16,60 s →
  0,010 s. Falta solo la carga consecutiva en la API/Firefox de retblast.
- **RI-08:** se documenta la discrepancia (descripción anuncia línea, ciudad
  y año; selectores cubren autores y asesor; REQ-24/26 parciales y REQ-27 en
  conflicto) y se deja la regla sin cambio hasta cotejar el manual y recibir
  la decisión de retblast sobre tamaño y severidad.
### 2026-11-24 — RI-09: ejemplos, conteos y documentación

Retblast fusionó el PR #124 y mandó aparte los hallazgos RI-07, RI-08 y RI-09.
Como no respondió a las preguntas del comentario del PR, se avanza con lo que
no depende de evidencia externa. Para esto el usuario autorizó explícitamente
tocar `AGENTS.md`.

- README: los ejemplos principales de CLI usan ahora `reglas_unt.yaml`, el
  mismo YAML que carga la API; el esquema legacy queda marcado como comparación
  histórica (con ese esquema la tesis aprobada daba rojo).
- `scripts/reglas_activas.py`: toma los conteos de `build_report()["resumen"]`
  y filtra no aplicables y capturas para el detalle. Antes contaba `resultados`
  directamente y mezclaba categorías.
- `AGENTS.md`: 50 → 54 reglas en las cuatro referencias, lista correcta de las
  10 reglas no aplicables al doc bueno y nota que distingue catálogo de filas
  del reporte (54 reglas, 44 evaluadas, 10 no aplicables en el doc bueno).
- Se incorpora `docs/PLAN_SEMANA12_MOTOR_CORRECTITUD.md`, que faltaba en esta
  rama y dejaba roto el enlace de la bitácora.

**Verificación:** `tests/test_reglas_activas.py` compara los cinco conteos del
script con el resumen del motor.

### 2026-11-25 — RI-08: los 12 pt de carátula cubren los cinco bloques

El usuario aclaró que el manual oficial estaba en el mismo ZIP de recursos de
`Descargas` junto con las tesis y las plantillas. Al cotejarlo, los párr.
179-183 fijan 12 pt para autores, asesor, línea de investigación, ciudad/país
y año en curso: la duda que había quedado abierta se resolvía con esa fuente.

- Se amplía `caratula_autores_tamano` (sigue `severidad: error`) con tres
  comprobaciones: línea (etiqueta + valor), ciudad (último «Trujillo» de la
  carátula, no la Universidad) y año (`contexto: caratula_ficha`, que incluye
  el párrafo de cierre de sección de las tesis reales). Todas usan `all_eq`
  sobre los runs con texto. La `cita` ahora reproduce literalmente los cinco
  párrafos del manual y la `ubicacion` se ajusta a párr. 179-183.
- Nueva regresión `tests/test_ri08_caratula_tamano.py`: 36 pt en línea,
  ciudad o año separado pasan a rojo; el año a 12 pt sigue en verde. Se
  actualizó el caso AUD-05 del run vacío para incluir los tres bloques nuevos.
- Se regeneraron los dos JSON golden de `docs/ejemplos/`; solo cambian
  `ubicacion` y `cita` de esta regla. Los DOCX versionados no se tocaron.
- Matriz: REQ-24 y REQ-26 siguen `PARCIAL` por las propiedades que faltan
  (letras mixtas, centrado), pero ya registran la evidencia de 12 pt; REQ-27
  mantiene `CONFLICTO` solo por año en curso frente a sustentación.
- Corpus real: la regla queda en verde en la tesis aprobada, la no aprobada
  y las cinco plantillas; no cambian semáforo, resumen, ficha ni los cuatro
  errores de la tesis no aprobada.

**Verificación:** `tests/test_ri08_caratula_tamano.py` y la suite enfocada de
carátula pasan; `ruff check`, `ruff format --check`, `mypy validator/ scripts/`
y el escáner de secretos sin hallazgos. Retblast fusionó el PR #126 (RI-07)
mientras se hacía este trabajo. RI-08 se entregó en el PR #128, abierto y sin
merge de mi parte; CI verde en https://github.com/retblast/vistobueno/actions/runs/45615829450
y aviso de pendientes publicado en #128 y #126.

### 2026-11-26 — REQ-24/REQ-26: letras mixtas y centrado de carátula

El usuario pidió avanzar con lo que se podía hacer de la lista de pendientes
sin decisión externa. RI-08 ya cubría el tamaño (12 pt) de los cinco bloques,
pero al cotejar el manual seguían sin evidencia propia las letras mixtas y el
centrado de línea y ciudad. Se trabajó sobre `ri08-tamano-caratula`, la rama
del PR #128, para no abrir otro PR.

- `caratula_ciudad_pais_negrita`: el `[1]` heredado medía la Universidad (las
  dos líneas contienen «Trujillo»); ahora usa `[last()]`. El patrón antes
  aceptaba solo mayúsculas; ahora exige al menos una mayúscula y una
  minúscula por run con letras y admite los runs de solo espacio que hay en
  la tesis real. Se quitó el acoplamiento con la negrita de la Universidad en
  `tests/_mutations.py`.
- `alineacion_caratula_todos_elementos`: se agregaron la etiqueta y el valor
  de «línea de investigación» al XPath de centrado.
- `caratula_linea_investigacion`: se conserva el catálogo RCU-220 y se añade
  el patrón mixto sobre el párrafo de valor; la cita ahora incluye el párr.
  181 del manual.
- Factory: `Trujillo - Perú, 2026` en vez de `TRUJILLO - PERÚ, 2026`
  (placeholder, sin datos personales).
- Nueva regresión `tests/test_req24_26_caratula_mixtas_centrado.py` (7 casos)
  y ajuste de las fixtures de `test_caratula.py` y `test_paridad_formatos.py`.
- Documentación: matriz REQ-24 y REQ-26 a `CERRADO`, handover de ficha §9 con
  el detalle y la cita actualizada en `docs/ejemplo_respuesta_motor.json`.
- Se regeneraron los DOS json y los DOS DOCX versionados de `docs/ejemplos/`;
  el cambio del texto del factory era intencional, así que esta vez sí se
  conservan los DOCX. En los golden solo cambian la cita y el tamaño de
  archivo.

**Verificación:** 107 pruebas enfocadas pasadas; suite completa 1223 pasadas,
9 omitidas y 1 fallo preexistente de WeasyPrint 70 (CI usa 69). `ruff check`,
`ruff format --check`, `mypy` y el escáner de secretos limpios. Corro el corpus
real por petición explícita del usuario: las tres reglas en verde en los siete
documentos (2 tesis + 5
plantillas) y semáforo/resumen sin cambios: aprobada 0 errores/5 advertencias,
no aprobada 4/5, plantillas 2 o 4 errores con 9 advertencias.

**Entrega:** commits `74c3216` y `dd09654` pusheados a
`origin/ri08-tamano-caratula` (PR #128, sin merge). CI verde en
https://github.com/retblast/vistobueno/actions/runs/45620297259 y aviso a
retblast en https://github.com/retblast/vistobueno/pull/128#issuecomment-7163377535.

### 2026-11-26 — RN-03, RN-02 y RN-04: primera tanda de la revisión de retblast

Se abre `rn-primera-tanda` sobre `upstream/master` `75aae02` (incluye los PR
#131 y #132) con tres commits atómicos, **sin merge**:

- `c4acf1e` (RN-03): el catálogo de líneas de investigación se coteja con el
  párrafo completo dentro de la carátula, no con cada `w:t`. La comprobación
  de letras mixtas se mide run por run. Nueva regresión
  `tests/test_rn03_linea_investigacion.py` (4 casos).
- `9e81cbe` (RN-02): `AnalizadorRegex` gana `unidad: run | nodo` (defecto
  `run`), validada por el linter y documentada en `docs/DSL.md`. La regla de
  autores cubre todos los nombres hasta el asesor, excluye ORCID, mide
  negrita por run y capitalidad por nombre completo. El usuario confirmó
  mantener el criterio `EVALUADO` de mayúsculas y minúsculas. Nueva regresión
  `tests/test_rn02_autores_bloque.py` (6 casos).
- `24f5950` (RN-04): el detalle muestra twips crudos solo cuando el redondeo
  a cm colisiona (1417 frente a 1418 → «2.50 cm»), sin tocar la comparación
  exacta ni aplicar `tolerancia: 1`. Nueva regresión
  `tests/test_rn04_diagnostico_margen.py` (3 casos).

**Documentación:** matriz REQ-06/07/08/09 a `CERRADO`, REQ-25 a `CERRADO`,
REQ-20 queda `DECIDIDO` con la cobertura de RN-02 y la decisión de biblioteca
pendiente; handover de ficha §9 con el detalle de los tres cierres; README y
`docs/DSL.md` actualizados en los commits de cada regla.

**Verificación:** corro el corpus real después de CADA cambio (dos tesis y
cinco plantillas, sin PII en el repo). Siempre: aprobada verde `0/5`, no
aprobada rojo `4/5`, EDUCACIÓN INICIAL rojo `2/9`, otras cuatro plantillas
rojo `4/9`, 54 evaluadas; sin cambio de semáforo. Suite completa final
`1276 passed, 14 skipped` más el fallo preexistente de WeasyPrint 70 (CI usa
69). Enfocadas de RN-04 con regresiones: 57 pasadas. `ruff check`,
`ruff format --check`, `mypy` y el escáner de secretos limpios en las rutas
que revisa CI. Golden de `docs/ejemplos/` sin regenerar: ningún documento
versionado cambió de salida.

**Pendiente:** RN-01 (verificación visual en Word), RN-10 (frontend/API),
RN-11 a RN-14 (decisión de biblioteca) y la tolerancia de 1 twip de RN-04.

### 2026-11-26 — Seguimiento de la revisión de retblast (PR #134)

Retblast revisó la tanda: CI verde, `1277 passed, 14 skipped` en su entorno y
corpus sin cambios. Pidió un ajuste antes de integrar y dos menores:

- `3445fce`: los dos XPath del bloque de autores descartan también los ORCID
  desnudos entre paréntesis, sin depender de la palabra `orcid`. Dos tests
  nuevos en `tests/test_rn02_autores_bloque.py` (ORCID terminado en `X`
  ignorado; segundo autor en negrita sigue fallando). Queda documentado el
  límite del ORCID pegado al nombre en el mismo párrafo.
- `233a416`: el linter del DSL rechaza claves desconocidas en `patron_texto`
  (p. ej. `unidade: nodo`), con dos tests en `tests/test_t2_linter.py` y nota
  en `docs/DSL.md`.
- Matriz: REQ-06/07/08/09 bajan a `DECIDIDO` mientras biblioteca decide la
  tolerancia de 1 twip.

El corte del bloque cuando falta la etiqueta del asesor queda como
seguimiento, según la recomendación de retblast. Corpus repetido tras cada
cambio: las siete cifras y los semáforos siguen idénticos. Suite final
`1280 passed, 14 skipped` con el mismo fallo preexistente; `ruff`, `mypy` y
el escáner de secretos limpios en las rutas de CI.

---

## Evidencias

| Evidencia | Archivo / comando |
|---|---|
| Plan de la semana | `docs/PLAN_SEMANA12_MOTOR_CORRECTITUD.md` (PR #97) |
| Reproducción de M11 | `KeyError: media/logo.png` con `python-docx` |
| Regresión | `tests/test_docx_factory_opc.py` (12 casos) |
| Arreglo | `tests/_xml_constants.py`, `tests/_docx_builder.py` |
| Suite M11 | 836 passed, 4 skipped, 6 xfailed |
| Regresión M4 | `tests/test_tipo_documento.py::TestDeclaracionesMultiples` (9 casos) |
| Regresión M5 | `tests/test_f3_mecanizacion.py::TestM5ResumenAbstract` (10 casos) |
| Regresión M6 | `tests/test_auditoria_motor.py::test_m6_*` (2 casos) |
| Regresión M7 | `tests/test_auditoria_motor.py::test_m7_*` (3 casos) |
| Linter de `imagen` | `tests/test_t2_linter.py` (5 pruebas, 8 casos) |
| Suite M4 | 924 passed, 4 skipped |
| Suite M5 | 935 passed, 4 skipped |
| Suite M6 | 937 passed, 4 skipped |
| Suite M7 | 948 passed, 4 skipped |
| Estado de los hallazgos | §2 de `HANDOVER_CORRECTITUD_2026-11-12.md` |
| Reproducción del ORCID del asesor | `tests/_caratula_real.py` (placeholders, sin PII) |
| Reglas de captura | `reglas_ficha.yaml`: `ficha_orcid_asesor`, `ficha_asesor`, `ficha_autores` |
| Suite de ficha | `pytest tests/test_ficha_extraccion.py tests/test_captura_ficha.py -q` → 32 passed (37 tras la revisión del 2026-11-24) |
| Cierre normativo | §11 de `docs/HANDOVER_AUDITORIA_2026-10-26.md` (NM-02, NM-05, NM-07) |
| RI-07 | `tests/test_caratula_xpath.py`, `scripts/medir_caratula.py`, diseño 17 §9 y handover de ficha §9 |
| RI-08 | PR #128: `tests/test_ri08_caratula_tamano.py`, `reglas_unt.yaml` (cinco bloques a 12 pt), handover de ficha §9 y matriz REQ-24/26/27 |
| RI-09 | `tests/test_reglas_activas.py`, README (CLI con `reglas_unt.yaml`), `AGENTS.md` (54 reglas) y plan de Semana 12 restaurado |
| REQ-24/REQ-26 | `tests/test_req24_26_caratula_mixtas_centrado.py`, `reglas_unt.yaml` (patrón mixto, `[last()]`, centrado de línea), matriz y handover de ficha §9 |
| RN-03 | `c4acf1e`, `tests/test_rn03_linea_investigacion.py`, `reglas_unt.yaml` (catálogo por párrafo en carátula) |
| RN-02 | `9e81cbe`, `tests/test_rn02_autores_bloque.py`, `unidad: nodo` en `AnalizadorRegex`, `docs/DSL.md` |
| RN-04 | `24f5950`, `tests/test_rn04_diagnostico_margen.py`, `validator/detalle.py`, handover de ficha §9 y matriz REQ-06/07/08/09 |
| Revisión PR #134 | `3445fce` (ORCID desnudo), `233a416` (claves de `patron_texto`), handover de ficha §9 y matriz REQ-06/07/08/09 a `DECIDIDO` |

---

## Dificultades y aprendizajes

- El extractor propio toleraba el paquete roto, así que la suite no lo
  detectaba; hizo falta abrir el DOCX con `python-docx` para reproducir el
  fallo que ve Int1.
- OPC exige que cada parte declare sus propias relaciones: un `Id` de
  `document.xml` no es visible desde `header1.xml`, aunque el nombre coincida.
- Declarar relaciones o tipos de contenido de partes ausentes también rompe
  el paquete; por eso las notas al pie se agregan solo cuando existen.
- El mismo criterio aplica a los estilos: M1 añadió `word/styles.xml` al
  factory y tuvo que declarar su `Override` de forma condicional, porque el
  paquete base no lleva esa parte. Un `Override` colgante no lo detecta el
  extractor propio (tolera el paquete roto), así que la única guarda es abrir
  el DOCX con `python-docx` y comprobar que cada tipo de contenido tiene su
  parte.

---

## Plan de la semana siguiente

1. Abrir y revisar el PR 12.1 (M11).
2. Implementar M1a: validar la entrada del extractor y documentar las partes
   OPC mínimas admitidas (desbloquea B5 de Int1).
3. Continuar con M1 (formato efectivo y revisión de todo el texto).
4. Coordinar con Int1 e Int2 los PR 2 y 3 del reparto ORCID: checksum y
   publicación del campo extraído, y aviso de verificación en la SPA.
