"""Analizadores de hoja para el DSL declarativo.

Definen la clase base `Analizador` y los analizadores atómicos:
- AnalizadorXML: atributos y presencia de nodos XML (xpath).
- AnalizadorRegex: patrones de texto sobre el contenido del documento.
- AnalizadorLista: pertenencia a una lista de valores permitidos.
- AnalizadorConteoNodos: contador genérico de nodos / párrafos (conteo_nodos).
- AnalizadorImagen: presencia de imágenes (blips) — subclase del anterior.
- AnalizadorCantidadPatron: cuenta palabras/matches/entradas (patron_cantidad).
- AnalizadorListaObligatoria: ítems obligatorios en una sección (lista_obligatoria).
- AnalizadorHipervinculo: hipervínculos que matchean un patrón (hipervinculo_texto).
- AnalizadorTocApunta: entradas del índice apuntan a secciones reales (toc_apunta).
- AnalizadorTocNumeracion: jerarquía de numeración del índice (toc_numeracion).

Los analizadores de tipo compuesto (secuencia, gramática, pila) viven en
`automata.py`; la clase base `Analizador` los integra a todos.

A diferencia del `checks.py` legacy (que opera sobre una regla completa
`{"checks": [...]}`), los analizadores del DSL reciben **una sola**
comprobación declarada y la ejecutan de forma autocontenida. Esto los
hace componibles y testables por separado.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .extractor import NS, ExtractedDocx, W, text_of
from .tokenizer import PARRAFO, _es_heading, seccion, tokenizar

# Prefijos de namespace para resolver names en atributos (ej. "@w:val").
PREFIX_NS = NS


def _resolve_attr_key(atributo: str) -> str:
    """Convierte '@w:val' en '{namespace}val' para lxml .get()."""
    name = atributo[1:]
    if ":" in name:
        prefix, local = name.split(":", 1)
        if prefix in PREFIX_NS:
            return "{" + PREFIX_NS[prefix] + "}" + local
    return name


class Analizador(ABC):
    """Interfaz común de todos los analizadores del DSL.

    Cada analizador se construye a partir de la configuración declarada
    en una sección del YAML (p. ej. `analizador_xml`, `patron_texto`) y
    ejecuta `analizar(extracted)` para producir (pasó, detalle).
    """

    def __init__(self, config: dict):
        self.config = config or {}
        # Nodo objetivo (párrafo/subnodo) que determinó la última ejecución.
        # Permite que el motor enriquezca `location` con "página N" (ítem 1).
        self.ultimo_nodo = None
        # Valor legible por maquina de la ultima ejecucion, cuando el
        # analizador produce uno. `analizar()` devuelve texto pensado para
        # personas, asi que no sirve para decidir condiciones `aplicar_si`.
        # Los analizadores de deteccion lo rellenan; los demas lo dejan None.
        self.valor: str | None = None

    @abstractmethod
    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]: ...

    # -- utilidades compartidas -------------------------------------------
    def _nodos(self, extracted: ExtractedDocx, parte: str, contexto: str):
        # Consulta XPath con cache (F4): mismo (parte, contexto, xpath) se
        # evalúa una sola vez por documento.
        nodos = extracted.xpath(parte, self.config.get("xpath", ""), contexto)
        self.ultimo_nodo = nodos[0] if nodos else None
        return nodos


class AnalizadorXML(Analizador):
    """Verifica atributos o presencia de nodos vía XPath.

    Se usa para los DSL `atributo_xml` y `presencia_xml`.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        comp = self.config.get("comparacion", "exists")

        try:
            nodes = self._nodos(extracted, parte, contexto)
        except ValueError:
            # La parte no existe (p. ej. tesis sin header*.xml): si la regla
            # declara `n_a_si_ausente`, el incumplimiento no aplica (n/a).
            if self.config.get("n_a_si_ausente"):
                return True, f"no aplica (parte '{parte}' ausente)"
            raise

        # Presencia simple
        if comp in ("exists", "not_exists"):
            if comp == "exists":
                return len(nodes) > 0, f"exists {len(nodes)} nodos"
            return len(nodes) == 0, f"not_exists {len(nodes)} nodos"

        # Atributo
        atributo = self.config.get("atributo")
        esperado = self.config.get("esperado")
        if atributo is None:
            return False, "falta 'atributo' para comparación de atributo"
        key = _resolve_attr_key(atributo)
        vals = [n.get(key) for n in nodes]
        vals = [v for v in vals if v is not None]
        self.valor = vals[0] if vals else None

        if comp == "eq":
            ok = bool(vals) and vals[0] == esperado
        elif comp == "all_eq":
            ok = bool(vals) and all(v == esperado for v in vals)
        elif comp == "contains":
            ignore_case = self.config.get("ignore_case", False)
            if ignore_case:
                ok = bool(vals) and all(str(esperado).lower() in str(v).lower() for v in vals)
            else:
                ok = bool(vals) and all(esperado in v for v in vals)
        else:
            return False, f"comparación '{comp}' no soportada"
        return ok, f"{atributo}={vals[:3]} esperado={esperado}"


