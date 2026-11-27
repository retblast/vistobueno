# DSL declarativo de validación — VistoBueno

Documento de referencia del **lenguaje específico de dominio (DSL)** para
definir reglas de validación de formato de tesis. El DSL reemplaza — de
forma **opcional y gradual** — el formato legacy
(`mecanismo_verificable.checks`) por un modelo basado en **analizadores
léxicos (tokenizer), autómatas finitos (DFA), autómatas de pila (PDA),
gramáticas BNF y analizadores de conteo/presencia** (F1→F3).

La gran ventaja: **no rompe el contrato de la API ni el del motor**. El
motor interno (`engine.validate_docx`) siguió devolviendo `List[RuleResult]`.

---

## Formato del archivo

```yaml
namespaces: { w: "...", r: "...", ... }
reglas:
  - id: <string>
    tipo: <atributo_xml | presencia_xml | patron_texto | lista_texto |
           imagen | secuencia | estructura | formato_texto>
    descripcion: <string>
    valor_esperado: <string | list>
    severidad: error | warning
    fuente: <string>
    ubicacion: <string>
    cita: <string>
    origen_cita: literal | parafasis | localizador | plantilla | calidad_tecnica | matriz_interna | norma_institucional  # opcional; default: literal
    # luego, UNA o VARIAS secciones de analizador (todas deben cumplirse):
    atributo_xml: { ... }
    patron_texto: { ... }
    lista_texto: { ... }
    imagen: { ... }
    automata_secuencia: { ... }
    gramatica_estructura: { ... }
    automata_pila: { ... }
    patron_cantidad: { ... }
    conteo_nodos: { ... }
    lista_obligatoria: { ... }
    hipervinculo_texto: { ... }
    paginacion: { ... }        # F2 ítem 1 — párrafo ↔ página física
    nota_pie: { ... }          # F2 ítem 3 — numeración de notas al pie
    toc_apunta: { ... }        # F2 ítem 11 — el índice apunta a secciones reales
    toc_numeracion: { ... }    # F2 ítem 12 — jerarquía de numeración del índice
    deteccion_tipo: { ... }     # Fase B — publica el tipo documental
```

El `engine` detecta el formato por la clave `reglas` (DSL) vs `rules`
(legacy). Ambos formatos pueden coexistir en el repositorio.

`origen_cita` (NM-07) declara qué es `cita`. `literal` conserva la etiqueta
histórica «Cita del reglamento»; los demás valores producen etiquetas propias
en los prompts («Paráfrasis del reglamento», «Localizador en el reglamento»,
«plantilla institucional», «calidad técnica», «matriz de auditoría interna» o
«Norma institucional»). Es un campo **interno**: no se serializa en
`RuleResult.to_dict()` ni se expone en la API. El linter rechaza valores
desconocidos y una cita literal recortada con elipsis o «etc.».

---

## Secciones de analizador

> Los analizadores de F3 (`patron_cantidad`, `conteo_nodos`,
> `lista_obligatoria`) y el `automata_pila` de F2 pueden acotar su
> búsqueda a una **sección del documento** usando `seccion:` (span cortado
> entre títulos por el tokenizer — ver § 0). Sin `seccion:`, operan sobre
> todo el documento.

### 0. El tokenizer y la función `seccion()` (F2/F3)

El módulo `validator/tokenizer.py` convierte el `<w:body>` en un flujo de
tokens tipados (`TITULO`, `PARRAFO`, `TABLA`, `IMAGEN`, `SALTO_SECCION`).
Es la base de los autómatas de F2 y de las secciones de F3:

```python
from validator.extractor import extract
from validator.tokenizer import tokenizar, seccion, TITULO, PARRAFO

flujo = tokenizar(extract("tesis.docx"))
resumen = seccion(flujo, "resumen")   # tokens tras el 1er TITULO "resumen*"
referencias = seccion(flujo, "referencias", fin="anexos")  # corte opcional
```

- `seccion(flujo, inicio, fin=None)`: devuelve los tokens posteriores al
  primer TITULO que matchea la regex `inicio` (ignore case) y hasta el
  siguiente TITULO (excluido). Si `fin` es una regex, solo un TITULO que la
  matchee corta; si no hay más títulos, toma el final del flujo. Sin match
  de `inicio`, devuelve la lista vacía (la regla cae como fallo).

Todas las secciones de analizador aceptan:

```yaml
seccion:
  inicio: resumen      # regex sobre el texto del TITULO que abre la sección
  fin: anexos          # opcional: regex del TITULO que la cierra
  hasta_final: false   # opcional: si no hay `fin`, ir hasta el final del doc
```

- `hasta_final` (booleano, por defecto `false`): cuando la sección no tiene
  un título de cierre (o `fin` no matchea), `true` hace que abarque hasta el
  final del documento en vez de cortar en el primer `TITULO` posterior. Se
  usa en los anexos, donde cada "Anexo N." es un `TITULO` y no hay un
  encabezado que cierre la sección (AUD-02).

### 1. `atributo_xml` / `presencia_xml` → `AnalizadorXML`

Verifica atributos de nodos o su presencia vía XPath.

```yaml
atributo_xml:
  parte: document | footer | header     # defecto: document
  contexto: todos | cuerpo | cuerpo_prosa | seccion_cuerpo | caratula  # defecto: todos
  xpath: //w:sectPr[1]/w:pgSz
  atributo: "@w:w"                      # solo para comparaciones de valor
  comparacion: eq | all_eq | contains | exists | not_exists
  esperado: "11906"
  tolerancia: 12                        # opcional: twips de desvío aceptado
  ignore_case: false                    # opcional (contains)
```

