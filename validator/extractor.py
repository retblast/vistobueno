"""Extracción y normalización de un DOCX para el motor de reglas.

Encapsula el acceso al paquete OPC (zip) y expone los árboles XML
necesarios (document.xml, footer1.xml, header1.xml) más el contexto
"cuerpo": los párrafos del cuerpo REAL del documento (desde el heading
"Introducción" hasta antes de "Referencias"/"Anexos"), excluyendo
headings, párrafos vacíos y captions de tabla. Ver
unt_format_rules_schema.yaml para la convención completa de
mecanismo_verificable.
"""

import re
import zipfile
from dataclasses import dataclass, field

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}

# Grado de certeza de la página asignada a un párrafo (M3/VA-04). No toda
# página se puede afirmar con la misma fuerza: un salto explícito del autor
# es un hecho estructural, mientras que `w:lastRenderedPageBreak` es una
# caché del render de Word y la ausencia de marcadores no prueba nada.
PAGINA_COMPROBADA = "comprobada"
PAGINA_ESTIMADA = "estimada"
PAGINA_DESCONOCIDA = "desconocida"


# Cota de tamaño DESCOMPRIMIDO por parte del paquete OPC (defensa zip bomb,
# revisión 2026-10-13, hallazgo R2): la API limita la subida a 10 MB
# comprimidos, pero un ZIP hostil puede declarar entradas de pocos KB que se
# expanden a GBs al leerlas, agotando la memoria del servidor. 50 MB es un
# techo holgado para cualquier tesis real (document.xml rara vez pasa de unos
# pocos MB) y sobre el que ninguna parte legítima del formato Office tripa.
TAMANO_MAXIMO_PARTE_BYTES = 50 * 1024 * 1024


def _leer_parte(z: zipfile.ZipFile, nombre: str) -> bytes:
    """Lee una parte del paquete OPC acotando el tamaño descomprimido.

    El tope se aplica DURANTE la lectura, no sobre el `file_size` declarado
    en el central directory: ese campo puede estar falseado en un ZIP
    malicioso. Se leen como máximo `TAMANO_MAXIMO_PARTE_BYTES + 1` bytes;
    si la parte real es mayor, se lanza `zipfile.BadZipFile` (que la API
    ya traduce a 422 sin necesidad de manejo adicional).

    Args:
        z: Instancia `ZipFile` abierta sobre el documento DOCX.
        nombre: Nombre de la parte dentro del ZIP (ej. "word/document.xml").

    Returns:
        El contenido descomprimido de la parte.

    Raises:
        zipfile.BadZipFile: Si la parte descomprimida supera
            `TAMANO_MAXIMO_PARTE_BYTES` (posible zip bomb).
    """
    with z.open(nombre) as f:
        datos = f.read(TAMANO_MAXIMO_PARTE_BYTES + 1)
    if len(datos) > TAMANO_MAXIMO_PARTE_BYTES:
        raise zipfile.BadZipFile(
            f"parte '{nombre}' excede el límite de descompresión "
            f"({TAMANO_MAXIMO_PARTE_BYTES} bytes): posible zip bomb"
        )
    return datos


def text_of(node) -> str:
    """Concatena el texto de todos los nodos ``w:t`` descendientes de un nodo.

    Args:
        node: Nodo XML del que extraer el texto.

    Returns:
        El texto concatenado de todos los ``w:t`` encontrados.
    """
    return "".join(t.text or "" for t in node.iter(W + "t"))


HEADING_RE = re.compile(r"^(?:Heading|T[ií]tulo|Ttulo)\d*$", re.I)


def es_heading(val: str | None) -> bool:
    """¿El valor de un `w:pStyle` es un estilo de encabezado?

    Criterio ÚNICO del proyecto para "párrafo de título": estilos `Heading*`
    y `Título*`/`Titulo*`/`Ttulo*` (con o sin número). Lo comparten el
    extractor (contextos de cuerpo y carátula), el tokenizer (inferencia de
    tipo del DSL) y el check legacy `secuencia_titulos`, de modo que todos
    hablen del mismo criterio (revisión PR #45, punto 3).

    Args:
        val: Valor del atributo `w:pStyle` del párrafo (puede ser None).

    Returns:
        True si `val` corresponde a un estilo de encabezado; False si es
        None, vacío o un estilo distinto.
    """
    if not val:
        return False
    return HEADING_RE.match(val) is not None


