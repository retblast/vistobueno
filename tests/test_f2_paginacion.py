"""Tests de la paginación física real (F2 ítem 1, corregida en M3/VA-04).

Cubre:
- `_paginacion_para`: mapa párrafo -> página procesando en orden los saltos
  explícitos (`w:br w:type="page"`, `w:pageBreakBefore`, `w:sectPr` no
  continuo) y la caché de render (`w:lastRenderedPageBreak`). `pageBreakBefore`
  afecta al propio párrafo, `w:val="0"` no crea salto y varios saltos en un
  mismo párrafo cuentan todos.
- `ExtractedDocx.pagina_de`, `certeza_pagina_de` y `pagina_confirmada_de`:
  la página puede ser comprobada (salto estructural), estimada (caché de
  render de Word) o desconocida (sin marcadores).
- `AnalizadorPaginacion` (`paginacion` / `paginas_distintas`): pasa solo si
  los objetivos caen en páginas físicas distintas; falla con
  `paginas_repetidas`. Si alguna sección objetivo no es identificable, o si
  la página es desconocida, pasa como n/a (la regla solo juzga paginación,
  no presencia ni inventa páginas).
- Regla `indice_paginas_separadas` end-to-end contra `reglas_unt.yaml`
  (documento base separado / mutación agrupada / índice renombrado).
- Linter y compilador DSL aceptan la sección `paginacion`.

Uso:
    pytest tests/test_f2_paginacion.py -v
"""

import tempfile
import zipfile
from pathlib import Path

from docx_factory import (
    aplicar_mutacion,
    compilar_docx,
    configuracion_base,
)

from validator.compilador import SECCIONES_ANALIZADOR, CompilerDSL
from validator.dsl_check import linter
from validator.engine import load_rules, validate_docx
from validator.extractor import NS, extract

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

RAIZ = Path(__file__).resolve().parent.parent
YAML_PATH = RAIZ / "reglas_unt.yaml"

_MAYUS = "ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ"
_MINUS = "abcdefghijklmnopqrstuvwxyzáéíóúñü"


def _xpath_que_contiene(termino: str) -> str:
    return (
        "//w:body//w:p[contains(translate(normalize-space(.), "
        f'"{_MAYUS}", "{_MINUS}"), "{termino}")]'
    )


_XPATHS_INDICES = [_xpath_que_contiene(t) for t in ("contenidos", "tablas", "figuras")]


