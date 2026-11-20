# Handover Integrante 3 — motor — 2026-11-12

**Estado:** M1 a M7 implementados y fusionados en `master` el 2026-11-17.
Merges: M1 `f6428d1` (#100), M1a `7d90502` (#99), M2 `2286886` (#101), M3
`0a6d78b` (#102), M4 `32a3c13` (#103), M5 `4a1ae60` (#104), M6 `a666778`
(#105) y M7 `de0ca8b` (#106). M8 (VA-16) está **corregido en código** en el
PR #115 (abierto, pendiente de fusión y de la medición con plantillas y
tesis real); M9 (VA-12) está corregido en código en el PR #113 (abierto,
pendiente de fusión). Quedan pendientes M10 (VA-18) y M12 (NM-01 a NM-07).
Ver [índice y estado común](HANDOVER_CORRECTITUD_2026-11-12.md).
Las dependencias de [Int1](HANDOVER_CORRECTITUD_INT1_2026-11-12.md),
[Int2](HANDOVER_CORRECTITUD_INT2_2026-11-12.md) e
[Int3](HANDOVER_CORRECTITUD_INT3_2026-11-12.md) no autorizan a editar sus archivos.

## 1. Tareas propias

### M0. Terminar la integración de PR #75 — VA-13 / AUD-24 a AUD-27

**Archivos:** los del PR #75 y su documentación.

- Consulta 2026-11-12: abierto, head `8c0a6c8`, checks verdes, conflictos.
  PR #73 ya está mergeado. El autor de #75 resuelve su integración.
- Conservar las correcciones actuales de índice/anexos. No reemplazar archivos
  enteros de `master` con versiones antiguas de la rama.
- Evidencia: rama exacta, 823 passed / 4 skipped; código funcional aplicado a
  la base auditada, 842 passed / 4 skipped. Esos conteos son evidencia histórica.
- **Aceptación:** ambas tesis capturan dos autoras completas, asesora, año 2026,
  resumen y palabras clave limpias. Comprobar también las cinco plantillas.
  Quitar xfail solo cuando el caso pase. Cierre tras integración, no por el body.

### M1a. Validar la entrada del extractor — VA-11

**Archivos:** `validator/extractor.py`, `tests/test_extractor_edgecases.py`.

- Definir una excepción de documento inválido para B5. Validar XML, raíz,
  namespace y cuerpo. Documentar qué partes OPC mínimas admite el motor.
- Conservar límites de descompresión y pruebas contra ZIP hostil. No usar un
  `except Exception` que convierta defectos del servidor en entradas inválidas.
- **Aceptación:** XML truncado, raíz ajena y cuerpo ausente fallan de forma
  controlada; documentos admitidos y fixtures válidos siguen extrayéndose.
- **Decisión (2026-11-15):** una parte opcional presente pero mal formada
  (encabezado, pie o notas al pie) también invalida el documento completo
  (`422`). Es defendible porque Word tampoco abriría ese archivo y evita
  validar un documento con partes corruptas; queda declarado aquí, no solo
  en el docstring del extractor.

### M1. Resolver formato efectivo y revisar todo el texto — VA-01, VA-02

**Archivos:** `extractor.py`, `analizadores.py`, `reglas_unt.yaml`, tests/factory.

- Leer `styles.xml`, `docDefaults`, estilos de párrafo/carácter, `basedOn` y
  propiedades directas. Definir precedencia y detectar ciclos sin bloquearse.
- Evaluar cada run con texto, incluidos hipervínculos. No usar solo `w:r[1]`.
  No seleccionar solo párrafos que ya declaran `w:jc` o `w:spacing`.
- Seleccionar primero los párrafos/runs sujetos a la regla; resolver después
  el valor efectivo. No ignorar una propiedad ausente ni suponer que cumple.
- Declarar límites para numeración, formato condicional, temas u otras fuentes
  que no se resuelvan. No prometer soporte completo por leer `basedOn`.
- Conservar exclusiones de dominio acordadas. La asignación de Heading1 no
  puede eximir texto arbitrario sin un alcance de títulos declarado y probado.
- **Aceptación:** primer run vacío; segundo run Arial 36 pt; estilo incorrecto;
  formato directo y heredado equivalentes; propiedades ausentes; estilo de
  carácter; hipervínculo; cadena de estilos; ciclo; párrafo con estilo de título.
  Una infracción local se detecta sin rechazar el documento equivalente correcto.

### M2. A4 en todas las secciones aplicables — VA-03

**Archivos:** `reglas_unt.yaml`, `analizadores.py`, pruebas de secciones.
No cambiar globalmente la semántica de `eq`: otras reglas la usan.
Comparar todas las secciones sujetas a A4 y normalizar orientación.
**Aceptación:** portada A4 + cuerpo Letter falla; A4 horizontal legítimo pasa;
señalar la sección culpable. Documentar el alcance de anexos y carátula.

### M3. Corregir paginación y su grado de certeza — VA-04

**Archivos:** `_paginacion_para` en `extractor.py`, analizador de paginación,
`tests/test_f2_paginacion.py`, documentación de la ubicación por página.

- Procesar saltos por orden y valor. `pageBreakBefore` afecta al propio párrafo;
  `w:val="0"` no crea salto. Contar varios saltos dentro del mismo párrafo.
- Corregir la prueba existente que espera el párrafo anterior para break-before.
- Distinguir página desconocida/estimada de página comprobada. No inventar
  precisión si faltan marcadores o dependen de render/caché de Word.
- **Aceptación mínima:** `[1,2]` con break-before en el segundo párrafo;
  `[1,3]` con dos saltos en el primero; `[1,1]` con break-before desactivado.
  Probar saltos de sección, marcadores ausentes y párrafo que cruza página.

### M4. Detectar declaraciones múltiples — VA-05

**Archivos:** `DeteccionTipo._tipo_declarado`, pruebas de tipo de documento.
Recoger todas las casillas marcadas antes de decidir. Dos tipos diferentes
producen contradicción; repetir el mismo tipo no cambia la decisión.
**Aceptación:** cuantitativo + cualitativo marcados no dan verde; invertir el
orden conserva el resultado; comprobar casillas en párrafos, tablas y controles.

- **Estado 2026-11-14:** corregido en `5fb2344`. `_tipo_declarado` devuelve
  todas las declaraciones; dos tipos distintos publican `TIPO_CONTRADICTORIO`
  y el centinela `tipo_documento_contradictorio`, y repetir el mismo tipo no
  cambia la decisión. Evidencia: `924 passed, 4 skipped`; ruff, ruff format,
  mypy y linter limpios.

### M5. Resumen, Abstract y palabras clave — VA-06, VA-07

**Archivos:** `reglas_unt.yaml`, analizadores de cantidad/sección, tests/factory.

- Leer el manual local. Resumen: 159–220 palabras; palabras clave: 3–5.
  Separar prosa y etiquetas antes del conteo. Probar límites exactos.
- Revisar Resumen y Abstract por separado. Un título ABSTRACT vacío no prueba
  que exista su contenido. Admitir las etiquetas de cada idioma documentadas.
- Verificar en el manual qué límites se aplican al Abstract. No copiar límites
  ni inventar severidades sin fuente. Registrar cualquier decisión pendiente.
- **Aceptación:** 158/159/220/221 palabras; 2/3/5/6 claves; Abstract vacío;
  solo un idioma correcto; palabras clave excluidas del conteo de prosa.
  Mil palabras y diez claves generan la observación correspondiente.
- Mantener `palabras_clave_minimo` en error. Si se agregan reglas, actualizar
  mutaciones, conteos, ejemplos y contrato. No debilitar las guardias existentes.

- **Estado 2026-11-15:** corregido en `feeab66`. `resumen_longitud` exige
  159–220 palabras y excluye del conteo la línea de palabras clave;
  `palabras_clave_minimo` exige 3–5 claves y cuenta Resumen y Abstract por
  separado, admitiendo `Palabras clave` y `Keywords`; `abstract_contenido`
  detecta un Abstract sin cuerpo. `patron_cantidad` admite `secciones`,
  `excluir`, `cantidad_maxima` y `count_entries` por párrafo. Evidencia:
  `935 passed, 4 skipped`; ruff, ruff format, mypy y linter limpios; 50 reglas
  (44 evaluadas en el documento base).
- **Decisiones ratificadas (2026-11-16):** la tokenización del Resumen es
  `\w+`; `abstract_contenido` se queda en `warning`; **Resumen y Abstract son
  obligatorios los dos** (3–5 palabras clave en cada uno) y se aceptan **las
  dos** etiquetas, `Palabras clave` y `Keywords`. Son las que ya estaban
  implementadas: la ratificación confirma el comportamiento, no lo cambia.
  La equivalencia Resumen/Abstract y la autoría de la traducción siguen
  siendo revisión humana.

### M6. Aplicar el nombre de anexo decidido — VA-14

**Archivos:** `reglas_unt.yaml`, pruebas de anexos.
Cambiar el ítem acordado a «Base de datos» y añadir nota `EVALUADO` con la
decisión de 2026-11-08. Mantener warning. **Aceptación:** el título real se
reconoce y su ausencia se informa. Un anexo como imagen requiere revisión
manual; texto XML no encontrado no demuestra ausencia del contenido escaneado.

- **Estado 2026-11-15:** corregido en `c2eb680`. El ítem 5 de
  `anexos_minimos_cuantitativo` es «Base de datos» y conserva `warning`. La
  nota `EVALUADO` documenta la decisión y el límite: la comparación es por
  subcadena y un anexo escaneado como imagen no se ve en el texto XML, así
  que la ausencia reportada exige revisión manual. Evidencia:
  `937 passed, 4 skipped`; regresión `test_m6_*` (título real reconocido y
  ausencia informada); ruff, ruff format, mypy y linter limpios; ejemplos
  regenerados.
- **Decisión ratificada (2026-11-16):** la comparación por **subcadena** se
  mantiene: un anexo «Base de datos cualitativa» también satisface el ítem
  cuantitativo. No se exige coincidencia de título completo. Sigue en pie el
  otro límite, que no es una decisión: un anexo escaneado como imagen no se
  ve en el texto XML, así que la ausencia reportada exige revisión manual.

### M7. Comprobar lo que anuncia la regla del logo — VA-15

**Archivos:** regla `caratula_logotipo_tamano`, analizador de imagen, tests.
Delimitar carátula y medir dibujo; usar 4,84 × 6,73 cm con tolerancia justificada.
No identificar visualmente el logo si no existe ese mecanismo.
**Aceptación:** imagen solo en el cuerpo no satisface carátula; dimensiones
incorrectas generan warning. Si solo se implementa presencia, renombrar la
descripción y dejar la medición expresamente pendiente, no «cerrada».

- **Estado 2026-11-15:** corregido en `b92f7f3`. `AnalizadorImagen`
  mide el `wp:extent` del `wp:inline`/`wp:anchor` que contiene cada blip
  (ancho = `cx`, alto = `cy`, 360000 EMU por cm). La regla declara
  `contexto: caratula` (primera sección), `ancho_cm: 6.73`, `alto_cm: 4.84`
  y `tolerancia_cm: 0.1`, con nota `EVALUADO`. Una imagen solo en el cuerpo
  no satisface la carátula y un tamaño fuera de tolerancia da `warning`.
  Evidencia: `948 passed, 4 skipped`; regresión `test_m7_*` (3 casos);
  el linter valida la forma de `imagen` (5 pruebas, 8 casos); ruff,
  ruff format, mypy y linter limpios; ejemplos regenerados.
- **Decisión ratificada (2026-11-16):** la tolerancia de medición es de
  **0,1 cm** (1 mm), la que ya se implementaba. El manual fija el tamaño del
  logo pero no da tolerancia.
- **Límite conocido:** no se identifica visualmente el logo. La regla mide
  el primer dibujo de la carátula; si hay varias imágenes, todas deben
  medir lo esperado.

### M8. ORCID por persona y destino — VA-16

**Estado:** corregido en código en el PR #115 (abierto, pendiente de fusión).

**Archivos:** `reglas_unt.yaml`, `AnalizadorHipervinculo`, extractor de relaciones.
**Hecho:** asociación por persona en la carátula (`AUTORES:`/`ASESOR(A):` con
dos puntos, con cortes por anexos/jurado/referencias/presentación y sin contar
las notas de plantilla entre paréntesis), checksum
ISO 7064 MOD 11-2 (admite `X`), destino del vínculo y validación del código
entre paréntesis (la forma que cita el manual). No se verifica identidad por
red. **Aceptación cubierta:** falta un autor, solo hay ORCID del asesor, texto
correcto con destino falso, ORCID válido terminado en X, checksum incorrecto,
código entre paréntesis con destino correcto/ajeno/inválido, estructura sin
`sectPr` reconocida como n/a y carátula delimitada ejercitada en pruebas.

**Medición (2026-11-19):** `scripts/eval_contra_plantillas.py` sobre las 5
plantillas oficiales y `scripts/benchmark_tesis.py` sobre la tesis real:

| Corpus | Antes (`master`) | Con #115 |
|---|---|---|
| 5 plantillas oficiales | 40/50 cada una; `caratula_orcid` **verde** con `0000-0000-0000-0000` | 39/50 cada una; `caratula_orcid` **rojo** por checksum (ORCID de relleno inválido) |
| Tesis real (`tesis_linares_2026.docx`) | rojo, 42 evaluadas, 4 errores, 5 warnings; `caratula_orcid` verde | idéntico; `caratula_orcid` verde |

Las plantillas de relleno traen ORCID `0000-0000-0000-0000` (checksum
inválido), así que el rojo es el veredicto correcto. La tesis real usa ORCID
válidos y no cambia. Queda como límite la identidad del perfil (fuera de
alcance) y la continuidad de la numeración de preliminares.

### M9. Texto literal y recursos restringidos en PDF — VA-12

**Archivos:** `validator/exportador.py`, `tests/test_exportador.py`.
Escapar también sintaxis Markdown de texto no confiable. Impedir que un prompt
cierre su bloque de código. Restringir el fetcher de PDF a recursos permitidos.
**Aceptación:** imágenes Markdown, URLs locales/remotas, backticks y HTML del
documento no activan accesos a recursos. Usar un fetcher simulado; no acceder
a archivos sensibles ni hacer peticiones reales para demostrarlo.

- **Estado 2026-11-18:** corregido en `95f4ad5`. El texto del documento se
  escapa también para Markdown (imágenes, enlaces, énfasis, código y
  encabezados); la cerca del bloque de un prompt es más larga que cualquier
  racha de backticks del contenido; y el fetcher del PDF solo acepta `data:`
  (rechaza `file:`, `http:`, `https:` y `ftp:`). Evidencia: `987 passed,
  9 skipped`; regresiones `test_markdown_neutraliza_imagenes_y_enlaces_del_documento`,
  `test_prompt_con_backticks_no_cierra_el_bloque_de_codigo`,
  `test_fetcher_restringido_rechaza_recursos_externos` y
  `test_pdf_no_abre_recursos_externos` (fetcher espiado, sin red ni
  archivos); ruff, ruff format y mypy limpios.
- **Revisión 2026-11-19 (PR #113, `1c617f1`):** se atendieron las tres
  observaciones de `retblast`. (1) La prueba del fetcher ya no es vacua:
  `test_pdf_no_abre_recursos_externos` espía la capa del fetcher (que
  WeasyPrint invoca con `__call__`) y
  `test_pdf_rechaza_recursos_externos_sin_escapar` salta `_escapar_texto`
  (monkeypatcheando `reporte_a_markdown`) para comprobar que, con HTML
  hostil, se rechazan `file://` y `http://` y el PDF se genera igual;
  verificado que falla si se quita `url_fetcher` de `reporte_a_pdf`.
  (2) `REPORTE` anotado como `dict[str, Any]`; mypy limpio también sobre
  `tests/test_exportador.py`. (3) `_escapar_texto` ya no escapa `~` (se
  renderizaba con barra invertida literal), con la regresión
  `test_markdown_no_escapa_la_virgulilla`. Evidencia: `989 passed,
  9 skipped`; ruff, ruff format y mypy limpios.

### M10. Contadores de CLI y exportación — VA-18

**Archivos:** `validator/cli.py`, `exportador.py`, pruebas de CLI/exportación.
Usar `total_evaluadas` bajo «evaluadas». Mostrar omitidas aparte.
**Aceptación:** 50 totales, 42 evaluadas no se presentan como 50 evaluadas.

- **Estado 2026-11-18:** corregido en `d83ffde`. El modo texto del CLI y el
  resumen Markdown publican «Reglas evaluadas: N de TOTAL» y una línea
  aparte con las no aplicables; el exportador sigue aceptando reportes
  antiguos sin `total_evaluadas`. Evidencia: `1020 passed, 9 skipped` en
  clon limpio (`1027 passed, 2 skipped` con `recursos/`); regresiones
  `test_cli_texto_distingue_evaluadas_de_no_aplicables`,
  `test_markdown_no_presenta_las_omitidas_como_evaluadas` y
  `test_markdown_acepta_reportes_antiguos_sin_total_evaluadas`; ruff, ruff
  format y mypy limpios.

### M11. Reparar el paquete OPC del factory — VA-17

**Archivos de Int3:** `tests/_xml_constants.py`, `tests/_docx_builder.py`,
`tests/docx_factory.py`, pruebas de construcción del motor.
**Consumidor:** B6 de Int1. Int3 no modifica el contrato de API ni sus ejemplos.

- Corregir la relación interna y agregar una imagen válida en el destino
  correcto del ZIP. Verificar también tipos de contenido y relaciones.
- **Aceptación:** el documento base abre con `python-docx`; todos los destinos
  de relaciones internas existen; mutaciones y reglas mantienen su intención.
- Entregar el PR/commit y el comando de regeneración a Int1. B6 continúa
  después de esta entrega. No encargar a retblast el arreglo del builder.
- **Dependencia declarada (2026-11-16):** `docs/ejemplos/doc_bueno.docx` y
  `docs/ejemplos/doc_malo.docx` siguen siendo los paquetes rotos de antes
  (`KeyError: "There is no item named 'media/logo.png' in the archive"`).
  No bloquea M11 —el factory es lo que se arregla aquí— pero su regeneración
  y el refuerzo de la guardia de ejemplos son **B6 de Int1**, con el comando
  `python scripts/ejemplo_bueno_malo.py`. Hasta que B6 los regenere, la
  evaluación contra los ejemplos versionados no es reproducible.

### M12. Cerrar brechas normativas — NM-01 a NM-07

**Dueño exclusivo de implementación:** Int3. Leer primero
[AUDITORIA_NORMATIVA_2026-11-12.md](AUDITORIA_NORMATIVA_2026-11-12.md) y sus CSV.
Esta tarea amplía M1, M3, M5 y M6. No duplica sus arreglos. Dividir en PR por
subtarea. Retblast no implementa estas reglas ni sus fixtures.

| Orden | Archivos / tarea | Aceptación concreta |
|---|---|---|
| M12a — P1 | `reglas_unt.yaml`, `analizadores.py`, `extractor.py` si requiere contexto; ampliar M3 | Decimal explícito correcto no falla por existir. Reinicio romano 99 falla. PAGE a la izquierda no cumple por otro párrafo derecho. `titlePg=0` no significa primera página diferente. Probar continuidad y pie activo; declarar límites de página sin render. |
| M12b — P1 | `reglas_unt.yaml`, selectores de carátula; ampliar M1 | Eliminar escuela falla aunque exista facultad. Asesor 36 pt falla aunque la etiqueta esté correcta. Probar cada bloque y cada propiedad exigida, con estilos y múltiples runs. |
| M12c — P1 | Reglas de detección y estructura; `reglas_unt_pendientes.yaml`; `tests/test_tipo_documento.py` | Encargado ratifica tesis/informe/TINV. No afirmar soporte de ocho tipos. Para cualitativo, eliminar cada apartado obligatorio produce fallo. Tipos ambiguos y no soportados quedan explícitos. No activar pendientes sin documento real. |
| M12d — P2 | Reglas y pruebas de carátula | Ratificar límite inferior del título por tipo; probar 14/15/20/21 palabras según decisión. Probar dos autores en orden e invertidos. Confirmar vigencia de máximo de autores antes de bloquear. Mantener autores en mixtas: confirmado por el usuario con la tesis aprobada por el jefe el 2026-11-12. |
| M12e — P2 | Reglas de referencias y analizador de cantidad | Probar mínimos 20/30/20 TINV; 30 por proyecto/informe cuando se soporten. TSP separa mínimo 20 del informe y máximo 10 de sesión. Una entrada partida no cuenta como varias referencias; texto ajeno no suma. APA y correspondencia semántica no se declaran comprobados por conteo. |
| M12f — P2 | Reglas de anexos; ampliar M6 | Encargado ratifica contradicciones REQ-51 a REQ-55. Eliminar cada anexo requerido falla en el tipo correcto. No acreditar firma ni porcentaje real por título del anexo. |
| M12g — P2 | `fuente`, `cita`, `ubicacion` en YAML y mensajes/prompts | Cada cita literal existe en la fuente. Paráfrasis marcada como tal. Seguimiento y notas se presentan como calidad técnica; encabezados como derivados de plantilla. Corregir conteo documental 46→50 sin alterar catálogo válido. |

En cada PR: agregar regresiones antes del arreglo, sincronizar mutaciones,
verificar documentos reales aplicables y actualizar matriz REQ con prueba y
límite. Si una decisión falta, registrar el requisito como pendiente; no elegir
un estándar por intuición ni convertirlo en «cumple». No tocar API o SPA.

### Nota de estado (2026-11-20): lo que queda tras M12g

Esta nota solo registra el estado; no implementa ni cierra ninguna tarea.

- **Integración pendiente:** los PR #118 (M12b), #119 (documentación de
  cierre), #120 (M12e) y #121 (M12g) están verdes y `MERGEABLE`, sin reviews.
  Retblast los fusiona en `retblast/vistobueno`; no se fusionan desde esta
  rama. Si #120 se integra antes que #121, revisar posibles conflictos en
  `reglas_unt.yaml` y en los documentos compartidos.
- **Motor que requiere ratificación:** M12c/NM-03 (tipos soportados; no activar
  las cinco estructuras de `reglas_unt_pendientes.yaml` sin plantillas reales),
  M12d/NM-04 (mínimo de palabras del título por tipo y vigencia del máximo de
  autores) y M12f/NM-06 (contradicciones de anexos REQ-51 a REQ-55). Son los
  únicos NM del bloque M12 sin implementar; no se cierran por intuición.
- **Cierre documental:** actualizar estados globales, bloques de aviso,
  cronología y bitácora de la Semana 12 después de las fusiones. `AGENTS.md`
  solo se edita con autorización explícita del usuario. La regeneración de
  ejemplos de B6 corresponde a Int1.
- **Verificación con fuentes reales:** M12g etiqueta la procedencia de las
  referencias, pero no certifica que el resto de las citas literales existan
  en el manual; para comprobarlo hacen falta el DOCX del manual y copias
  autorizadas, sin datos personales.
- **Fuera del bloque M12:** siguen abiertos VA-10, VA-11 (B5), VA-17 (B6),
  VA-19, la verificación en navegador de VA-20 y VA-21, y el seguimiento de
  NM-08 en el piloto.