def _texto_normalizado(node) -> str:
    """Texto de un párrafo normalizado: mayúsculas, whitespace colapsado."""
    return re.sub(r"\s+", " ", text_of(node)).upper().strip()


def _para_ancestor(node):
    cur = node
    while cur is not None and cur.tag != W + "p":
        cur = cur.getparent()
    return cur


def _rango_cuerpo(doc) -> tuple[list, int, int]:
    """Índices del rango del cuerpo real: párrafos top-level desde el primer
    heading "Introducción" hasta antes de "Referencias"/"Bibliografía"/"Anexos".

    Si no hay heading "Introducción", el rango cubre todo el documento
    (fallback robusto). Devuelve `(paras, start, end)` sobre
    `//w:body/w:p` (solo párrafos top-level; los de tabla quedan fuera).
    """
    paras = doc.xpath("//w:body/w:p", namespaces=NS)

    def _heading_idx(raw):
        """Índice de los párrafos con estilo de encabezado (Ttulo/Heading)."""
        res = []
        for i, p in enumerate(raw):
            pPr = p.find(W + "pPr")
            st = pPr.find(W + "pStyle") if pPr is not None else None
            val = st.get(W + "val") if st is not None else ""
            if es_heading(val):
                res.append(i)
        return res

    headings = _heading_idx(paras)

    def _timbre(pat, desde=0):
        """Primer heading (>= desde) cuyo texto normalizado matchea `pat`."""
        for i in headings:
            if i >= desde and pat.search(_texto_normalizado(paras[i])):
                return i
        return None

    inicio = _timbre(re.compile(r"^INTRODUCCI"))
    fin = None
    for pat in (re.compile(r"^REFERENCIAS"), re.compile(r"^BIBLIOGRAF"), re.compile(r"^ANEXOS")):
        fin = _timbre(pat, desde=inicio if inicio is not None else 0)
        if fin is not None:
            break

    start = inicio + 1 if inicio is not None else 0
    end = fin if fin is not None else len(paras)
    return paras, start, end


def _cuerpo_paras(doc) -> set:
    """Párrafos del cuerpo real del documento (para reglas de formato).

    El cuerpo empieza en el primer heading "Introducción" y termina antes
    del primer heading "Referencias"/"Bibliografía"/"Anexos". Quedan fuera
    los headings (los títulos de capítulo van centrados y con su propio
    tamaño), los párrafos vacíos (separadores) y los captions de tabla
    "Nota."/"Fuente." (tipografía APA legítima que el manual no prescribe).
    Si el documento no tiene heading "Introducción", todo el documento es
    candidato (fallback robusto).

    Solo se consideran párrafos top-level de `w:body`; los que viven dentro
    de una tabla quedan excluidos por construcción.
    """
    paras, start, end = _rango_cuerpo(doc)
    result = set()
    for i in range(start, end):
        p = paras[i]
        pPr = p.find(W + "pPr")
        st = pPr.find(W + "pStyle") if pPr is not None else None
        val = st.get(W + "val") if st is not None else ""
        if es_heading(val):
            continue
        texto = _texto_normalizado(p)
        if not texto or re.match(r"^(NOTA|FUENTE)[.\s]", texto):
            continue
        result.add(p)
    return result