- `exists` / `not_exists` operan solo sobre la cantidad de nodos. Cuando
  `not_exists` incumple, el detalle nombra los nodos culpable por su
  posición (`not_exists 1 nodos; incumplen: #1`) y la ubicación de la regla
  apunta al primero.
- `eq` compara el primer valor del atributo; `all_eq` todos; `contains`
  subcadena (con `ignore_case`).
- `tolerancia` (entero, opcional) permite `eq`/`all_eq` numéricos con un
  desvío máximo: el valor cumple si `|valor - esperado| <= tolerancia`.
  Se usa p. ej. en `sangria_parrafo` (esperado 720 twips, tolerancia 12) para
  aceptar los 708/709 twips (~1.25 cm) de las plantillas oficiales. Si el
  valor o el esperado no son numéricos, se compara por igualdad exacta.
- `contexto: cuerpo` restringe la consulta al cuerpo real (entre el heading
  "Introducción" y el de "Referencias"/"Bibliografía"/"Anexos") y excluye
  títulos, párrafos vacíos y líneas de caption `Nota.`/`Fuente.`.
- `contexto: cuerpo_prosa` es un subconjunto de `cuerpo` que además excluye
  ítems de lista (`w:numPr` directo o estilo cuyo `w:name` sea
  `List Paragraph`), títulos de tabla y figura (estilo cuyo `w:name` contenga
  `caption`) y líneas de leyenda (`---: ...`). El filtro es por nombre de
  estilo, no por identificador, para que funcione igual en Word en español e
  inglés. Se usa en `alineacion_cuerpo`: el manual justifica la prosa, no las
  listas ni los títulos de tabla.
- En `w:pgSz` (tamaño de papel), `@w:w` compara el **lado corto** y `@w:h`
  el **lado largo**, sin importar la orientación: un A4 horizontal
  (`16838 x 11906`) cumple igual que uno vertical, con o sin
  `w:orient="landscape"`. `papel_tamano` valida **todas** las secciones
  (carátula y anexos incluidos) con `all_eq`; la sección culpable se
  identifica por su posición `#N` en el detalle. Límite: se compara el
  valor OOXML exacto, así que una conversión que redondee el papel
  (p. ej. `11910 x 16840`) sigue fallando hasta que se decida una
  tolerancia.
- `w:pgSz` es **opcional** en OOXML: una sección que no lo declara no
  puede compararse. Por eso `papel_tamano` añade una comprobación
  `presencia_xml` con `xpath: '//w:sectPr[not(w:pgSz)]'` y
  `comparacion: not_exists`, y así ninguna sección queda sin revisar. El
  detalle de `not_exists` incumplido nombra los nodos por posición
  (`not_exists 1 nodos; incumplen: #1`) y la ubicación de la regla apunta
  al primero.
- `contexto: caratula` restringe la consulta a los párrafos de la carátula:
  los `w:p` de nivel superior anteriores al primer `w:pPr/w:sectPr` del cuerpo
  (el salto que cierra la portada). Si el documento no declara ese salto, se
  toman todos los párrafos del cuerpo. Sirve para reglas que en el manual
  aplican solo a la portada y que, evaluadas sobre todo el documento,
  producirían falsos positivos.
- `n_a_si_ausente` (opcional): si la parte XML no existe, la regla se
  considera n/a en vez de fallar.
- `n_a_si_sin_nodos` (opcional): en comparaciones de atributo, si el XPath no
  encuentra ningún nodo, la regla se considera n/a (`no aplica (sin nodos)`).
  Se usa para reglas acotadas a un tipo de título cuya línea puede no existir
  en otros documentos (p. ej. `caratula_optar_grado_tamano`, AUD-07).

### 2. `patron_texto` → `AnalizadorRegex`

Aplica una expresión regular al contenido textual de los nodos.

```yaml
patron_texto:
  parte: document
  xpath: //w:body//w:p
  patron: "^\\d+$"
  coincidencia: todos | alguno | ninguno   # defecto: todos
  comparacion: regex | fullmatch           # defecto: regex (search)
  ignore_case: false
  unidad: run | nodo                       # defecto: run
```

- `todos`: todos los nodos `w:t` deben matchear.
- `alguno` / `ninguno`: al menos uno / ninguno.
- `unidad: run` mide cada `w:t` por separado (semántica legacy).
  `unidad: nodo` reúne con `text_of()` todo el texto del nodo seleccionado;
  se usa cuando la propiedad es del bloque completo (por ejemplo, que el
  nombre del autor tenga mayúsculas y minúsculas aunque Word lo parta en
  varios runs). Un valor distinto —o una clave mal escrita— se rechaza al
  cargar el DSL, para no caer en `run` en silencio.

### 3. `lista_texto` → `AnalizadorLista`

Comprueba que el texto de los nodos pertenezca a una lista permitida.

```yaml
lista_texto:
  parte: document
  xpath: //w:body/w:p[contains(., 'línea')]
  lista: ["Línea: educación", "Línea: desarrollo"]
  ignore_case: true
```

### 4. `imagen` → `AnalizadorImagen`

Cuenta imágenes (blips) en los nodos que matchean el XPath y verifica
cantidades mínima y/o máxima. Opcionalmente mide el dibujo que contiene
cada blip (M7/VA-15):