class AnalizadorRegex(Analizador):
    """Aplica una expresión regular al contenido textual de nodos.

    `coincidencia`: `todos` (todos los nodos deben matchear, por defecto),
    `alguno` (al menos uno), `ninguno` (ninguno).
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        patron = self.config.get("patron", "")
        coincidencia = self.config.get("coincidencia", "todos")
        ignore_case = self.config.get("ignore_case", False)

        nodes = self._nodos(extracted, parte, contexto)
        textos = [t.text for n in nodes for t in n.iter(W + "t") if t.text]
        if not textos:
            return False, "sin nodos w:t que evaluar"

        flags = re.IGNORECASE if ignore_case else 0
        rx = re.compile(patron, flags)

        def _matchea(s: str) -> bool:
            c = self.config.get("comparacion", "regex")
            if c == "fullmatch":
                # Sin strip para preservar el comportamiento del motor legacy
                # (checks.run_check usa `patron.fullmatch` sobre el w:t tal cual).
                return bool(rx.fullmatch(s))
            return bool(rx.search(s))

        if coincidencia == "todos":
            incumplen = [t for t in textos if not _matchea(t)]
            return not incumplen, f"textos={len(textos)} incumplen={len(incumplen)}"
        if coincidencia == "alguno":
            ok = any(_matchea(t) for t in textos)
            return ok, f"textos={len(textos)} alguno_matchea={ok}"
        if coincidencia == "ninguno":
            ok = not any(_matchea(t) for t in textos)
            return ok, f"textos={len(textos)} ninguno_matchea={ok}"

        return False, f"coincidencia '{coincidencia}' no soportada"


class AnalizadorLista(Analizador):
    """Verifica que el texto de los nodos pertenezca a una lista permitida."""

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        lista = self.config.get("lista", [])
        ignore_case = self.config.get("ignore_case", False)

        nodes = self._nodos(extracted, parte, contexto)
        textos = [text_of(n).strip() for n in nodes if text_of(n).strip()]
        if not textos:
            return False, "sin nodos de texto que evaluar"

        def _norm(s: str) -> str:
            s = re.sub(r"\s+", " ", s).strip()
            return s.lower() if ignore_case else s

        valores = [_norm(t) for t in textos]
        permitidos = [_norm(x) for x in lista]
        incumplen = [v for v in valores if v not in permitidos]
        return not incumplen, f"textos={valores[:3]} en_lista_faltan={incumplen[:3]}"


class AnalizadorConteoNodos(Analizador):
    """Cuenta nodos (XPath) o párrafos de una sección y compara min/máx.

    Es el contador genérico para `conteo_nodos` (F3). Si la config lleva
    `seccion`, cuenta los PÁRRAFOS no vacíos de esa sección vía el
    tokenizer en lugar de XPath (p. ej. referencias mínimas).
    """

    def _etiqueta(self) -> str:
        return self.config.get("label", "nodos")

    def _cuenta(self, extracted: ExtractedDocx) -> int:
        sec = self.config.get("seccion")
        if sec:
            corte = seccion(tokenizar(extracted), sec["inicio"], sec.get("fin"))
            return sum(1 for t in corte if t.tipo == PARRAFO and t.texto.strip())
        nodos = self._nodos(
            extracted,
            self.config.get("parte", "document"),
            self.config.get("contexto", "todos"),
        )
        return len(nodos)

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        minimo = self.config.get("cantidad_minima", 1)
        maximo = self.config.get("cantidad_maxima")
        multiples = self.config.get("cantidades_multiples")
        n = self._cuenta(extracted)
        etq = self._etiqueta()
        if multiples:
            # Se cumple si la cantidad alcanza CUALQUIER mínimo declarado
            # (p. ej. mínimo según tipo de investigación: [20, 30, 20]).
            ok = any(n >= m for m in multiples)
            return ok, f"{etq}={n} minimos={multiples}"
        if n < minimo:
            return False, f"{etq}={n} minimo={minimo}"
        if maximo is not None and n > maximo:
            return False, f"{etq}={n} maximo={maximo}"
        return True, f"{etq}={n} minimo={minimo}"


class AnalizadorImagen(AnalizadorConteoNodos):
    """Verifica la presencia (y cantidad) de imágenes embebidas.

    Misma semántica que el legacy `imagen_presencia` (checks.run_check):
    detalle `imagenes=N minimo=M`. Es un caso particular de
    `AnalizadorConteoNodos` con etiqueta "imagenes".
    """

    def _etiqueta(self) -> str:
        return "imagenes"


class AnalizadorCantidadPatron(Analizador):
    r"""Cuenta palabras, matches de regex o entradas en una sección/texto.

    Sección DSL `patron_cantidad` (F3). `operacion`:
      count_words   — palabras (`\w+`) del texto contado
      count_matches — matches de `patron`
      count_entries — entradas separadas por ',' o ';' del texto tras
                      el primer ':' (p. ej. "Palabras clave: a, b, c").
    El texto contado proviene de una `seccion` (tokenizer + `filtro`
    opcional por párrafo) o de nodos XPath.
    """

    def _piezas(self, extracted: ExtractedDocx) -> list[str]:
        sec = self.config.get("seccion")
        xpath_cfg = self.config.get("xpath")
        if sec:
            corte = seccion(tokenizar(extracted), sec["inicio"], sec.get("fin"))
            piezas = [t.texto for t in corte if t.tipo == PARRAFO and t.texto.strip()]
        elif xpath_cfg:
            nodos = self._nodos(
                extracted,
                self.config.get("parte", "document"),
                self.config.get("contexto", "todos"),
            )
            piezas = [text_of(n).strip() for n in nodos if text_of(n).strip()]
        else:
            return []
        filtro = self.config.get("filtro")
        if filtro:
            rx = re.compile(filtro, re.IGNORECASE if self.config.get("ignore_case", True) else 0)
            piezas = [p for p in piezas if rx.search(p)]
        return piezas

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "count_words")
        minimo = self.config.get("cantidad_minima", 1)
        maximo = self.config.get("cantidad_maxima")
        texto = " ".join(self._piezas(extracted))

        if operacion == "count_words":
            n = len(re.findall(r"\w+", texto))
            detalle = f"palabras={n}"
        elif operacion == "count_matches":
            patron = self.config.get("patron", "")
            flags = re.IGNORECASE if self.config.get("ignore_case", False) else 0
            n = len(re.findall(patron, texto, flags))
            detalle = f"matches={n}"
        elif operacion == "count_entries":
            cuerpo = texto.split(":", 1)[1] if ":" in texto else texto
            n = len([x for x in re.split(r"[,;]", cuerpo) if x.strip()])
            detalle = f"entradas={n}"
        else:
            return False, f"operación '{operacion}' no soportada"

        if n < minimo:
            return False, f"{detalle} minimo={minimo}"
        if maximo is not None and n > maximo:
            return False, f"{detalle} maximo={maximo}"
        return True, f"{detalle} minimo={minimo}"


class AnalizadorListaObligatoria(Analizador):
    """Verifica que cada ítem de `items` aparezca en la sección/texto.

    Sección DSL `lista_obligatoria` (F3) para anexos mínimos: substring
    normalizado (colapso de whitespace y, por defecto, ignore_case).
    """

    def _texto(self, extracted: ExtractedDocx) -> str:
        sec = self.config.get("seccion")
        if sec:
            corte = seccion(tokenizar(extracted), sec["inicio"], sec.get("fin"))
            return " ".join(t.texto for t in corte if t.tipo == PARRAFO)
        nodos = self._nodos(
            extracted,
            self.config.get("parte", "document"),
            self.config.get("contexto", "todos"),
        )
        return " ".join(text_of(n) for n in nodos)

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        items = self.config.get("items", [])
        texto = self._texto(extracted)
        ignore = self.config.get("ignore_case", True)

        def _norm(s: str) -> str:
            s = re.sub(r"\s+", " ", s).strip()
            return s.lower() if ignore else s

        texto_norm = _norm(texto)
        faltan = [it for it in items if _norm(it) not in texto_norm]
        if not faltan:
            return True, f"items_obligatorios={len(items)} completo"
        return False, f"items_obligatorios={len(items)} faltan={faltan[:8]}"


class AnalizadorPaginacion(Analizador):
    """Verifica que los párrafos objetivo estén en páginas físicas distintas.

    Sección DSL `paginacion` (F2 ítem 1). La paginación real se calcula en
    el extractor contando los saltos que Word persiste en el XML
    (`w:lastRenderedPageBreak` y `w:br w:type="page"`). Cada párrafo objetivo
    (p. ej., un índice de contenidos/tablas/figuras) debe caer en una página
    física distinta para que la regla pase.

    Uso:
        paginacion:
          xpaths:
            - //w:body//w:p[contains(...)]
            - //w:body//w:p[contains(...)]
          comparacion: paginas_distintas

    No necesita verificar la separación cuando no es aplicable: si NINGUNA
    o alguna de las secciones objetivo no es identificable (p. ej. la
    plantilla usa un "Índice" genérico dentro de sdtContent que el xpath no
    localiza, o falta el índice de tablas), la regla pasa como n/a y no
    produce un falso positivo: solo juzga la paginación de las secciones
    que existen. La sección de "presencia" la cubren otras reglas.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        xpaths = self.config.get("xpaths")
        if not isinstance(xpaths, list) or len(xpaths) < 2:
            return False, "paginacion requiere xpaths (>=2)"

        ubicaciones = []
        sin_coincidencia = []
        for xpath in xpaths:
            nodos = extracted.xpath("document", xpath, "todos")
            if not nodos:
                sin_coincidencia.append(xpath)
                continue
            para = nodos[0]
            self.ultimo_nodo = para
            pagina = extracted.pagina_de(para)
            if pagina is None:
                return False, f"pagina_no_disponible={xpath}"
            ubicaciones.append((pagina, para))

        # No todas las secciones objetivo son identificables (p. ej. la
        # plantilla usa un "Índice" genérico dentro de sdtContent, o falta el
        # índice de tablas): esta regla juzga solo la PAGINACIÓN, no la
        # presencia de secciones, así que pasa como n/a y no genera un falso
        # positivo (ver revisión técnica PR #28).
        if sin_coincidencia:
            return True, "indices_no_verificables (n/a)"

        paginas = [p for p, _ in ubicaciones]
        ok = len(set(paginas)) == len(paginas)
        detalle = "; ".join(f"{i + 1}: página {p}" for i, (p, _) in enumerate(ubicaciones))
        if ok:
            return True, f"paginas_distintas={paginas}"
        return False, f"paginas_repetidas={paginas}; {detalle}"


