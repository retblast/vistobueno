"""Márgenes en secciones landscape (handover issue #2).

Word rota los márgenes en secciones landscape (bottom<->left, top<->right)
para que el borde de empaste siga en el mismo lado físico. Las reglas
`margen_*` validan SOLO las secciones que rigen el cuerpo
(`contexto: seccion_cuerpo`) y normalizan esa rotación: una tabla ancha
legítima en landscape (p. ej. OPERACIONALIZACIÓN) ya no genera falsos
positivos, mientras que una sección del cuerpo con márgenes realmente mal
configurados sigue fallando.

Artificio del documento de prueba, en orden de documento:
    portada ... <sectPr cover>   (sección NO-cuerpo, márgenes rotos a posta)
    INTRODUCCIÓN + prosa         (cuerpo)
    ... <sectPr portrait>        (sección del cuerpo, márgenes conformes)
    OPERACIONALIZACIÓN (tabla ancha) ... <sectPr landscape>   (rotada)
    prosa ... REFERENCIAS        (cuerpo)
    <w:body/w:sectPr>            (sección final del cuerpo, conformes)
"""

import os
import tempfile
import zipfile
from pathlib import Path

from validator.engine import load_rules, validate_docx
from validator.extractor import NS, W, extract

RAIZ = Path(__file__).resolve().parent.parent
WNS = NS["w"]
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

OK = 'w:top="1418" w:bottom="1418" w:left="1701" w:right="1418"'
BAD = 'w:top="1418" w:bottom="1300" w:left="1701" w:right="1418"'
MARG_LAND = 'w:top="1418" w:bottom="1701" w:left="1418" w:right="1418"'


def _p(texto: str, ppr: str = "") -> str:
    ppr_xml = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    return f'<w:p>{ppr_xml}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _h(texto: str) -> str:
    return _p(texto, '<w:pStyle w:val="Ttulo1"/>')


def _sect_break(marg: str, landscape: bool = False) -> str:
    sz = (
        '<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
        if landscape
        else '<w:pgSz w:w="11906" w:h="16838"/>'
    )
    return _p(" ", f"<w:sectPr>{sz}<w:pgMar {marg}/></w:sectPr>")


def _docx(cover_marg: str, body_marg: str, body_land_marg: str, final_marg: str) -> str:
    body = (
        _p("UNIVERSIDAD NACIONAL DE TRUJILLO")
        + _sect_break(cover_marg)
        + _h("INTRODUCCIÓN")
        + _p("La motricidad fina se desarrolla con estrategias lúdicas.")
        + _sect_break(body_marg)
        + _p("OPERACIONALIZACIÓN DE LAS VARIABLES")
        + _sect_break(body_land_marg, landscape=True)
        + _p("La tabla ocupa una página completa en horizontal.")
        + _h("REFERENCIAS")
        + f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar {final_marg}/></w:sectPr>'
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}" xmlns:r="{RNS}"><w:body>{body}</w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", xml)
    return path


RULES = load_rules(str(RAIZ / "reglas_unt.yaml"))


def _margen(path: str, rid: str):
    for r in validate_docx(path, RULES):
        if r.rule_id == rid:
            return r
    return None


def test_landscape_legitimo_en_cuerpo_no_falla():
    """Sección landscape legítima dentro del cuerpo: márgenes pasan.

    La sección landscape rota bottom<->left (1701/1418). Sin normalización
    `margen_inferior` vería bottom=1701 y `margen_izquierdo` left=1418:
    ambos serían falsos rojos. La portada (no-cuerpo) tiene márgenes rotos
    a posta y se ignora.
    """
    path = _docx(BAD, OK, MARG_LAND, OK)
    try:
        assert _margen(path, "margen_superior").passed, "margen_superior"
        assert _margen(path, "margen_inferior").passed, "landscape bottom rotado"
        assert _margen(path, "margen_derecho").passed, "margen_derecho"
        assert _margen(path, "margen_izquierdo").passed, "landscape left rotado"
    finally:
        os.unlink(path)


def test_seccion_del_cuerpo_con_margen_mal_falla():
    """La sección portrait del cuerpo con margen inferior mal: falla."""
    path = _docx(BAD, BAD, MARG_LAND, OK)
    try:
        assert not _margen(path, "margen_inferior").passed, "bottom del cuerpo mal"
        assert _margen(path, "margen_izquierdo").passed, "izquierdo sigue conforme"
    finally:
        os.unlink(path)


def test_evidencia_de_la_rotacion():
    """La sección landscape guarda bottom=1701 (y left=1418): el swap es
    necesario y el contexto `seccion_cuerpo` si la incluye."""
    path = _docx(OK, OK, MARG_LAND, OK)
    try:
        ex = extract(path)
        doc = ex.document
        pgmars = doc.xpath("//w:sectPr/w:pgMar", namespaces=NS)
        landscape = [n for n in pgmars if ex.es_seccion_landscape(n)]
        assert landscape, "debe existir una sección landscape"
        assert landscape[0].get(W + "bottom") == "1701", "bottom roto en OOXML"
        assert landscape[0].get(W + "left") == "1418", "left roto en OOXML"
        nodos = ex.xpath("document", "(//w:sectPr)/w:pgMar", "seccion_cuerpo")
        assert nodos, "el cuerpo debe tener al menos una sección"
        assert any(ex.es_seccion_landscape(n) for n in nodos), "la landscape es del cuerpo"
    finally:
        os.unlink(path)