```yaml
imagen:
  parte: document
  contexto: caratula    # opcional: todos | cuerpo | caratula | ...
  xpath: //w:drawing//a:blip
  formato: png
  cantidad_minima: 1
  cantidad_maxima: 4     # opcional
  ancho_cm: 6.73         # opcional, junto con alto_cm
  alto_cm: 4.84
  tolerancia_cm: 0.1     # opcional; por defecto 0.1
```

- Sin `ancho_cm`/`alto_cm` solo se comprueba la presencia y la cantidad.
- Con ambos, se lee el `wp:extent` del `wp:inline`/`wp:anchor` que contiene
  el blip: **ancho = `cx`**, **alto = `cy`** (360000 EMU por cm). Una
  imagen sin `wp:extent` no se puede medir y la regla falla
  (`tamanos=sin_dimensiones`); no se da por buena en silencio.
- `contexto: caratula` limita la búsqueda a la primera sección, así que una
  imagen solo en el cuerpo o en el encabezado no satisface la carátula.
- La tolerancia absorbe el redondeo cm↔EMU y el ajuste manual. El manual
  no fija una; la regla del logo usa 0,1 cm (1 mm) y queda anotada como
  decisión a ratificar.

### 5. `automata_secuencia` → DFA (secuencia ordenada de títulos)

Modela la estructura de secciones como un **autómata finito determinista**.
Los estados son los títulos esperados; cada transición consume el próximo
título que matchea el patrón del estado. Los estados `opcional: true` se
omiten (pero no se exigen).

```yaml
automata_secuencia:
  nivel_titulo: [1, 2, 3]                 # estilos Heading/Título reconocidos
  normalizacion: [mayusculas, ignorar_indent]
  reconocimiento: greedy | backtracking   # defecto: greedy
  estados:
    - nombre: caratula
      patron: "universidad"               # regex sobre el heading normalizado
      opcional: true
    - nombre: introduccion
      patron: "introducción"
    - nombre: resultados
      patron: "resultados"
```

Reglas de reconocimiento:
- El puntero de entrada **nunca retrocede** (`greedy`) — se preserva el
  comportamiento histórico del motor legacy.
- `backtracking` explora interpretaciones alternativas (búsqueda NFA).
- La carátula se satisface si el **primer párrafo** del documento contiene
  "universidad" (no usa estilo de encabezado).

### 6. `gramatica_estructura` → BNF (estructura jerárquica)

Expresa la estructura completa como una **gramática libre de contexto**
(BNF ligera) y la evalúa con un **parseador descendente recursivo**.

```yaml
gramatica_estructura:
  reglas_sintacticas:
    - "TESIS → CARATULA INDICE INTRODUCCION CUERPO CONCLUSIONES REFERENCIAS"
    - "CUERPO → METODOLOGIA RESULTADOS"
  terminales: [CARATULA, INDICE, INTRODUCCION, METODOLOGIA, RESULTADOS, CONCLUSIONES, REFERENCIAS]
  no_terminales: [TESIS, CUERPO]
  inicio: TESIS
```

El parser expande `inicio` hasta obtener secuencias de terminales y
comprueba que los headings del documento las cubran en orden.

### 7. `automata_pila` → PDA push/pop (estructura anidada)

Expresa una sección como un **autómata de pila** (F2): los estados se
abren con `push` y se cierran con `pop`, lo que permite validar
anidamiento de sub-secciones (no expresable con un DFA plano).

```yaml
automata_pila:
  nivel_titulo: [1, 2, 3]
  estados:
    - nombre: introduccion
      patron: "introducción"
      push: desarrollo            # entrar al sub-nivel "desarrollo"
      pila: [...]
      vaciar_pila: false
    - nombre: desarrollo
      patron: "metodología"
      push: resultados
    - nombre: resultados
      patron: "resultados"
      pop: true                   # cierra el nivel "desarrollo"
    - nombre: conclusiones
      patron: "conclusiones"
      pop: true
```

Reglas de reconocimiento (compartidas con el DFA):
- El puntero de entrada no retrocede (salvo `backtracking`).
- `opcional: true` en un estado lo hace no exigible.
- El tokenizer alimenta el PDA con la proyección de texto del flujo de
  títulos (`TITULO`), igual que el DFA y la gramática.

### 8. `patron_cantidad` → `AnalizadorCantidadPatron` (F3)

Cuenta palabras, matches de regex o entradas estructuradas y verifica un
rango (`cantidad_minima`/`cantidad_maxima`):

```yaml
patron_cantidad:
  seccion: { inicio: resumen }        # una sola sección
  # — o, para contar cada idioma por separado —
  secciones:
    - { nombre: resumen, inicio: resumen }
    - { nombre: abstract, inicio: abstract }
  operacion: count_words | count_matches | count_entries
  patron: "..."                       # solo count_matches
  filtro: "^palabras clave"           # opcional: párrafos que cuentan
  excluir: "^(palabras clave|keywords)\b"  # opcional: párrafos que NO cuentan
  ignore_case: true
  cantidad_minima: 159
  cantidad_maxima: 220
```

- `count_words`: palabras (`\w+`) del texto contado (regla *resumen
  159–220 palabras*). `excluir` permite separar la prosa de la línea de
  palabras clave.
- `count_matches`: matches de `patron` en el texto.
- `count_entries`: entradas separadas por `,` o `;` del texto posterior al
  primer `:` de **cada párrafo** (p. ej. `Palabras clave: a, b, c` → 3).
  Útil con `filtro` sobre el párrafo de etiqueta.
- `secciones`: lista de secciones; cada una se cuenta y evalúa por separado
  y el detalle las nombra (`resumen=3 abstract=2`). No se puede combinar con
  `seccion`.
