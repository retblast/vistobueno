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


def text_of(node) -> str:
    """Concatena el texto de todos los w:t descendientes de un nodo."""
    return "".join(t.text or "" for t in node.iter(W + "t"))


HEADING_RE = re.compile(r"^(?:Heading|T[ií]tulo|Ttulo)\d*$", re.I)


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
            if HEADING_RE.match(val or ""):
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
        if HEADING_RE.match(val or ""):
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


def _paginacion_para(document) -> dict[int, int]:
    """Calcula el mapa de paginación real (párrafo -> página física).

    Word persiste en el XML tres marcadores fiables de saltos de página:
    ``w:lastRenderedPageBreak`` (insertado al guardar un documento renderizado),
    ``w:br w:type="page"`` (salto explícito) y la propiedad de párrafo
    ``w:pPr/w:pageBreakBefore`` (el párrafo arranca en página nueva).
    Recorremos los párrafos en orden de documento y correlacionamos cada uno
    con su número físico de página sin necesidad de renderizar el documento.

    La página 1 es la carátula (aunque el manual indique que no se enumera
    visualmente, se cuenta para el correlativo del resto del documento).
    """
    # El mapa usa como clave el ELEMENTO (proxy lxml) y no `id()`: los
    # proxies se liberan y recrean (su `id()` cambia) si no hay una
    # referencia fuerte, lo que rompería las consultas posteriores.
    paginacion: dict = {}
    pagina = 1

    for p in document.xpath("//w:body//w:p", namespaces=NS):
        tiene_salto = (
            p.find(f".//{W}lastRenderedPageBreak", namespaces=NS) is not None
            or p.find(f".//{W}br[@w:type='page']", namespaces=NS) is not None
            or p.find(f"{W}pPr/{W}pageBreakBefore", namespaces=NS) is not None
        )
        paginacion[p] = pagina
        if tiene_salto:
            pagina += 1

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
    # Paginación real (ítem 1 de la Fase 2): párrafo -> número físico de
    # página, calculada a partir de los saltos que Word persiste en el XML.
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
        """
        s = self._nodo_seccion(node)
        if s is None:
            return False
        sz = s.find(W + "pgSz")
        return sz is not None and sz.get(W + "orient") == "landscape"

    def pagina_de(self, node) -> int | None:
        """Número físico de página de un párrafo (None si no es un párrafo
        del cuerpo del documento). Es la forma de "devolver también el
        número de página real" pedida en el ítem 1 de la Fase 2."""
        if node is None:
            return None
        p = _para_ancestor(node)
        return self._paginacion.get(p)

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
    """Abre un .docx (zip OPC) y devuelve sus partes XML relevantes ya
    parseadas, listas para que checks.run_check las consulte.

    Además de los árboles XML, calcula la paginación física real (párrafo ->
    página) a partir de los saltos de página que Word persiste en el XML,
    para que el motor pueda correlacionar texto con número de página sin
    renderizar el documento.
    """
    with zipfile.ZipFile(docx_path) as z:
        names = z.namelist()
        document = etree.fromstring(z.read("word/document.xml"))
        headers = [
            etree.fromstring(z.read(n))
            for n in sorted(x for x in names if x.startswith("word/header") and x.endswith(".xml"))
        ]
        footers = [
            etree.fromstring(z.read(n))
            for n in sorted(x for x in names if x.startswith("word/footer") and x.endswith(".xml"))
        ]
        footnotes = (
            etree.fromstring(z.read("word/footnotes.xml"))
            if "word/footnotes.xml" in names
            else None
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