def _para(texto: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _p_break() -> str:
    """Párrafo con salto renderizado por Word (w:lastRenderedPageBreak)."""
    return "<w:p><w:r><w:lastRenderedPageBreak/></w:r></w:p>"


def _p_br_page() -> str:
    """Párrafo con salto de página explícito (w:br w:type=\"page\")."""
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def _p_break_before(texto: str) -> str:
    """Párrafo que arranca en página nueva (w:pageBreakBefore en w:pPr)."""
    return (
        "<w:p><w:pPr><w:pageBreakBefore/></w:pPr>"
        f'<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'
    )


def _make_docx(paras: list) -> str:
    """Escribe un DOCX mínimo en un archivo temporal y devuelve su ruta."""
    body = "".join(paras)
    body += '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{body}</w:body></w:document>'
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
    return path


def _regla_paginacion(xpaths: list) -> dict:
    """Regla DSL `paginacion` autocontenida (para un DOCX mínimo)."""
    return {
        "id": "paginacion_test",
        "tipo": "paginacion",
        "descripcion": "Los índices deben presentarse en páginas separadas",
        "valor_esperado": "cada índice en una página distinta",
        "severidad": "warning",
        "ubicacion": "Sección Índice",
        "fuente": "MANUAL.docx",
        "cita": '"cada índice debe presentarse en páginas separadas"',
        "paginacion": {"comparacion": "paginas_distintas", "xpaths": xpaths},
    }


# ---------------------------------------------------------------------------
# Mapa de paginación física (_paginacion_para / ExtractedDocx)
# ---------------------------------------------------------------------------


def _extraer_factory(cfg):
    path = compilar_docx(cfg)
    try:
        return extract(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_paginacion_es_monotona_y_pagina_inicial():
    ext = _extraer_factory(configuracion_base())
    paras = ext.document.xpath("//w:body//w:p", namespaces=NS)
    pags = [ext.pagina_de(p) for p in paras]
    assert pags[0] == 1
    assert all(isinstance(p, int) for p in pags)
    assert all(a <= b for a, b in zip(pags, pags[1:], strict=False))


def test_mapa_de_saltos_renderizados_y_explicitos():
    # Word: lastRenderedPageBreak (párrafo que cierra la página N) y
    # w:br w:type="page" (salto explícito). El párrafo con salto SÍ queda en
    # la página actual; el contenido siguiente pasa a la siguiente.
    path = _make_docx([_para("A"), _p_break(), _para("B"), _p_br_page(), _para("C")])
    try:
        ext = extract(path)
    finally:
        Path(path).unlink(missing_ok=True)
    paras = ext.document.xpath("//w:body//w:p", namespaces=NS)
    assert [ext.pagina_de(p) for p in paras] == [1, 1, 2, 2, 3]


def test_pagina_de_no_para_es_none():
    ext = _extraer_factory(configuracion_base())
    assert ext.pagina_de(None) is None
    assert ext.pagina_de(ext.document) is None


def test_mapa_de_salto_con_page_break_before():
    # w:pageBreakBefore (propiedad de w:pPr) afecta al PROPIO párrafo: el
    # párrafo que lo declara arranca en página nueva (M3/VA-04). Antes se le
    # asignaba la página anterior y el salto se cobraba recién en el
    # siguiente.
    path = _make_docx([_para("A"), _p_break_before("SECCION"), _para("B")])
    try:
        ext = extract(path)
    finally:
        Path(path).unlink(missing_ok=True)
    paras = ext.document.xpath("//w:body//w:p", namespaces=NS)
    assert [ext.pagina_de(p) for p in paras] == [1, 2, 2]


# ---------------------------------------------------------------------------
# M3/VA-04: orden y valor de los saltos
# ---------------------------------------------------------------------------


def _paginas(paras: list) -> list[int | None]:
    path = _make_docx(paras)
    try:
        ext = extract(path)
    finally:
        Path(path).unlink(missing_ok=True)
    return [ext.pagina_de(p) for p in ext.document.xpath("//w:body//w:p", namespaces=NS)]


def test_break_before_afecta_al_propio_parrafo():
    # Aceptación M3: [1,2] con break-before en el segundo párrafo.
    assert _paginas([_para("A"), _p_break_before("B")]) == [1, 2]


def test_break_before_desactivado_no_crea_salto():
    # Aceptación M3: w:val="0" desactiva el salto; ambos quedan en página 1.
    paras = [
        _para("A"),
        '<w:p><w:pPr><w:pageBreakBefore w:val="0"/></w:pPr>'
        '<w:r><w:t xml:space="preserve">B</w:t></w:r></w:p>',
    ]
    assert _paginas(paras) == [1, 1]


def test_break_before_off_tampoco_crea_salto():
    paras = [
        _para("A"),
        '<w:p><w:pPr><w:pageBreakBefore w:val="off"/></w:pPr>'
        '<w:r><w:t xml:space="preserve">B</w:t></w:r></w:p>',
    ]
    assert _paginas(paras) == [1, 1]


def test_dos_saltos_en_el_mismo_parrafo():
    # Aceptación M3: [1,3] con dos saltos en el primero. Un párrafo puede
    # contener varios w:br y todos avanzan la página.
    paras = [
        '<w:p><w:r><w:br w:type="page"/><w:br w:type="page"/></w:r></w:p>',
        _para("B"),
    ]
    assert _paginas(paras) == [1, 3]


def test_salto_de_seccion_next_page_avanza_la_pagina():
    # w:sectPr en pPr cierra la sección; nextPage (el valor por defecto)
    # hace que la sección siguiente empiece en otra página.
    paras = [
        _para("INDICE DE CONTENIDOS"),
        '<w:p><w:pPr><w:sectPr><w:type w:val="nextPage"/></w:sectPr></w:pPr>'
        '<w:r><w:t xml:space="preserve"> </w:t></w:r></w:p>',
        _para("INDICE DE TABLAS"),
    ]
    assert _paginas(paras) == [1, 1, 2]


def test_salto_de_seccion_continuo_no_avanza_la_pagina():
    paras = [
        _para("INDICE DE CONTENIDOS"),
        '<w:p><w:pPr><w:sectPr><w:type w:val="continuous"/></w:sectPr></w:pPr>'
        '<w:r><w:t xml:space="preserve"> </w:t></w:r></w:p>',
        _para("INDICE DE TABLAS"),
    ]
    assert _paginas(paras) == [1, 1, 1]


def test_parrafo_que_cruza_pagina_conserva_la_pagina_de_inicio():
    # Un párrafo con texto, un salto y más texto cruza la página: se le
    # asigna la página donde empieza y el siguiente párrafo pasa a la nueva.
    paras = [
        '<w:p><w:r><w:t xml:space="preserve">Antes</w:t></w:r>'
        "<w:r><w:lastRenderedPageBreak/></w:r>"
        '<w:r><w:t xml:space="preserve">Después</w:t></w:r></w:p>',
        _para("Siguiente"),
    ]
    assert _paginas(paras) == [1, 2]


def test_sin_marcadores_la_pagina_es_desconocida():
    # Sin marcadores no se puede afirmar la página: la certeza lo declara
    # en vez de inventar "página 1" para todo.
    path = _make_docx([_para("A"), _para("B"), _para("C")])
    try:
        ext = extract(path)
        paras = ext.document.xpath("//w:body//w:p", namespaces=NS)
        certezas = [ext.certeza_pagina_de(p) for p in paras]
        confirmadas = [ext.pagina_confirmada_de(p) for p in paras]
    finally:
        Path(path).unlink(missing_ok=True)
    # El primero empieza el documento (página 1 comprobada); el resto pudo
    # haber fluido a otra página sin marcador.
    assert certezas[0] == "comprobada"
    assert certezas[1:] == ["desconocida", "desconocida"]
    assert confirmadas == [True, False, False]


def test_salto_explicito_es_comprobado_y_render_es_estimado():
    path = _make_docx([_para("A"), _p_br_page(), _para("B"), _p_break(), _para("C")])
    try:
        ext = extract(path)
        paras = ext.document.xpath("//w:body//w:p", namespaces=NS)
        certezas = [ext.certeza_pagina_de(p) for p in paras]
    finally:
        Path(path).unlink(missing_ok=True)
    # B empieza tras un w:br explícito (comprobada); C tras un
    # lastRenderedPageBreak (estimada).
    assert certezas[0] == "comprobada"
    assert certezas[2] == "comprobada"
    assert certezas[4] == "estimada"


def test_certeza_de_nodo_que_no_es_parrafo_es_none():
    path = _make_docx([_para("A")])
    try:
        ext = extract(path)
        assert ext.certeza_pagina_de(None) is None
        assert ext.certeza_pagina_de(ext.document) is None
        assert ext.pagina_confirmada_de(None) is None
    finally:
        Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AnalizadorPaginacion: paginas_distintas
# ---------------------------------------------------------------------------


def _analizador_paginas(paras: list):
    """Compila una regla `paginacion` y devuelve su AnalizadorPaginacion."""
    regla = _regla_paginacion(_XPATHS_INDICES)
    compilada = CompilerDSL().compilar({"reglas": [regla]})[0]
    path = _make_docx(paras)
    try:
        extracted = extract(path)
    finally:
        Path(path).unlink(missing_ok=True)
    return compilada.analizadores[0], extracted


def _validar_una(paras: list, xpaths: list):
    path = _make_docx(paras)
    try:
        return validate_docx(path, {"reglas": [_regla_paginacion(xpaths)]})[0]
    finally:
        Path(path).unlink(missing_ok=True)


def test_paginas_distintas_pasa():
    an, extracted = _analizador_paginas(
        [
            _p_break(),
            _para("INDICE DE CONTENIDOS"),
            _p_break(),
            _para("INDICE DE TABLAS"),
            _p_break(),
            _para("INDICE DE FIGURAS"),
        ]
    )
    ok, detalle = an.analizar(extracted)
    assert ok
    assert "paginas_distintas" in detalle
    # End-to-end: la regla pasa (found queda en "cumple", por convención).
    r = _validar_una(
        [
            _p_break(),
            _para("INDICE DE CONTENIDOS"),
            _p_break(),
            _para("INDICE DE TABLAS"),
            _p_break(),
            _para("INDICE DE FIGURAS"),
        ],
        _XPATHS_INDICES,
    )
    assert r.passed


def test_paginas_repetidas_falla():
    # Sin salto entre CONTENIDOS y TABLAS quedan en la misma página.
    r = _validar_una(
        [
            _p_break(),
            _para("INDICE DE CONTENIDOS"),
            _para("INDICE DE TABLAS"),
            _p_break(),
            _para("INDICE DE FIGURAS"),
        ],
        _XPATHS_INDICES,
    )
    assert not r.passed
    assert "paginas_repetidas" in r.found


def test_sin_marcadores_no_se_inventa_paginas_repetidas():
    """Sin saltos ni caché de render la regla pasa como n/a (M3/VA-04).

    Antes todos los párrafos recibían la página 1 y la regla fallaba con
    `paginas_repetidas` aunque el XML no probara nada.
    """
    an, extracted = _analizador_paginas(
        [
            _para("INDICE DE CONTENIDOS"),
            _para("INDICE DE TABLAS"),
            _para("INDICE DE FIGURAS"),
        ]
    )
    ok, detalle = an.analizar(extracted)
    assert ok
    assert "paginas_no_verificables" in detalle
    assert "n/a" in detalle

    r = _validar_una(
        [
            _para("INDICE DE CONTENIDOS"),
            _para("INDICE DE TABLAS"),
            _para("INDICE DE FIGURAS"),
        ],
        _XPATHS_INDICES,
    )
    assert r.passed
    assert "paginas_repetidas" not in r.found


def test_paginas_estimadas_se_declaran_en_el_detalle():
    """Con caché de render la comparación es posible, pero se declara."""
    an, extracted = _analizador_paginas(
        [
            _p_break(),
            _para("INDICE DE CONTENIDOS"),
            _p_break(),
            _para("INDICE DE TABLAS"),
            _p_break(),
            _para("INDICE DE FIGURAS"),
        ]
    )
    ok, detalle = an.analizar(extracted)
    assert ok
    assert "estimadas" in detalle
    assert "paginas_distintas" in detalle


def test_paginas_distintas_solo_con_page_break_before():
    # Límites de sección del índice marcados SOLO con w:pageBreakBefore (sin
    # saltos renderizados ni explícitos): no deben colapsar a
    # paginas_repetidas (nit de la revisión PR #28).
    an, extracted = _analizador_paginas(
        [
            _p_break_before("INDICE DE CONTENIDOS"),
            _p_break_before("INDICE DE TABLAS"),
            _p_break_before("INDICE DE FIGURAS"),
        ]
    )
    ok, detalle = an.analizar(extracted)
    assert ok
    assert "paginas_distintas" in detalle
    r = _validar_una(
        [
            _p_break_before("INDICE DE CONTENIDOS"),
            _p_break_before("INDICE DE TABLAS"),
            _p_break_before("INDICE DE FIGURAS"),
        ],
        _XPATHS_INDICES,
    )
    assert r.passed
    assert "repetidas" not in r.found


def test_no_encontrado_es_no_aplica():
    # Falta el índice de tablas: la regla solo juzga paginación, no
    # presencia de secciones, así que pasa como n/a (sin falso positivo).
    r = _validar_una(
        [_p_break(), _para("INDICE DE CONTENIDOS"), _para("INDICE DE FIGURAS")],
        _XPATHS_INDICES,
    )
    assert r.passed


def test_sin_indices_no_aplica_pasa():
    # Ninguna sección objetivo localizable (las plantillas usan un "Índice"
    # genérico dentro de sdtContent que el xpath no matchea): la regla no
    # produce falso positivo y pasa como n/a (ver revisión técnica PR #28).
    an, extracted = _analizador_paginas(
        [_p_break(), _para("ÍNDICE GENERAL"), _para("CUERPO DE LA TESIS")]
    )
    ok, detalle = an.analizar(extracted)
    assert ok
    assert "n/a" in detalle
    r = _validar_una(
        [_p_break(), _para("ÍNDICE GENERAL"), _para("CUERPO DE LA TESIS")],
        _XPATHS_INDICES,
    )
    assert r.passed


# ---------------------------------------------------------------------------
# Regla indice_paginas_separadas end-to-end (reglas_unt.yaml + factory)
# ---------------------------------------------------------------------------


def _resultado_indice(cfg):
    rules = load_rules(str(YAML_PATH))
    path = compilar_docx(cfg)
    try:
        res = validate_docx(path, rules)
    finally:
        Path(path).unlink(missing_ok=True)
    return next(r for r in res if r.rule_id == "indice_paginas_separadas")


def test_indice_paginas_separadas_base_pasa():
    r = _resultado_indice(configuracion_base())
    assert r.passed
    assert r.found == "cumple"


def test_indice_paginas_separadas_mutacion_falla():
    r = _resultado_indice(aplicar_mutacion("indice_paginas_separadas", configuracion_base()))
    assert not r.passed
    assert "paginas_repetidas" in r.found


def test_indice_paginas_separadas_contenidos_renombrado_falla():
    r = _resultado_indice(aplicar_mutacion("indice_subdivisiones", configuracion_base()))
    assert not r.passed
    assert "paginas_repetidas" in r.found


# ---------------------------------------------------------------------------
# Sección DSL `paginacion` aceptada por linter y compilador
# ---------------------------------------------------------------------------


def test_paginacion_es_seccion_dsl_valida():
    regla = _regla_paginacion(_XPATHS_INDICES)
    assert "paginacion" in SECCIONES_ANALIZADOR
    assert linter({"reglas": [regla]}) == []
    compiladas = CompilerDSL().compilar({"reglas": [regla]})
    assert len(compiladas) == 1
    assert compiladas[0].rule["id"] == "paginacion_test"
    assert compiladas[0].analizadores[0].__class__.__name__ == "AnalizadorPaginacion"


# ---------------------------------------------------------------------------
# Enriquecimiento de `location` con la página física (ítem 1, bloque A)
# ---------------------------------------------------------------------------


def _resultado_dsl(cfg, rule_id):
    rules = load_rules(str(YAML_PATH))
    path = compilar_docx(cfg)
    try:
        res = validate_docx(path, rules)
    finally:
        Path(path).unlink(missing_ok=True)
    return next(r for r in res if r.rule_id == rule_id)


def test_regla_fallida_enriquece_location_con_pagina():
    # sangria_parrafo falla (firstLine=0); su primera línea del cuerpo cae en
    # la página 4 del DOCX sintético (3 saltos previos: contenido, tablas y
    # figuras). La página viene de la caché de render de Word, así que el
    # sufijo la declara estimada (M3/VA-04).
    cfg = aplicar_mutacion("sangria_parrafo", configuracion_base())
    r = _resultado_dsl(cfg, "sangria_parrafo")
    assert not r.passed
    assert r.location is not None
    assert r.location == 'Sección "Formato general" (párr. 141); página 4 (estimada)'


def test_regla_cumplida_no_altera_location():
    # Regla cumplida: la ubicación queda tal cual (sin sufijo de página).
    r = _resultado_dsl(configuracion_base(), "sangria_parrafo")
    assert r.passed
    assert r.location == 'Sección "Formato general" (párr. 141)'


def test_pagina_desconocida_no_se_anexa_a_la_location():
    """Sin marcadores no se inventa una página en la ubicación (M3/VA-04)."""
    regla = {
        "id": "ubicacion_sin_pagina",
        "tipo": "atributo_xml",
        "descripcion": "Atributo de prueba",
        "valor_esperado": "otro",
        "severidad": "error",
        "ubicacion": "Cuerpo",
        "fuente": "MANUAL.docx",
        "cita": '"cita"',
        "atributo_xml": {
            "parte": "document",
            "contexto": "todos",
            # Segundo párrafo: no arranca página ni hay marcadores.
            "xpath": "//w:body/w:p[2]/w:r/w:t",
            "atributo": "@xml:space",
            "comparacion": "eq",
            "esperado": "default",
        },
    }
    path = _make_docx([_para("A"), _para("B")])
    try:
        r = validate_docx(path, {"reglas": [regla]})[0]
    finally:
        Path(path).unlink(missing_ok=True)
    assert not r.passed
    assert r.location == "Cuerpo"