- `excluir` y `filtro` se aplican por párrafo antes de contar; primero se
  descartan los párrafos que matchean `excluir` y luego se conservan los que
  matchean `filtro`.

### 9. `conteo_nodos` → `AnalizadorConteoNodos` (F3)

Cuenta nodos XPath, párrafos no vacíos o entradas de una sección y verifica
cantidad mínima/máxima:

```yaml
conteo_nodos:
  seccion: { inicio: referencias }    # modo "sección"
  unidad: entrada                     # parrafo (default) | entrada (NM-05)
  label: referencias                  # etiqueta del detalle (default: nodos)
  # — o en su lugar —
  parte: document
  xpath: //w:body//w:p                # modo "nodos"
  cantidad_minima: 20
  cantidad_maxima: 30                 # opcional: rango
  cantidades_multiples: [20, 30, 20]  # opcional: cualquier valor cumple
```

- Sin `xpath` pero con `seccion:`, cuenta los párrafos no vacíos
  (`PARRAFO`) del slice. Con `unidad: entrada` cuenta solo las entradas
  con patrón autor-año: una continuación sin año no suma y el texto ajeno
  se ignora. Es el modo que usan las reglas de referencias (NM-05). No
  comprueba APA, sangría francesa ni la relación cita-referencia (REQ-50).
- `cantidades_multiples` permite aceptar cualquiera de varios mínimos
  (cuando el mínimo depende del tipo de investigación). Si se declara,
  **no** se usa `cantidad_minima`.
- Un `unidad` desconocido o una clave mal escrita los rechaza el linter al
  cargar el DSL, en vez de dejar la regla contando párrafos en silencio.

### 10. `lista_obligatoria` → `AnalizadorListaObligatoria` (F3)

Verifica que cada ítem de una lista de **contenidos obligatorios** (por
subcadena normalizada) aparezca en la sección:

```yaml
lista_obligatoria:
  seccion: { inicio: anexo, hasta_final: true }
  ignore_case: true
  items:
    - Matriz de consistencia
    - Consentimiento informado
```

- Cada ítem se busca como subcadena (normalizada a minúsculas) en el texto
  de la sección. Usado por las reglas de *anexos mínimos*. Por ser
  subcadena, un ítem corto como «Base de datos» también satisface títulos
  más largos («Base de datos cuantitativa»).
- Solo se lee el texto del DOCX: un anexo escaneado como imagen no se
  detecta y su ausencia reportada exige revisión manual.
- `hasta_final: true` es necesario en anexos: sin él, `seccion()` cortaría
  en el primer `TITULO` posterior (el siguiente "Anexo N.") y solo se
  revisaría el primero. Con él, el slice llega al final del documento.
- El `found` de un fallo reporta `encontrados=N/M` además de la lista de
  faltantes, para distinguir "no hay ninguno" de "faltan algunos".

### 11. `hipervinculo_texto` → `AnalizadorHipervinculo` (F3)

Cuenta hipervínculos (`w:hyperlink`) cuyo texto matchea un patrón y
verifica un mínimo:

```yaml
hipervinculo_texto:
  parte: document
  contexto: caratula
  xpath: //w:body//w:hyperlink
  patron: 'https?://orcid\.org/\d{4}-?\d{4}-?\d{4}-?\d{3}[\dXx]'
  cantidad_minima: 1
```

Con la sub-configuración `validar_orcid` (M8/VA-16) se valida además el
contenido del identificador y su relación con la carátula:

```yaml
hipervinculo_texto:
  # ...
  validar_orcid:
    checksum: true     # ISO 7064 MOD 11-2; el último carácter puede ser X
    destino: true      # el Target de la relación debe ser el mismo perfil
    por_persona: true  # cada autor y el asesor deben tener su ORCID debajo
```

- Con `validar_orcid`, los candidatos son **todos** los `w:hyperlink` cuyo
  texto contenga un ORCID (`orcid.extraer`), no solo los que encajan con
  `patron`: el manual pide el código entre paréntesis y limitarse al patrón
  de URL dejaba el checksum y el destino sin comprobar.
- `checksum` usa el algoritmo ISO 7064 MOD 11-2 que define ORCID. Un
  identificador con forma correcta pero dígito de control inválido falla
  con `invalidos=[... checksum]`.
- `destino` lee `word/_rels/document.xml.rels` y exige que el `Target`
  del `w:hyperlink` apunte a `orcid.org` con **el mismo** identificador
  visible. Un texto correcto con destino falso falla con
  `invalidos=[... destino]`. Si la parte de relaciones falta o está mal
  formada, el destino se considera ausente.
- `por_persona` reconoce los bloques «AUTORES:»/«AUTORA:» y
  «ASESOR(A):» de la carátula (la etiqueta exige los dos puntos): cada
  párrafo de nombre es una persona y su ORCID debe estar en el mismo
  párrafo o en el siguiente. Las etiquetas «anexos», «jurado»,
  «referencias» y «presentación» cierran el bloque aunque no haya salto de
  sección, para no contar las referencias como personas. Una línea de
  ORCID en texto plano (sin hipervínculo) no satisface la regla. Si la
  estructura de la carátula no se reconoce, el detalle informa
  `personas=0 (n/a)` y se mantiene la comprobación global de
  `cantidad_minima`.
- `checksum` y `destino` valen `true` si se omiten (fallo cerrado);
  `por_persona` exige `parte: document` y `contexto: caratula` (el linter
  rechaza otra combinación).
