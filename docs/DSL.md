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
```

### 1. `atributo_xml` / `presencia_xml` → `AnalizadorXML`

Verifica atributos de nodos o su presencia vía XPath.

```yaml
atributo_xml:
  parte: document | footer | header     # defecto: document
  contexto: todos | cuerpo | seccion_cuerpo | caratula  # defecto: todos
  xpath: //w:sectPr[1]/w:pgSz
  atributo: "@w:w"                      # solo para comparaciones de valor
  comparacion: eq | all_eq | contains | exists | not_exists
  esperado: "11906"
  ignore_case: false                    # opcional (contains)
```

- `exists` / `not_exists` operan solo sobre la cantidad de nodos.
- `eq` compara el primer valor del atributo; `all_eq` todos; `contains`
  subcadena (con `ignore_case`).
- `contexto: caratula` restringe la consulta a los párrafos de la carátula:
  los `w:p` de nivel superior anteriores al primer `w:pPr/w:sectPr` del cuerpo
  (el salto que cierra la portada). Si el documento no declara ese salto, se
  toman todos los párrafos del cuerpo. Sirve para reglas que en el manual
  aplican solo a la portada y que, evaluadas sobre todo el documento,
  producirían falsos positivos.

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
```

- `todos`: todos los nodos `w:t` deben matchear.
- `alguno` / `ninguno`: al menos uno / ninguno.

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
cantidades mínima y/o máxima.

```yaml
imagen:
  parte: document
  xpath: //w:drawing//a:blip
  formato: png
  cantidad_minima: 1
  cantidad_maxima: 4     # opcional
```

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
valor mínimo:

```yaml
patron_cantidad:
  seccion: { inicio: resumen }        # opcional: acota el texto contado
  operacion: count_words | count_matches | count_entries
  patron: "..."                       # solo count_matches
  filtro: "^palabras clave"           # opcional: párrafos que cuentan
  ignore_case: true
  cantidad_minima: 159
```

- `count_words`: palabras (`\w+`) del texto contado (regla *resumen
  ≥ 159 palabras*).
- `count_matches`: matches de `patron` en el texto.
- `count_entries`: entradas separadas por `,` o `;` del texto posterior al
  primer `:` (p. ej. `Palabras clave: a, b, c` → 3). Útil con `filtro`
  sobre el párrafo de etiqueta.

### 9. `conteo_nodos` → `AnalizadorConteoNodos` (F3)

Cuenta nodos XPath **o** párrafos no vacíos de una sección y verifica
cantidad mínima:

```yaml
conteo_nodos:
  seccion: { inicio: referencias }    # modo "sección": cuenta PARRAFOs
  # — o en su lugar —
  parte: document
  xpath: //w:body//w:p                # modo "nodos"
  cantidad_minima: 20
  cantidades_multiples: [20, 30, 20]  # opcional: cualquier valor cumple
```

- Sin `xpath` pero con `seccion:`, cuenta los párrafos no vacíos
  (`PARRAFO`) del slice — usado por las reglas de *referencias mínimas*
  según tipo de investigación.
- `cantidades_multiples` permite aceptar cualquiera de varios mínimos
  (cuando el mínimo depende del tipo de investigación). Si se declara,
  **no** se usa `cantidad_minima`.

### 10. `lista_obligatoria` → `AnalizadorListaObligatoria` (F3)

Verifica que cada ítem de una lista de **contenidos obligatorios** (por
subcadena normalizada) aparezca en la sección:

```yaml
lista_obligatoria:
  seccion: { inicio: anexo }
  ignore_case: true
  items:
    - Matriz de consistencia
    - Consentimiento informado
```

- Cada ítem se busca como subcadena (normalizada a minúsculas) en el texto
  de la sección. Usado por las reglas de *anexos mínimos*.

### 11. `hipervinculo_texto` → `AnalizadorHipervinculo` (F3)

Cuenta hipervínculos (`w:hyperlink`) cuyo texto matchea un patrón y
verifica un mínimo:

```yaml
hipervinculo_texto:
  parte: document
  contexto: todos
  xpath: //w:body//w:hyperlink
  patron: 'https?://orcid\.org/\d{4}-?\d{4}-?\d{4}-?\d{4}'
  cantidad_minima: 1
```

Usado por la regla *caratula_orcid* (el código ORCID debe ser un
hipervínculo de 16 dígitos, normalizado a minúsculas y entre paréntesis).

### 12. `paginacion` → `AnalizadorPaginacion` (F2 ítem 1)

Correlaciona los párrafos con su **página física** (mapa construido a
partir de `w:lastRenderedPageBreak` y `w:br w:type="page"`) y compara las
páginas de los nodos que matchean cada XPath:

```yaml
paginacion:
  comparacion: paginas_distintas
  xpaths:
    - "//w:p[w:pPr/w:pStyle/@w:val='Ttulo1'][w:r/w:t[contains(.,'INDICE DE CONTENIDOS')]]"
    - "//w:p[w:pPr/w:pStyle/@w:val='Ttulo1'][w:r/w:t[contains(.,'INDICE DE TABLAS')]]"
    - "//w:p[w:pPr/w:pStyle/@w:val='Ttulo1'][w:r/w:t[contains(.,'INDICE DE FIGURAS')]]  "
```

- `paginas_distintas`: los títulos deben quedar en páginas separadas
  (`paginas_repetidas` si hay dos en la misma; `no_encontrado` si algún
  XPath no coincide).
- A efectos del *enriquecimiento de `ubicacion`*, el analizador expone el
  último nodo analizado (`ultimo_nodo`); cuando una regla FALLA con página
  conocida, el compilador anexa `; página N` a la ubicación.
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
   etiquetas cortas ceden ante las más específicas.
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
| `reglas_unt.yaml` | — | 48 reglas de producción, incluida `deteccion_tipo_documento` |
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