class AnalizadorHipervinculo(Analizador):
    """Detecta hipervínculos (w:hyperlink) cuyo texto coincida con un patrón.

    Sección DSL `hipervinculo_texto` (F3), p. ej. ORCID:
    `https://orcid.org/XXXXXXXXXXXXXXXX` (16 dígitos).
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        patron = self.config.get("patron", "")
        ignore_case = self.config.get("ignore_case", True)
        minimo = self.config.get("cantidad_minima", 1)
        maximo = self.config.get("cantidad_maxima")

        nodos = self._nodos(extracted, parte, contexto)
        rx = re.compile(patron, re.IGNORECASE if ignore_case else 0)
        coinciden = [n for n in nodos if rx.search(text_of(n))]
        n = len(coinciden)
        if n < minimo:
            return False, f"hipervinculos={n} minimo={minimo}"
        if maximo is not None and n > maximo:
            return False, f"hipervinculos={n} maximo={maximo}"
        return True, f"hipervinculos={n} minimo={minimo}"


class AnalizadorNotaPie(Analizador):
    """Valida la consistencia de la numeración de las notas al pie (ítem 3).

    Sección DSL `nota_pie`, `operacion: numeracion_consistente`: los ids de
    `w:footnoteReference` en el cuerpo deben ser consecutivos (1..N, sin
    saltos, sin repetir) y, si la parte `word/footnotes.xml` existe, cada id
    referenciado debe estar definido ahí. Un documento SIN notas al pie pasa
    (n/a documentado), porque la ausencia no es un desvío.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "numeracion_consistente")
        if operacion != "numeracion_consistente":
            return False, f"operación '{operacion}' no soportada"

        ids = [int(i) for i in extracted.xpath("document", "//w:footnoteReference/@w:id", "todos")]
        if not ids:
            return True, "sin_notas_al_pie (n/a)"

        if len(ids) != len(set(ids)):
            return False, f"notas_ids={sorted(ids)} duplicadas=True"

        ord = sorted(ids)
        consecutivas = ord == list(range(1, len(ord) + 1))
        definidas = True
        faltantes: list[int] = []
        fn = extracted.footnotes
        if fn is not None:
            disponibles = {int(e.get(W + "id")) for e in fn.iter(W + "footnote") if e.get(W + "id")}
            faltantes = [i for i in ord if i not in disponibles]
            definidas = not faltantes

        ok = consecutivas and definidas
        detalle = f"notas_ids={ord} consecutivas={consecutivas}"
        if faltantes:
            detalle += f" sin_definir={faltantes}"
        return ok, detalle