- La identidad del perfil no se verifica por red: el motor solo compara
  texto y destino dentro del DOCX.

Usado por la regla *caratula_orcid* (el código ORCID debe ser un
hipervínculo de 16 dígitos, normalizado a minúsculas y entre paréntesis).

### 12. `paginacion` → `AnalizadorPaginacion` (F2 ítem 1, M3/VA-04)

Correlaciona los párrafos con su **página física** y compara las páginas de
los nodos que matchean cada XPath. El mapa se construye procesando los
saltos en orden de documento:

- `w:br w:type="page"`: salto explícito (estructural).
- `w:pPr/w:pageBreakBefore`: el **propio párrafo** arranca en página nueva;
  `w:val="0"`, `false` u `off` lo desactivan.
- `w:pPr/w:sectPr` con tipo distinto de `continuous`/`nextColumn`: la
  sección siguiente empieza en otra página.
- `w:lastRenderedPageBreak`: caché del render de Word.

Varios saltos dentro del mismo párrafo cuentan todos. Un párrafo que cruza
página conserva la página donde empieza. Cada página lleva un grado de
certeza: **comprobada** (salto estructural), **estimada** (caché de render)
o **desconocida** (sin marcadores).

```yaml
paginacion:
  comparacion: paginas_distintas
  xpaths:
    # «Índice de contenidos»; si no existe, el título genérico «Índice».
    - >-
      (//w:p[normalize-space(translate(translate(normalize-space(.),
      'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúñü'),
      'áéíóúüñ', 'aeiouun')) = 'indice de contenidos']
      | //w:p[normalize-space(translate(translate(normalize-space(.),
      'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúñü'),
      'áéíóúüñ', 'aeiouun')) = 'indice']
      [not(//w:p[normalize-space(translate(translate(normalize-space(.),
      'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúñü'),
      'áéíóúüñ', 'aeiouun')) = 'indice de contenidos'])])[1]
    - "//w:p[normalize-space(translate(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúñü'), 'áéíóúüñ', 'aeiouun')) = 'indice de tablas']"
    - "//w:p[normalize-space(translate(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúñü'), 'áéíóúüñ', 'aeiouun')) = 'indice de figuras']"
```

- `paginas_distintas`: los títulos deben quedar en páginas separadas
  (`paginas_repetidas` si hay dos en la misma; `indices_no_verificables`
  si algún XPath no coincide).
- El XPath de la regla *indice_paginas_separadas* **pliega tildes** (para
  que "ÍNDICE" se encuentre) y compara el **texto completo** del párrafo
  (para que la línea `PAGEREF` de la tabla de contenido no se confunda con
  el título de la sección). Con un XPath tolerante (`contains`) la regla
  daba un falso positivo `paginas_repetidas` sobre la tesis aprobada. El
  primer XPath acepta «Índice de contenidos» y, si no existe, el título
  genérico «Índice» (la tesis aprobada titula así esa sección); cuando
  existe el título específico, el genérico se descarta para que un título
  paraguas no le gane a la subdivisión. Se toma la primera coincidencia de
  cada XPath en orden de documento.
- Si algún XPath no coincide, la regla es **NO APLICABLE**
  (`aplicable=False`, `found="no aplica a este documento"`), no "cumple":
  la presencia de las secciones la cubren otras reglas.
- Si la página de algún objetivo es **desconocida** (el DOCX no trae
  marcadores ni caché de render), la regla pasa como n/a con
  `paginas_no_verificables`: no se inventa una página para fallar por
  `paginas_repetidas`. Si la página solo está **estimada** (caché de render
  de Word), el detalle declara `(estimadas)`. Este caso también es **NO
  APLICABLE**.
- A efectos del *enriquecimiento de `ubicacion`*, el analizador expone el
  último nodo analizado (`ultimo_nodo`); cuando una regla FALLA con página
  conocida, el compilador anexa `; página N` (o `; página N (estimada)` si
  la página viene de la caché de render). Si la página es desconocida, el
  sufijo se omite.
- Los párrafos de `header*`/`footer*` **no** están en el mapa de página
  → nunca reciben el sufijo.

Usado por la regla *indice_paginas_separadas* (warning, Manual párr. 193).

### 13. `nota_pie` → `AnalizadorNotaPie` (F2 ítem 3)

Valida la consistencia de la numeración de **notas al pie** (`1..N`
consecutivos, sin duplicados y definidos en `word/footnotes.xml`):

```yaml
nota_pie:
  operacion: numeracion_consistente
```

- Lee `//w:footnoteReference/@w:id` del cuerpo. Sin referencias → la regla
  **pasa (n/a)**: la ausencia de notas no es un desvío.
- Si la parte `footnotes.xml` existe, cada id referenciado debe estar
  definido ahí (ids `-1` y `0` son los separadores reservados de Word).

Usado por la regla *notas_al_pie_consistencia* (warning, estándar Word;
el manual no la regula).

### 14. `toc_apunta` → `AnalizadorTocApunta` (F2 ítem 11)

Verifica que cada entrada del **índice de contenidos** apunte a una sección
real del documento:

```yaml
toc_apunta:
  operacion: entradas_corresponden
```

- La región del índice es la que sigue a un título de encabezado que matchea
  `regex_indice` (defecto `^indice(\s+de\s+contenidos)?$`, comparado **sin
  acentos** e IGNORECASE), hasta el siguiente encabezado de cualquier nivel.