def _secciones_cuerpo(doc) -> set:
    """Conjunto de `w:sectPr` que rigen el cuerpo real del documento.

    Cada párrafo pertenece a la sección que termina en el primer `w:sectPr`
    en orden de documento con posición mayor o igual a la suya (si el mismo
    párrafo trae un `w:sectPr` en `pPr`, esa es su sección). Devolvemos
    las secciones que gobiernan el rango semántico del cuerpo, para que las
    reglas de márgenes validen las páginas del texto (las que el manual
    regula) y no las secciones landscape de anexos con tablas, que Word
    legitima con los márgenes rotados (bottom↔left).

    Si el rango está vacío o sin párrafos, todo el documento es candidato
    (fallback robusto): `secciones = TODOS los sectPr`.
    """
    paras, start, end = _rango_cuerpo(doc)
    sectprs = doc.xpath("//w:sectPr", namespaces=NS)
    # Orden de documento: lxml mantiene proxies estables para un mismo nodo
    # mientras el root del documento tenga referencias fuertes (misma regla
    # que _paginacion_para), así los elementos sirven como clave de dict.
    rank = {el: i for i, el in enumerate(doc.iter())}

    gobernantes: set = set()
    for p in paras[start:end]:
        for s in sectprs:
            if rank[s] >= rank[p]:
                gobernantes.add(s)
                break

    if not gobernantes:
        return set(sectprs)
    return gobernantes


def _caratula_paras(doc) -> set:
    """Párrafos top-level de la carátula (primera sección del documento).

    La carátula es una unidad estructural que Word delimita con un salto de
    sección (`w:pPr/w:sectPr`): todos los párrafos del body anteriores al
    primer salto pertenecen a ella. Limitando las reglas de carátula a este
    conjunto se evitan falsos positivos por keywords ("universidad",
    "facultad", "trujillo"...) que aparecen además en el cuerpo (handover
    issue #3).

    Si el documento no trae ningún salto de sección (una sola sección), no
    hay forma estructural de delimitar la carátula y se devuelve todo el
    body como candidato (fallback robusto).
    """
    paras = doc.xpath("//w:body/w:p", namespaces=NS)
    limite = len(paras)
    for i, p in enumerate(paras):
        pPr = p.find(W + "pPr")
        if pPr is not None and pPr.find(W + "sectPr") is not None:
            limite = i
            break
    return set(paras[:limite])


@dataclass(frozen=True)
class PaginaFisica:
    """Página asignada a un párrafo y el grado de certeza de esa asignación."""

    numero: int
    certeza: str


def _apagado(el) -> bool:
    """¿El booleano OOXML está desactivado de forma explícita?

    `w:pageBreakBefore w:val="0"` (o `false`/`off`) NO crea un salto. Antes
    se trataba cualquier presencia del nodo como un salto (M3/VA-04).
    """
    val = el.get(W + "val")
    return val is not None and val.strip().lower() in {"0", "false", "off"}


def _salta_pagina_por_seccion(sect) -> bool:
    """¿Este `w:sectPr` obliga a que la sección siguiente empiece en otra página?

    `w:type` vale `nextPage` por defecto. `continuous` y `nextColumn` no
    cambian de página. `evenPage`/`oddPage` sí, aunque pueden dejar una
    página en blanco: el mapa los cuenta como un salto (límite documentado).
    """
    tipo = sect.find(W + "type")
    valor = (tipo.get(W + "val") if tipo is not None else None) or "nextPage"
    return valor.strip().lower() not in {"continuous", "nextcolumn"}


def _parrafo_tiene_contenido(p) -> bool:
    """¿El párrafo puede consumir espacio de la página?

    Un párrafo vacío (solo marcadores de salto o espacios) no aleja al
    siguiente del inicio de página. Se excluye `w:br w:type="page"` porque
    es el salto, no contenido; los demás `w:br` (línea nueva) sí ocupan
    espacio.
    """
    for el in p.iter():
        if el.tag == W + "t":
            if (el.text or "").strip():
                return True
        elif el.tag in (W + "drawing", W + "pict", W + "object", W + "sym", W + "tab"):
            return True
        elif el.tag == W + "br" and el.get(W + "type") != "page":
            return True
    return False


