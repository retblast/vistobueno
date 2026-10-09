"""Carátula: contexto `caratula` + título por posición (handover #3 y #4).

- **Issue #3** `alineacion_caratula_todos_elementos`: las keywords
  ('universidad', 'facultad', 'trujillo'...) podían matchear párrafos del
  cuerpo (justificados, jc=both) y `all_eq` esperaba center → falso rojo.
  Con `contexto: caratula` la regla solo mira la primera sección.
- **Issue #4** `caratula_titulo_*`: el XPath buscaba el placeholder
  "título del trabajo" de las plantillas; una tesis real no lo contiene y la
  regla moría con `@w:val=[]`. Ahora se localiza el título como el primer
  párrafo no vacío tras "ESCUELA PROFESIONAL" que no repite universidad/
  facultad/escuela/pará-optar/tesis (perfil fijo del manual).
"""

import os
import tempfile
import zipfile
from pathlib import Path

from validator.engine import load_rules, validate_docx
from validator.extractor import NS

RAIZ = Path(__file__).resolve().parent.parent
WNS = NS["w"]
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

OK = 'w:top="1418" w:bottom="1418" w:left="1701" w:right="1418"'


def _p(texto: str, jc: str = "center", bold: bool = False, sz: str = "") -> str:
    rpr = ""
    if bold:
        rpr += "<w:b/>"
    if sz:
        rpr += f'<w:sz w:val="{sz}"/>'
    rpr_xml = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (
        f'<w:p><w:pPr><w:jc w:val="{jc}"/></w:pPr>'
        f'<w:r>{rpr_xml}<w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'
    )


def _h(texto: str) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="Ttulo1"/></w:pPr><w:r><w:t>{texto}</w:t></w:r></w:p>'


def _sect_break() -> str:
    return (
        f'<w:p><w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        f"<w:pgMar {OK}/></w:sectPr></w:pPr><w:r><w:t> </w:t></w:r></w:p>"
    )


def _docx(cuerpo_both: bool, titulo_real: bool, jc_trujillo: str = "center") -> str:
    titulo = (
        "Taller de dramatización de títeres para mejorar la identidad cultural"
        if titulo_real
        else "Título del trabajo: con altas y bajas, según corresponda"
    )
    jc_cuerpo = "both" if cuerpo_both else "center"
    cover = (
        _p("UNIVERSIDAD NACIONAL DE TRUJILLO", bold=True, sz="36")
        + _p("FACULTAD EDUCACIÓN Y CIENCIAS DE LA COMUNICACIÓN", bold=True, sz="26")
        + _p("ESCUELA PROFESIONAL DE EDUCACIÓN PRIMARIA", bold=True, sz="26")
        + _p(titulo, bold=True, sz="26")
        + _p(
            "Para optar el Título Profesional de Licenciado en Educación Primaria",
            bold=True,
            sz="24",
        )
        + _p("AUTORES:", bold=True)
        + _p("Br. Morales Saldaña, Victor Alberto")
        + _p("ASESORA:", bold=True)
        + _p("Dra. Vásquez Mondragón, Cecilia Del Pilar", bold=True)
        + _p("TRUJILLO - PERÚ, 2026", bold=True, jc=jc_trujillo)
        + _sect_break()
    )
    body = (
        _h("INTRODUCCIÓN")
        + _p("la FACULTAD de Educación aplica el método científico en sus tesis.", jc=jc_cuerpo)
        + _h("REFERENCIAS")
        + f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar {OK}/></w:sectPr>'
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}" xmlns:r="{RNS}"><w:body>{cover}{body}</w:body></w:document>'
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


def _regla(path: str, rid: str):
    for r in validate_docx(path, RULES):
        if r.rule_id == rid:
            return r
    return None


def test_body_con_keyword_no_rompe_alineacion():
    """Un párrafo del cuerpo con 'facultad' justificado (both) no cuenta:
    `alineacion_caratula_todos_elementos` se limita a la carátula."""
    path = _docx(cuerpo_both=True, titulo_real=True)
    try:
        r = _regla(path, "alineacion_caratula_todos_elementos")
        assert r is not None and r.passed, r.found if r else "regla no evaluada"
    finally:
        os.unlink(path)


def test_caratula_desalineada_falla():
    """La línea de ciudad de la carátula con jc=left sí es detectada."""
    path = _docx(cuerpo_both=True, titulo_real=True, jc_trujillo="left")
    try:
        r = _regla(path, "alineacion_caratula_todos_elementos")
        assert r is not None and not r.passed
    finally:
        os.unlink(path)


def test_titulo_real_sin_placeholder():
    """Título real (sin la frase 'título del trabajo'): se encuentra por
    posición y se mide su tamaño real (sz 26), en vez de morir con []."""
    path = _docx(cuerpo_both=True, titulo_real=True)
    try:
        r = _regla(path, "caratula_titulo_trabajo_tamano")
        assert r is not None
        assert r.found != "@w:val=[]", "título no localizado"
        assert "26" in r.found, r.found
    finally:
        os.unlink(path)


def test_titulo_negrita_mixta_pasa_con_caracteres_reales():
    """El título real (con minúsculas y negrita) cumple la regla de mixta;
    antes moría por XPath de placeholder."""
    path = _docx(cuerpo_both=True, titulo_real=True)
    try:
        r = _regla(path, "caratula_titulo_negrita_mixta")
        assert r is not None and r.passed, r.found if r else "regla no evaluada"
    finally:
        os.unlink(path)