- Cada entrada se normaliza (se quita el prefijo de numeración `I.`/`1.1.`,
  el número de página final, paréntesis, puntuación y tildes) y se compara su
  "palabra significativa" (primer token ≥ 4 caracteres) contra los títulos del
  cuerpo normalizados. Así "1.1. EL PROBLEMA ..... 3" apunta a "EL PROBLEMA".
- Caso anexos: la entrada "Anexo 1. …" matchea el título "ANEXOS" vía
  subcadena (`ANEXO` ⊂ `ANEXOS`).
- Sin región de índice → la regla **pasa (n/a)**: la ausencia de índice no es
  un desvío (es cubierto por otras reglas de estructura).

Usado por la regla *indice_apunta_secciones* (warning, Manual párr. 194).

### 15. `toc_numeracion` → `AnalizadorTocNumeracion` (F2 ítem 12)

Valida la **jerarquía de numeración** de las entradas del índice:

```yaml
toc_numeracion:
  operacion: jerarquia_consistente
```

- Capítulos en romano (`I.`, `II.`, …) deben ser **consecutivos** (sin saltos).
- Subsecciones decimales (`K.1`, `K.1.1`, …) deben pertenecer a su capítulo
  (el primer componente = número del capítulo actual), la primera subsección
  de cada capítulo debe ser `K.1`, y el conjunto debe estar en **orden
  preorder estricto** (comparación de tuplas: `1.1 < 1.1.1 < 1.2 < 1.3`).
- NO exige contigüidad de subsecciones hermanas (1.1 → 1.3 es aceptable) para
  evitar falsos positivos cuando una sección "no aplica" y se omite
  (decisión `EVALUADO`).
- Entradas sin número (p. ej. "REFERENCIAS", "ANEXOS") se ignoran.
- Sin región de índice → la regla **pasa (n/a)**.

Usado por la regla *indice_numeracion_jerarquica* (warning, Manual párr. 194).

---

### 16. `deteccion_tipo` → `DeteccionTipo` (Fase B)

No es un verificador de formato: es la única regla que **publica un dato en
el contexto** del documento, del que dependen las demás. Determina a qué tipo
de documento pertenece la tesis para que cada estructura se valide solo si
corresponde.

```yaml
- id: deteccion_tipo_documento
  tipo: deteccion
  severidad: warning          # siempre informa, nunca bloquea (decisión 4)
  deteccion_tipo:
    expone: tipo_documento    # la clave que publica en el contexto
    declaracion:              # nivel 1: lo que el autor escribió
      anexo: 'Anexo 10 — Declaración jurada (párr. 5008-5022)'
      etiquetas:              # etiqueta -> tipo, o lista de etiquetas
        tinv_cuantitativo:
          - 'TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUANTITATIVA'
          - 'TRABAJO DE INVESTIGACIÓN CUANTITATIVO'
    firmas:                   # nivel 2: lo que el documento trae en su estructura
    - tipo: tsp
      evidencia: ['SECUENCIA DIDÁCTICA', 'SUSTENTO PSICOPEDAGÓGICO']
      minimo: 2               # cuántos de esosasaros hay que alcanzar
    minimo_global: 1          # sin esto, ninguna firma se alcanza
```

Detecta en **dos niveles**, y el primero que llegue a su umbral gana:

1. **`declaracion`** — busca cada etiqueta del Anexo 10 junto a una casilla
   marcada. La casilla se lee como símbolo, texto plano o content-control de
   Word (`w14:checkbox`), y puede vivir en cualquier párrafo del cuerpo,
   incluida una tabla (`w:tbl`) o un bloque `w:sdt`. Si el Anexo 10 es una
   tabla, la etiqueta se busca en la **misma fila** que la casilla (suelen ir
   en celdas distintas). La comparación es por subcadena, así que las
   etiquetas cortas ceden ante las más específicas. Se recogen **todas** las
   casillas marcadas, no solo la primera: si dos declaran tipos distintos, el
   resultado es `contradictorio`; marcar dos veces el mismo tipo (o dos de sus
   etiquetas) no cambia la decisión.
2. **`firmas`** — conjuntos de secciones que solo tiene un tipo. `minimo: 2`
   significa "al menos 2 de las 3 evidencias". Las firmas se cotejan **solo
   contra párrafos con estilo de título** (los mismos que consume el DFA de
   estructura): la prosa es ruido y no cuenta como evidencia estructural, para
   que un párrafo cualquiera (p. ej. la línea "Línea de investigación:" de la
   carátula) no alcance el mínimo de otro tipo y robe la clasificación.

El resultado es uno de cinco valores, y `expone` publica ese valor como
`tipo_documento`:

| `nivel` | Significado | ¿Se publica? |
|---------|-------------|--------------|
| `declarado` | El autor lo escribió en el Anexo 10 | Sí, el tipo declarado |
| `inferido` | Alcanzó una firma estructural | Sí, el tipo de la firma |
| `sin_determinar` | Ninguna fuente llega al umbral | No: publica `sin_determinar` |
| `contradictorio` | Dos fuentes dan tipos distintos | No: publica `contradictorio` |

Cuando el valor es `sin_determinar` o `contradictorio` ninguna estructura
aplica y el motor emite **un error centinela accionable** (decisión 6), en vez
de validar contra todos los esquemas a la vez. Además, si el tipo publicado es
uno de los 5 **sin estructura cargada** (proyecto, informe y TSP), el motor
emite un **warning** `tipo_documento_sin_estructura`: el documento se valida
con las reglas generales, pero su esquema formal aún no — así el semáforo no
vende un "verde" que no validó el capítulo de metodología.

#### `expone`