def _paginacion_para(document) -> dict:
    """Calcula el mapa de paginación (párrafo -> `PaginaFisica`).

    Word persiste en el XML cuatro señales de salto de página:

    - ``w:br w:type="page"``: salto explícito del autor (estructural).
    - ``w:pPr/w:pageBreakBefore``: el párrafo arranca en página nueva
      (estructural); ``w:val="0"`` lo desactiva.
    - ``w:pPr/w:sectPr`` con tipo distinto de ``continuous``/``nextColumn``:
      la sección siguiente empieza en otra página (estructural).
    - ``w:lastRenderedPageBreak``: caché del render de Word (estimada).

    Se recorren los párrafos en orden de documento y se procesan los saltos
    en el orden en que aparecen. Un párrafo con `pageBreakBefore` pertenece
    a la página nueva; los saltos internos (`w:br`, `lastRenderedPageBreak`)
    se cuentan todos y avanzan la página del contenido siguiente. Un párrafo
    puede cruzar una página: se le asigna la página donde empieza.

    Cada asignación lleva su grado de certeza:

    - ``comprobada``: el párrafo empieza en un salto estructural (o es el
      inicio del documento). El número absoluto supone que los saltos
      anteriores también están marcados; el límite está documentado.
    - ``estimada``: la página se deduce de la caché de render de Word
      (`lastRenderedPageBreak`), que puede estar desactualizada.
    - ``desconocida``: no hay marcador; el texto pudo fluir a otra página
      sin que el XML lo registre.

    La página 1 es la carátula (aunque el manual indique que no se enumera
    visualmente, se cuenta para el correlativo del resto del documento).
    """
    # El mapa usa como clave el ELEMENTO (proxy lxml) y no `id()`: los
    # proxies se liberan y recrean (su `id()` cambia) si no hay una
    # referencia fuerte, lo que rompería las consultas posteriores.
    paginacion: dict = {}
    pagina = 1
    # El primer párrafo empieza en la página 1: no hay ambigüedad.
    inicio_comprobado = True
    # Si el documento trae la caché de render, Word ya insertó los cortes
    # naturales: ausencia de marcador significa "misma página" (estimada).
    tiene_render = next(document.iter(W + "lastRenderedPageBreak"), None) is not None

    for p in document.xpath("//w:body//w:p", namespaces=NS):
        ppr = p.find(W + "pPr")
        pbb = ppr.find(W + "pageBreakBefore") if ppr is not None else None
        if pbb is not None and not _apagado(pbb):
            # `pageBreakBefore` afecta al PROPIO párrafo (M3/VA-04).
            pagina += 1
            inicio_comprobado = True

        if inicio_comprobado:
            certeza = PAGINA_COMPROBADA
        elif tiene_render:
            certeza = PAGINA_ESTIMADA
        else:
            certeza = PAGINA_DESCONOCIDA
        paginacion[p] = PaginaFisica(pagina, certeza)

        saltos = 0
        saltos_estructurales = 0
        for el in p.iter():
            if el.tag == W + "lastRenderedPageBreak":
                saltos += 1
            elif el.tag == W + "br" and el.get(W + "type") == "page":
                saltos += 1
                saltos_estructurales += 1

        sect = ppr.find(W + "sectPr") if ppr is not None else None
        if sect is not None and _salta_pagina_por_seccion(sect):
            saltos += 1
            saltos_estructurales += 1

        if saltos:
            # Varios saltos en el mismo párrafo cuentan todos: el contenido
            # siguiente puede quedar varias páginas más adelante.
            pagina += saltos
            # El siguiente párrafo empieza en página nueva. Solo es
            # comprobada si todos los saltos fueron estructurales; si alguno
            # vino de la caché de Word, la certeza baja a estimada.
            inicio_comprobado = saltos_estructurales == saltos
        elif not _parrafo_tiene_contenido(p):
            # Párrafo vacío: el siguiente sigue en el inicio de página.
            pass
        else:
            inicio_comprobado = False

    return paginacion