# ---------------------------------------------------------------------------
# Índice / tabla de contenidos (ítems 11 y 12 del PLAN_BACKLOG_FUTURO).
# ---------------------------------------------------------------------------

# Título que abre la región del índice de contenidos. Cubre "ÍNDICE" (plantilla
# y factory) y "INDICE DE CONTENIDOS" (factory). IGNORECASE vía `re` en el
# analizador. El texto se compara SIN acentos (re.IGNORECASE no iguala "Í" con
# "I"), así que el patrón es ASCII; la lógica de región elimina tildes primero.
REFERENCIA_INDICE = r"^indice(\s+de\s+contenidos)?$"

# Mapa para quitar tildes al normalizar (matching tolerante en el ítem 11).
_MAP_ACENTOS = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")


def _sin_acentos(s: str) -> str:
    """Elimina tildes de un texto (para matching ASCII de regiones)."""
    return s.translate(_MAP_ACENTOS)


def _norm_indice(texto: str) -> str:
    """Texto de una entrada de índice normalizado para MATCHING (ítem 11).

    Quita el prefijo de numeración (romano "I." o decimal "1.1."), el número
    de página al final (arábigo "10" o romano "ii"), separadores sueltos,
    tildes y colapsa el whitespace, en mayúsculas.
    """
    s = texto.strip()
    s = re.sub(r"^\s*(?:[IVXLC]+\s*\.|(?:\d+)+(?:\.\d+)*\s*\.?\s*)", "", s)
    s = re.sub(r"\s*[ivxlc]{1,5}\s*$", "", s)
    s = re.sub(r"\s*\d+\s*$", "", s)
    s = re.sub(r"[()\[\],;:¿?¡!.]", " ", s)
    s = s.translate(_MAP_ACENTOS)
    return re.sub(r"\s+", " ", s).upper().strip()