Declara la clave que la regla publica en el contexto. Debe ser un texto no
vacío y **solo puede aparecer en una regla** del archivo (si dos reglas
publican la misma clave, el contexto sería ambiguo y el linter lo rechaza).
Una regla con `expone` no puede llevar `aplicar_si`: no puede condicionarse a
un valor que ella misma produce.

#### `aplicar_si`

Condiciona una regla a un valor del contexto. Las condiciones se resuelven en
**dos fases**: primero se ejecuta todo lo que expone claves, después lo que se
condiciona. Por eso una regla condicionada puede declararse *antes* que la
que produce su clave, y el orden del YAML es irrelevante.

```yaml
- id: estructura_tinv_cuantitativo
  aplicar_si:
    tipo_documento: tinv_cuantitativo    # solo su tipo exacto
```

- El valor puede ser un escalar o una **lista de aceptados**. Una lista vacía
  no casaría con nada y dejaría la regla muerta, así que el linter la rechaza.
- La clave tiene que exponerla **alguna regla del mismo archivo**. El linter
  no consulta los otros YAML del repositorio: es lo que obliga a que un
  archivo como `reglas_unt_pendientes.yaml` traiga su propia copia de
  `deteccion_tipo_documento`.
- Una regla que **no** aplica no ha fallado: se emite con `passed=True` y
  `aplicable=False`. Así no puede bloquear la entrega, y el resumen cuenta
  aparte lo evaluado de lo omitido.

Usado por `estructura_tinv_cuantitativo`, `estructura_tinv_cualitativo`,
`estructura_tinv_revision_literatura` y por las 5 estructuras de
`reglas_unt_pendientes.yaml`.

### 17. `formato_efectivo` → `AnalizadorFormato` (M1)

Resuelve el formato **efectivo** de los runs o párrafos sujetos a la regla,
en vez de leer solo el primer run y solo el formato directo. Es la sección
que usan las reglas de fuente, tamaño, interlineado, alineación y negrita
del cuerpo y de la carátula.

```yaml
formato_efectivo:
  parte: document
  contexto: cuerpo | cuerpo_prosa | caratula | todos | seccion_cuerpo   # defecto: todos
  sujeto: run | parrafo                                  # defecto: run
  parrafo_xpath: //w:body//w:p
  propiedad: w:rFonts/@w:ascii    # o un toggle: w:b
  comparacion: eq | all_eq | contains                    # defecto: all_eq
  esperado: Times New Roman
  tolerancia: 12                  # opcional, igual que atributo_xml
  n_a_si_sin_nodos: true          # opcional
  n_a_si_ausente: true            # opcional
```

- `parrafo_xpath` selecciona **primero** los párrafos candidatos (respetando
  `parte` y `contexto`); después se resuelve el valor efectivo de cada sujeto.
  No se ignora una propiedad ausente ni se supone que cumple.
- `sujeto: run` evalúa **todos los runs con texto** de cada párrafo,
  incluidos los que viven dentro de un `w:hyperlink`. Un run sin texto no
  aporta valor y no exime al párrafo. `sujeto: parrafo` evalúa las
  propiedades de `w:pPr` (p. ej. `w:jc` o `w:spacing`).
- `propiedad` es `w:elemento/@w:atributo` para una propiedad con valor, o
  `w:elemento` para un toggle OOXML (`w:b`, `w:i`, `w:u`). Un toggle
  ausente en todas las capas devuelve `"0"` (Word lo considera apagado);
  el resto de propiedades ausentes devuelve `(ausente)`.
- `comparacion: all_eq` es la recomendada: `eq` solo miraría el primer
  sujeto y repetiría el defecto de VA-01.
- `n_a_si_sin_nodos`: si el `parrafo_xpath` no selecciona párrafos, la
  regla se marca n/a. `n_a_si_ausente`: si la parte XML no existe, la regla
  se marca n/a en vez de fallar.

**Precedencia de resolución** (de mayor a menor), igual que Word:

1. formato directo: `w:rPr` del run o `w:pPr` del párrafo;
2. estilo de carácter (`w:rStyle`) y su cadena `basedOn`;
3. estilo de párrafo (`w:pStyle`, o el estilo de párrafo por defecto
   `w:default="1"`) y su cadena `basedOn` (sus `w:rPr`/`w:pPr`);
4. `w:docDefaults` (`w:rPrDefault`/`w:pPrDefault`).

Un ciclo en la cadena `basedOn` no tumba la validación: el analizador lo
reporta como incumplimiento (`ciclo de estilos: A -> B -> A`), porque un
documento con estilos cíclicos no permite conocer el formato efectivo.

**Límites declarados** (M1/VA-02): no se resuelven temas (`w:asciiTheme`),
numeración (`w:numPr`), formato condicional de tablas, estilos de tabla ni
cambios de formato con seguimiento (`w:rPrChange`/`w:pPrChange`). Leer
`basedOn` no promete soporte completo de estilos. Un `word/styles.xml`
ausente o mal formado se trata como ausente: las reglas afectadas fallan
con `(ausente)` en vez de tumbar la validación.

El alcance de los títulos es explícito: `contexto: cuerpo` excluye los
párrafos con estilo de título (los títulos tienen su propio formato en el
manual). Si una regla necesita evaluar títulos, debe seleccionarlos con su
propio `parrafo_xpath`; el analizador no los exime por sí mismo.

