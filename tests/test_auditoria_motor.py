"""Regresiones de la auditoría de motor de la semana 10 (AUD-01…AUD-03, AUD-20).

Blinda los arreglos con fixtures que reproducen la estructura real de las
plantillas:

- AUD-01: títulos del cuerpo que acaban en letra romana no deben perder su
  última letra al normalizarse (falso positivo de `indice_apunta_secciones`).
- AUD-02: los anexos se buscan hasta el final del documento y los Títulos1
  cuentan como texto (en las plantillas cada "Anexo N." es un Título1).
- AUD-03: al fallar `all_eq` el `found` muestra primero a los culpables y la
  `location` apunta a la página del nodo infractor, no a la del primero.

Uso:
    pytest tests/test_auditoria_motor.py -v
"""

import tempfile
import zipfile
from pathlib import Path

from docx_factory import (
    compilar_docx,
    configuracion_anexos_titulos,
    configuracion_titulo_romano,
)

from validator.analizadores import _norm_indice, _norm_titulo_cuerpo, _sigpalabra
from validator.engine import load_rules, validate_docx

RULES = load_rules("reglas_unt.yaml")

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


def _por_regla(resultados):
    return {r.rule_id: r for r in resultados}


def _sin_archivo(path: str):
    Path(path).unlink(missing_ok=True)


def test_norm_indice_no_recorta_sufijo_de_palabra():
    """AUD-01: sin número de página, la última letra se conserva."""
    assert _norm_indice("GENERAL") == "GENERAL"
    assert _norm_titulo_cuerpo("General") == "GENERAL"


def test_norm_indice_si_recorta_pagina_arabiga_y_romana():
    """AUD-01: con número de página, sí se recorta (precedido de espacio)."""
    assert _norm_indice("1.4. OBJETIVOS 9") == "OBJETIVOS"
    assert _norm_indice("OBJETIVOS iv") == "OBJETIVOS"


def test_aud01_titulo_romano_apunta_a_seccion_real():
    """AUD-01/AUD-20: "GENERAL" del cuerpo y "1.4.1. GENERAL 9" del índice."""
    path = compilar_docx(configuracion_titulo_romano())
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)
    assert res["indice_apunta_secciones"].passed


def test_aud02_anexos_como_titulos_satisfacen_minimos():
    """AUD-02/AUD-20: los "Anexo N." como Título1 se detectan igual."""
    path = compilar_docx(configuracion_anexos_titulos())
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)
    assert res["anexos_minimos_cuantitativo"].passed


def test_aud02_reporta_todos_los_faltantes_sin_truncar():
    """AUD-02/AUD-20: `found` lista los 9 anexos faltantes (antes [:8])."""
    cfg = configuracion_anexos_titulos()
    cfg["anexos_items"] = []
    path = compilar_docx(cfg)
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)
    regla = res["anexos_minimos_cuantitativo"]
    assert not regla.passed
    # El noveno ítem obligatorio quedaría fuera con el truncado antiguo.
    assert "Carta de autorización de publicación" in regla.found


def _para_sz(texto: str, sz: str) -> str:
    return (
        "<w:p><w:r><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
        f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
        "</w:rPr>"
        f'<w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'
    )


def _p_break() -> str:
    return "<w:p><w:r><w:lastRenderedPageBreak/></w:r></w:p>"


def _docx_sz(paras: list[str]) -> str:
    body = "".join(paras) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
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


def _docx_caratula(texto: str, sz: str) -> str:
    paras = [
        _para_sz("UNIVERSIDAD NACIONAL DE TRUJILLO", "24"),
        _para_sz(texto, sz),
    ]
    # El `w:pPr/w:sectPr` cierra la portada: los párrafos anteriores son la
    # carátula para `contexto: caratula`.
    body = (
        "".join(paras)
        + "<w:p><w:pPr><w:sectPr/></w:pPr></w:p>"
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
    )
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


def _regla_sz(comparacion: str = "all_eq", esperado: str = "24") -> dict:
    return {
        "id": "sz_test",
        "tipo": "atributo_xml",
        "descripcion": "Tamaño de letra del cuerpo",
        "valor_esperado": "12pt",
        "severidad": "error",
        "ubicacion": "Cuerpo",
        "fuente": "MANUAL.docx",
        "cita": '"Times New Roman: 12 puntos"',
        "atributo_xml": {
            "parte": "document",
            "contexto": "todos",
            "xpath": "//w:body/w:p/w:r/w:rPr/w:sz",
            "atributo": "@w:val",
            "comparacion": comparacion,
            "esperado": esperado,
        },
    }


def _validar_sz(comparacion: str, esperado: str):
    path = _docx_sz([_para_sz("A", "24"), _p_break(), _para_sz("B", "30"), _para_sz("C", "24")])
    try:
        return validate_docx(
            path, {"namespaces": {"w": WNS}, "reglas": [_regla_sz(comparacion, esperado)]}
        )[0]
    finally:
        _sin_archivo(path)


def test_aud03_culpables_primero_y_pagina_del_nodo_infractor():
    """AUD-03: `incumplen` va antes y la página es la del nodo culpable."""
    r = _validar_sz("all_eq", "24")
    assert not r.passed
    assert r.found == "@w:val esperado=24; incumplen=[#2=30]; muestra=[24, 30, 24]"
    # El primer nodo (A) está en la página 1; el culpable (B) en la 2.
    assert r.location == "Cuerpo; página 2"


def test_aud03_valores_sin_repr_crudo():
    """AUD-03: la muestra se imprime legible, sin comillas de lista Python."""
    r = _validar_sz("eq", "26")
    assert not r.passed
    assert r.found == "@w:val=[24, 30, 24] esperado=26"


def test_aud06_entrada_sin_palabra_larga_se_omite():
    """AUD-06: sin token de 4+ caracteres no hay señal para verificar."""
    assert _sigpalabra("1.2 IV") == ""
    assert _sigpalabra("FASE I") == "FASE"


def test_aud07_linea_bachiller_se_evalua():
    """AUD-07: la línea de Bachiller sí se compara contra los 13 pt."""
    path = _docx_caratula(
        "Trabajo de Investigación para optar el grado de Bachiller en Educación Inicial",
        "24",
    )
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)
    regla = res["caratula_optar_grado_tamano"]
    assert not regla.passed
    assert regla.found == "@w:val=[24] esperado=26"


def test_aud07_otras_titulaciones_no_disparan_la_regla():
    """AUD-07: la línea de Licenciatura queda fuera del alcance (n/a)."""
    path = _docx_caratula(
        "Para Optar el Título Profesional de Licenciada en Educación Inicial",
        "24",
    )
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)
    regla = res["caratula_optar_grado_tamano"]
    assert regla.passed
    assert regla.found == "cumple"