@dataclass
class ExtractedDocx:
    """Árboles XML extraídos + caché XPath + paginación física.

    `headers`/`footers` contienen TODAS las partes del paquete
    (`header1.xml`, `header2.xml`, ...). Los accesores `header`/`footer`
    (propiedades) devuelven la primera parte, por compatibilidad con el
    motor legacy (`checks.py` consulta `part("footer")`).
    """

    document: etree._Element
    headers: list
    footers: list
    footnotes: etree._Element | None
    _cuerpo: set
    # Párrafos de la carátula (primera sección; issue handover #3): las
    # reglas de carátula validan SOLO estos, no keywords repetidas en el cuerpo.
    _caratula: set = field(default_factory=set, repr=False)
    # Secciones que rigen el cuerpo real (issue handover #2): las reglas de
    # márgenes validan solo estas, excluyendo secciones landscape de anexos.
    _secciones_cuerpo: set = field(default_factory=set, repr=False)
    # Caché de consultas XPath (F4): clave (parte, contexto, xpath). Evita
    # re-ejecutar la misma consulta por cada analizador de la regla.
    _cache: dict = field(default_factory=dict, repr=False)
    # Paginación física (ítem 1 de la Fase 2, corregida en M3/VA-04):
    # párrafo -> `PaginaFisica` (número + grado de certeza), calculada a
    # partir de los saltos que Word persiste en el XML.
    _paginacion: dict = field(default_factory=dict, repr=False)

    @property
    def header(self) -> etree._Element | None:
        return self.headers[0] if self.headers else None

    @property
    def footer(self) -> etree._Element | None:
        return self.footers[0] if self.footers else None

    def is_cuerpo(self, node) -> bool:
        return _para_ancestor(node) in self._cuerpo

    def is_caratula(self, node) -> bool:
        """¿El nodo vive en un párrafo de la carátula (primera sección)?"""
        return _para_ancestor(node) in self._caratula

    def _nodo_seccion(self, node):
        """Ancestro `w:sectPr` del nodo (o el mismo si es un sectPr)."""
        cur = node
        while cur is not None and cur.tag != W + "sectPr":
            cur = cur.getparent()
        return cur

    def es_seccion_cuerpo(self, node) -> bool:
        """¿El nodo pertenece a una sección que rige el cuerpo real?"""
        return self._nodo_seccion(node) in self._secciones_cuerpo

    def es_seccion_landscape(self, node) -> bool:
        """¿El `w:pgMar` del nodo vive en una sección landscape?

        Word rota los márgenes en secciones landscape (bottom<->left,
        top<->right): el empaste sigue en el mismo borde físico. Las reglas
        de márgenes normalizan ese valor rotado antes de comparar.

        Detecta landscape por `w:orient="landscape"` y, como fallback, por
        geometría: una página físicamente más ancha que alta es landscape por
        definición. El fallback cubre generadores no-Word (conversiones desde
        PDF) que omiten `w:orient` (revisión PR #45, punto 2).
        """
        s = self._nodo_seccion(node)
        if s is None:
            return False
        sz = s.find(W + "pgSz")
        if sz is None:
            return False
        if sz.get(W + "orient") == "landscape":
            return True
        w = sz.get(W + "w")
        h = sz.get(W + "h")
        if w is None or h is None:
            return False
        try:
            return int(w) > int(h)
        except ValueError:
            return False

    def _pagina_de(self, node) -> PaginaFisica | None:
        """Información de página del párrafo que contiene `node`."""
        if node is None:
            return None
        p = _para_ancestor(node)
        return self._paginacion.get(p)

    def pagina_de(self, node) -> int | None:
        """Número físico de página de un párrafo (None si no es un párrafo
        del cuerpo del documento). Es la forma de "devolver también el
        número de página real" pedida en el ítem 1 de la Fase 2.

        El número es la mejor estimación disponible; para saber si está
        comprobado o solo estimado, usar `certeza_pagina_de()`.
        """
        info = self._pagina_de(node)
        return info.numero if info is not None else None

    def certeza_pagina_de(self, node) -> str | None:
        """Grado de certeza de la página de un párrafo (M3/VA-04).

        Devuelve ``PAGINA_COMPROBADA``, ``PAGINA_ESTIMADA`` o
        ``PAGINA_DESCONOCIDA``; ``None`` si el nodo no es un párrafo del
        cuerpo. La distinción evita afirmar una página cuando el XML no la
        respalda (sin marcadores o solo con la caché de render de Word).
        """
        info = self._pagina_de(node)
        return info.certeza if info is not None else None

    def pagina_confirmada_de(self, node) -> bool | None:
        """¿La página del párrafo está respaldada por un salto estructural?"""
        certeza = self.certeza_pagina_de(node)
        if certeza is None:
            return None
        return certeza == PAGINA_COMPROBADA

    def part(self, name: str) -> etree._Element | None:
        return {
            "document": self.document,
            "footer": self.footer,
            "header": self.header,
        }.get(name)

    def _arboles(self, parte: str) -> list:
        return {
            "document": [self.document],
            "footer": self.footers,
            "header": self.headers,
        }.get(parte, [])

    def xpath(self, parte: str, xpath_expr: str, contexto: str = "todos") -> list:
        """Consulta XPath con cache por (parte, contexto, xpath).

        Es el punto único por el que los analizadores consultan los árboles:
        dos secciones con el mismo XPath comparten el resultado. Para encabe-
        zados/pies consulta TODAS las partes del tipo (`header*.xml`,
        `footer*.xml`) y combina los resultados. Con `contexto == "cuerpo"`
        se filtra por los párrafos del cuerpo real del documento; con
        `contexto == "seccion_cuerpo"`, por las secciones que rigen ese
        cuerpo (márgenes, papel), lo que deja fuera las secciones landscape
        de anexos; con `contexto == "caratula"`, por los párrafos de la
        primera sección (carátula).
        """
        clave = (parte, contexto, xpath_expr)
        if clave in self._cache:
            return self._cache[clave]
        arboles = self._arboles(parte)
        if not arboles:
            raise ValueError(f"parte '{parte}' no disponible en este archivo")
        nodos = []
        for tree in arboles:
            nodos.extend(tree.xpath(xpath_expr, namespaces=NS))
        if contexto == "cuerpo":
            nodos = [n for n in nodos if self.is_cuerpo(n)]
        if contexto == "seccion_cuerpo":
            nodos = [n for n in nodos if self.es_seccion_cuerpo(n)]
        if contexto == "caratula":
            nodos = [n for n in nodos if self.is_caratula(n)]
        self._cache[clave] = nodos
        return nodos