def _sigpalabra(s: str) -> str:
    """Primera palabra con >=4 caracteres de un texto normalizado (o vacío)."""
    for tk in s.split():
        if len(tk) >= 4:
            return tk
    return ""


def _entradas_indice(extracted: ExtractedDocx, regex_indice: str = REFERENCIA_INDICE) -> list[dict]:
    """Entradas del índice de contenidos en orden de documento.

    Regiones: párrafos NO-título que siguen a un título que matchea
    `regex_indice` (solo estilos de encabezado), hasta el siguiente título
    de cualquier nivel. Se acumulan TODAS las regiones que matcheen (la
    plantilla usa un único "Índice"; el factory "ÍNDICE" + "INDICE DE
    CONTENIDOS"). Cada entrada lleva su nodo `w:p` (para `ultimo_nodo`).
    """
    body = extracted.document.find(W + "body")
    if body is None:
        return []
    rx = re.compile(regex_indice, re.IGNORECASE)
    entradas: list[dict] = []
    en_region = False
    for p in body.findall(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        estilo = st.get(W + "val") if st is not None else ""
        texto = text_of(p).strip()
        if _es_heading(estilo):
            en_region = bool(rx.search(_sin_acentos(texto)))
            continue
        if en_region and texto:
            entradas.append({"texto": texto, "nivel": 1, "nodo": p})
    return entradas


def _títulos_cuerpo(extracted: ExtractedDocx) -> set[str]:
    """Títulos del cuerpo normalizados (solo estilos de encabezado)."""
    body = extracted.document.find(W + "body")
    if body is None:
        return set()
    titulos: set[str] = set()
    for p in body.findall(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        estilo = st.get(W + "val") if st is not None else ""
        if _es_heading(estilo):
            texto = text_of(p).strip()
            if texto:
                titulos.add(_norm_indice(texto))
    return titulos


def _parse_numero_indice(texto: str) -> tuple | None:
    """Número de una entrada del índice: ("romano", n) o ("decimal", (k, ...))."""
    m = re.match(r"^\s*([IVXLC]+)[\.\s]+(.+)$", texto)
    if m:
        letras = m.group(1).upper()
        valores = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
        total = 0
        for i, c in enumerate(letras):
            v = valores[c]
            if i + 1 < len(letras) and valores[letras[i + 1]] > v:
                total -= v
            else:
                total += v
        return ("romano", total)
    m = re.match(r"^\s*(\d+(?:\.\d+)+)\s*\.?\s*(.+)$", texto)
    if m:
        return ("decimal", tuple(int(x) for x in m.group(1).split(".")))
    return None


class AnalizadorTocApunta(Analizador):
    """Verifica que el índice apunte a secciones reales del documento (ítem 11).

    Sección DSL `toc_apunta`, `operacion: entradas_corresponden`: cada
    entrada de la región del índice de contenidos debe tener su palabra
    significativa (>=4 caracteres, sin numeración, número de página, tildes
    ni separadores) como subcadena de ALGÚN título del cuerpo. Un documento
    sin región de índice pasa (n/a documentado).

    Fiel al manual (párr. 194): "Lista estructurada de los segmentos que
    integran la investigación, según orden de presentación". NO prohíbe
    números de página (el índice de tablas los exige).
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "entradas_corresponden")
        if operacion != "entradas_corresponden":
            return False, f"operación '{operacion}' no soportada"

        entradas = _entradas_indice(extracted, self.config.get("regex_indice", REFERENCIA_INDICE))
        if not entradas:
            return True, "sin_indice (n/a)"

        titulos = _títulos_cuerpo(extracted)
        faltan: list[str] = []
        self.ultimo_nodo = None
        for e in entradas:
            norm = _norm_indice(e["texto"])
            sig = _sigpalabra(norm)
            if not sig or any(sig in t for t in titulos):
                continue
            if self.ultimo_nodo is None:
                self.ultimo_nodo = e["nodo"]
            faltan.append(e["texto"][:60])

        if faltan:
            return False, f"entrada_sin_seccion={faltan[:6]}"
        return True, "entradas_corresponden"


class AnalizadorTocNumeracion(Analizador):
    """Valida la jerarquía de numeración del índice (ítem 12).

    Sección DSL `toc_numeracion`, `operacion: jerarquia_consistente`:

    - Capítulos en romano (I, II, ...) consecutivos, sin saltos.
    - Subsecciones decimales (1.1, 1.1.1, ...) bajo el capítulo actual y en
      orden preorder estricto (un padre precede a sus hijos; 1.1 < 1.1.1 <
      1.1.2 < 1.2 < 1.3 ...).
    - La primera subsección de cada capítulo es K.1.

    NO exige contigüidad de subsecciones hermanas (1.1 → 1.3 es aceptable)
    para evitar falsos positivos cuando una sección "no aplica" y se omite;
    solo orden y pertenencia al capítulo. Un documento sin región de índice
    pasa (n/a documentado).
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "jerarquia_consistente")
        if operacion != "jerarquia_consistente":
            return False, f"operación '{operacion}' no soportada"

        entradas = _entradas_indice(extracted, self.config.get("regex_indice", REFERENCIA_INDICE))
        if not entradas:
            return True, "sin_indice (n/a)"

        caps: list[int] = []
        prev: tuple | None = None
        primera = True
        fallos: list[str] = []
        self.ultimo_nodo = None
        for e in entradas:
            num = _parse_numero_indice(e["texto"])
            if num is None:
                continue
            tipo, valor = num
            if tipo == "romano":
                if caps and valor != caps[-1] + 1:
                    fallos.append(f"salto_capitulo={valor}")
                caps.append(valor)
                prev = None
                primera = True
                continue
            # decimal
            if not caps:
                fallos.append("subseccion_sin_capitulo")
            elif valor[0] != caps[-1]:
                fallos.append(f"capitulo_descolgado={e['texto'][:60]}")
            elif primera:
                if len(valor) >= 2 and valor[1] != 1:
                    fallos.append(f"primera_subseccion_no_K1={e['texto'][:60]}")
                primera = False
                prev = valor
            else:
                if prev is not None and not (prev < valor):
                    fallos.append(f"fuera_de_orden={e['texto'][:60]}")
                prev = valor

        if fallos:
            if self.ultimo_nodo is None:
                self.ultimo_nodo = entradas[0]["nodo"]
            return False, "jerarquia_incorrecta; " + " | ".join(fallos[:6])
        return True, "jerarquia_ok"


# ---------------------------------------------------------------------------
# deteccion_tipo: qué tipo de documento es (Semana 6, paso 2)
# ---------------------------------------------------------------------------

NIVEL_DECLARADO = "declarado"
NIVEL_INFERIDO = "inferido"
NIVEL_NO_DETERMINADO = "sin_determinar"

# Valores que publica en el contexto cuando no se puede afirmar un tipo.
TIPO_SIN_DETERMINAR = "sin_determinar"
TIPO_CONTRADICTORIO = "contradictorio"

# Casillas del Anexo 10 que sabemos leer de forma determinista. Un documento
# puede marcarlas como texto plano o como símbolo Wingdings (`w:sym`), que es
# como las dibuja Word; se cubren las dos formas.
_CASILLA_MARCADA_TXT = re.compile(r"[☒☑✔■]|\[\s*(?:[xX✓])\s*\]|\(\s*[xX]\s*\)")
_CASILLA_VACIA_TXT = re.compile(r"[☐□◻]|\[\s*\]|\(\s*\)")
# Wingdings: F0FE/F0FC/F0A3 marcadas; F0A8/F0B0 son la casilla vacía.
_SYM_MARCADA = {"F0FE", "F0FC", "F0A3"}
_SYM_VACIA = {"F0A8", "F0B0"}


def _norm_deteccion(s: str) -> str:
    """Normaliza para comparar firmas: mayúsculas, sin tildes, sin
    indentación y con espacios colapsados."""
    return re.sub(r"\s+", " ", _sin_acentos(s).upper()).strip()


def _estado_casilla(p) -> tuple[bool, bool]:
    """(marcada, hay_casilla) para un párrafo `w:p`.

    Una casilla sin marcar hace que el párrafo NO sea una declaración, aunque
    tenga una etiqueta de tipo al lado: es el caso "desmarcado", que es el
    error más fácil de cometer al leer.
    """
    texto = text_of(p)
    for sym in p.iter(f"{W}sym"):
        char = (sym.get(W + "char") or "").upper()
        if char in _SYM_VACIA:
            return False, True
        if char in _SYM_MARCADA:
            return True, True
    if _CASILLA_VACIA_TXT.search(texto):
        return False, True
    if _CASILLA_MARCADA_TXT.search(texto):
        return True, True
    return False, False


class DeteccionTipo(Analizador):
    """Determina el tipo de documento de forma determinista.

    Sección DSL `deteccion_tipo`. Tres niveles, en orden de preferencia
    (decisión 2 del diseño):

    1. **Declarado** — casilla marcada del Anexo 10, con la etiqueta del tipo
       que el autor eligió. Es una declaración del autor, no una inferencia.
    2. **Inferido** — se cuentan las firmas estructurales de cada tipo y gana
       el primero que alcance su `minimo`. El orden de `firmas` es el de
       especificidad (decisión 2: el informe gana al proyecto).
    3. **Sin determinar** — ninguna firma alcanzó su umbral.

    Si hay nivel 1 y nivel 2 y no coinciden, se publica
    `TIPO_CONTRADICTORIO`: es preferible decir que hay una contradicción
    visible a elegir en silencio.

    El valor publicado (`Analizador.valor`) es el identificador canónico del
    tipo, que es lo que consume `aplicar_si` en las reglas de estructura. El
    nivel y la evidencia quedan además en `self.nivel` y `self.evidencia`,
    para que el reporte pueda explicarle al estudiante por qué se eligió ese
    tipo sin tener que parsear el texto del detalle.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        # Nivel que decidió la detección (declarado / inferido / sin_determinar).
        self.nivel: str = NIVEL_NO_DETERMINADO
        # Evidencia concreta: la etiqueta del Anexo 10 leída, o las firmas
        # que alcanzaron el umbral.
        self.evidencia: list[str] = []

    def _resolver(self, nivel: str, tipo: str | None, detalle: str) -> tuple[bool, str]:
        self.nivel = nivel
        self.valor = tipo if tipo is not None else TIPO_SIN_DETERMINAR
        return tipo is not None, detalle

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        body = extracted.document.find(W + "body")
        if body is None:
            self.nivel = NIVEL_NO_DETERMINADO
            self.valor = TIPO_SIN_DETERMINAR
            return False, "sin_determinado (documento sin cuerpo)"

        parrafos = body.findall(W + "p")
        declaracion, etiqueta = self._tipo_declarado(parrafos)
        inferido, evidencia = self._tipo_inferido(parrafos)

        if declaracion and inferido and declaracion != inferido:
            self.nivel = NIVEL_NO_DETERMINADO
            self.evidencia = [etiqueta, *evidencia]
            self.valor = TIPO_CONTRADICTORIO
            return False, (
                f"contradictorio: declarado={declaracion} ('{etiqueta}') "
                f"inferido={inferido} ({', '.join(evidencia)})"
            )

        if declaracion:
            self.evidencia = [etiqueta]
            return self._resolver(
                NIVEL_DECLARADO, declaracion, f"declarado={declaracion} ('{etiqueta}')"
            )

        if inferido:
            self.evidencia = evidencia
            quoted = ", ".join(f'"{e}"' for e in evidencia)
            return self._resolver(NIVEL_INFERIDO, inferido, f"inferido={inferido} ({quoted})")

        self.evidencia = []
        return self._resolver(
            NIVEL_NO_DETERMINADO, None, "sin_determinado (ninguna firma alcanzó su mínimo)"
        )

    # -- nivel 1: declaración del Anexo 10 --------------------------------
    def _tipo_declarado(self, parrafos) -> tuple[str | None, str]:
        """Tipo cuya casilla aparece marcada junto a su etiqueta.

        La casilla y la etiqueta deben estar en el MISMO párrafo: si estuvieran
        separadas, no habría forma de saber a cuál corresponde cada casilla.

        Si en un mismo párrafo casan varias etiquetas, gana la MÁS LARGA. El
        cotejo es por subcadena y unas etiquetas contienen a otras: "INFORME
        DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO" contiene "PROYECTO DE
        INVESTIGACIÓN CUANTITATIVO", así que las dos casan en el mismo
        párrafo. Con el orden del diccionario el resultado dependía de dónde
        estuviera escrita cada clave en el YAML, que es una fuente de fallo
        silencioso. Con la más larga gana, el texto del Anexo 10 basta para
        decidir y reordenar el YAML no cambia nada.
        """
        etiquetas = self.config.get("declaracion", {}).get("etiquetas", {})
        if not etiquetas:
            return None, ""
        for p in parrafos:
            marcada, hay_casilla = _estado_casilla(p)
            if not hay_casilla or not marcada:
                continue
            texto = _norm_deteccion(text_of(p))
            candidatos: list[tuple[int, str, str]] = []
            for tipo, alias in etiquetas.items():
                for etiqueta in [tipo, *alias]:
                    clave = _norm_deteccion(etiqueta)
                    if clave and clave in texto:
                        candidatos.append((len(clave), tipo, etiqueta))
            if candidatos:
                # Más larga primero. El nombre del tipo solo desempata, para
                # que un empate no dependa del orden del diccionario.
                candidatos.sort(key=lambda c: (-c[0], c[1]))
                _, tipo, etiqueta = candidatos[0]
                return tipo, etiqueta
        return None, ""

    # -- nivel 2: firmas estructurales ------------------------------------
    def _tipo_inferido(self, parrafos) -> tuple[str | None, list[str]]:
        textos = [_norm_deteccion(text_of(p)) for p in parrafos]
        for firma in self.config.get("firmas", []):
            minimo = firma.get("minimo", 1)
            encontradas = [
                ev
                for ev in firma.get("evidencia", [])
                if any(_norm_deteccion(ev) in t for t in textos)
            ]
            if len(encontradas) >= minimo:
                return firma.get("tipo"), encontradas
        return None, []