`contexto: cuerpo_prosa` es el subconjunto de prosa de `cuerpo`: además de
los títulos, excluye listas (`w:numPr` o estilo `List Paragraph`), captions
de tabla y figura (estilo `Caption`) y leyendas (`---: ...`). Se usa en
`alineacion_cuerpo`, porque el manual solo justifica el texto continuo;
`fuente_principal`, `tamano_cuerpo` e `interlineado` siguen con
`contexto: cuerpo` para revisar también listas y títulos.

---

## Componentes de código

| Archivo | Clases | Responsabilidad |
|---------|--------|-----------------|
| `validator/automata.py` | `DFA`, `Transicion`, `GramaticaEstructura`, `PDA`, `TransicionPDA` | DFA, PDA y gramáticas puras, sin conocimiento del DOCX |
| `validator/tokenizer.py` | `Token`, `tokenizar`, `seccion`, `solo`, `textos` | Análisis léxico: flujo tipado del `<w:body>` y cortes por sección |
| `validator/analizadores.py` | `Analizador` (ABC), `AnalizadorXML`, `AnalizadorRegex`, `AnalizadorLista`, `AnalizadorConteoNodos`, `AnalizadorImagen`, `AnalizadorCantidadPatron`, `AnalizadorListaObligatoria`, `AnalizadorHipervinculo`, `AnalizadorPaginacion`, `AnalizadorNotaPie`, `AnalizadorTocApunta`, `AnalizadorTocNumeracion`, `DeteccionTipo` | Analizadores de hoja sobre `ExtractedDocx` |
| `validator/compilador.py` | `CompilerDSL`, `ReglaCompilada`, `AutomataSecuencia`, `GramaticaEstructuraAnalizador`, `AutomataPila` | Compila el YAML DSL → analizadores y produce `List[RuleResult]` |
| `validator/engine.py` | `validate_docx` (modificado) | Detecta el formato (DSL vs legacy) y delega |
| `reglas_dsl_ejemplo.yaml` | — | Archivo de ejemplo completo del formato DSL |
| `reglas_unt.yaml` | — | 54 reglas de producción, incluidas `deteccion_tipo_documento` y `track_changes_sin_resolver` |
| `reglas_unt_pendientes.yaml` | — | 5 estructuras implementadas y **sin** probar contra documentos reales (no hay plantillas de esos tipos); no lo carga la API |

---

## Paridad de contrato

| Contrato | Legacy | DSL | ¿Cambia? |
|----------|--------|-----|----------|
| `validate_docx() -> List[RuleResult]` | ✅ | ✅ | No |
| `build_report() -> {semaforo, resumen, resultados}` | ✅ | ✅ | No |
| `RuleResult.to_dict()` campos | ✅ | ✅ | No |
| `ValidarResponse` (API, español) | ✅ | ✅ | No |
| CLI `python -m validator.cli` | ✅ | ✅ | No |

---

## Ejecutar

```bash
# Con el motor (detecta el formato automáticamente)
python -m validator.cli tesis.docx reglas_dsl_ejemplo.yaml --json

# Tests específicos del DSL
pytest tests/test_dsl.py tests/test_f2_automatas.py tests/test_f3_mecanizacion.py -v
```

---

## Extensión

Para agregar un tipo de analizador nuevo:
1. Crear la clase que herede de `Analizador` en `validator/analizadores.py`
   (o en `automata.py` si es compuesto).
2. Registrar la sección en `SECCIONES_ANALIZADOR` y en `_FABRICAS` de
   `validator/compilador.py`.
3. Agregar un ejemplo en `reglas_dsl_ejemplo.yaml` y un test en
   `tests/test_dsl.py`.

---

## Linter del DSL

El linter (`validator/dsl_check.py`) valida la configuración de las reglas en
tiempo de carga. Detecta:

- **XPath no evaluables**: valida la expresión completa con el compilador de
  lxml (`etree.XPath(expr, namespaces=NS)`), así que distingue los literales
  entre comillas (`'Palabras clave:'`) de los prefijos de namespace y detecta
  también la sintaxis inválida (p. ej. `//wp:ind` o `//w:p[`). Evita que la
  regla reviente con `XPathEvalError` en tiempo de ejecución.
- **Claves desconocidas a nivel de regla**: el conjunto de claves válidas es
  **cerrado** (30 en total: las 19 secciones de analizador más los 11 campos
  de regla). Cualquier otra clave —una sección mal escrita (`atributo_xmls`) o
  un truncamiento (`conteo`)— se reporta; antes la regla desaparecía del
  reporte en silencio. La similitud difusa solo se usa para sugerir la sección
  correcta.
- **Configuraciones de sección que no son diccionario** (p. ej.
  `lista_obligatoria: "x"`) — antes causaban `AttributeError` en runtime.
- **Errores de autómatas** (`automata_secuencia`, `automata_pila`): estados
  duplicados, transiciones imposibles y ciclos épsilon.
- **Severidades fuera del catálogo** `error`/`warning` (derivado de
  `validator.models.Severity`).
- **Valores de `aplicar_si`** que no son un tipo documental declarado. Los
  centinelas `sin_determinar` y `contradictorio` son valores legítimos.
- **`id` de regla duplicado** — doble conteo en el resumen y observaciones
  indistinguibles.

Los hallazgos se devuelven como `DSLValidationError` con un mensaje legible
para el usuario. Ejemplos reales:

```text
[r1] atributo_xml: XPath inválido '//wp:ind': prefijo de namespace desconocido ['wp'] (prefijos válidos: ['a', 'pic', 'r', 'w'])
[r1] sección desconocida 'atributo_xmls' (¿quiso decir 'atributo_xml'?)
[r1] severidad: 'aviso' no es válida (valores admitidos: ['error', 'warning'])
```