def extract(docx_path: str) -> ExtractedDocx:
    """Extrae y normaliza un DOCX para el motor de reglas.

    Abre el paquete OPC (zip) del documento y devuelve sus partes XML
    relevantes ya parseadas, listas para que ``checks.run_check`` las
    consulte. Además de los árboles XML, calcula la paginación física real
    (párrafo -> página) a partir de los saltos de página que Word persiste
    en el XML, para que el motor pueda correlacionar texto con número de
    página sin renderizar el documento.

    La extracción es robusta: soporta documentos con y sin heading
    "Introducción", maneja carátulas y secciones, y descarta párrafos
    vacíos, headings y captions de tabla ("Nota."/"Fuente.") que el manual
    no prescribe.

    Args:
        docx_path: Ruta al archivo .docx a extraer.

    Returns:
        Un ``ExtractedDocx`` con los árboles XML, la caché de consultas
        XPath, la paginación física y los metadatos del documento.

    Raises:
        zipfile.BadZipFile: Si el archivo no es un ZIP válido o una parte
            supera el límite de descompresión (posible zip bomb).
        KeyError: Si falta document.xml u otra parte esencial del DOCX.
    """
    with zipfile.ZipFile(docx_path) as z:
        names = z.namelist()
        document = etree.fromstring(_leer_parte(z, "word/document.xml"))
        headers = [
            etree.fromstring(_leer_parte(z, n))
            for n in sorted(x for x in names if x.startswith("word/header") and x.endswith(".xml"))
        ]
        footers = [
            etree.fromstring(_leer_parte(z, n))
            for n in sorted(x for x in names if x.startswith("word/footer") and x.endswith(".xml"))
        ]
        footnotes_xml = (
            _leer_parte(z, "word/footnotes.xml") if "word/footnotes.xml" in names else None
        )
        footnotes = (
            etree.fromstring(footnotes_xml) if footnotes_xml and len(footnotes_xml) > 0 else None
        )

    return ExtractedDocx(
        document=document,
        headers=headers,
        footers=footers,
        footnotes=footnotes,
        _cuerpo=_cuerpo_paras(document),
        _caratula=_caratula_paras(document),
        _secciones_cuerpo=_secciones_cuerpo(document),
        _paginacion=_paginacion_para(document),
    )
