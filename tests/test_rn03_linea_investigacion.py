"""RN-03: la línea de investigación se compara por párrafo, no por run.

El catálogo RCU-220 dice qué línea es válida; la comprobación debe reunir
todo el texto del párrafo de valor. Con el XPath anterior (`.../w:p[1]//w:t`)
una línea legítima repartida en dos runs se partía en dos textos y ninguno
estaba en el catálogo. La comprobación de letras mayúsculas/minúsculas sigue
siendo por run (REQ-24), así que no se toca `patron_texto`.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from validator.engine import load_rules, validate_docx

RAIZ = Path(__file__).resolve().parent.parent
REGLAS = load_rules(str(RAIZ / "reglas_unt.yaml"))
REGLA = "caratula_linea_investigacion"

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

LINEA = "Educación y Ciencias de la Comunicación y Desarrollo Sostenible"


def _para(runs: list[str]) -> str:
    """Párrafo con un run por texto recibido (asinile el Word partido)."""
    contenidos = "".join(f'<w:r><w:t xml:space="preserve">{texto}</w:t></w:r>' for texto in runs)
    return f"<w:p>{contenidos}</w:p>"


def _docx(caratula: list[list[str]], cuerpo: list[list[str]] | None = None) -> Path:
    """DOCX mínimo con la carátula cerrada por un salto de sección."""
    cuerpo = cuerpo or []
    body = (
        "".join(_para(p) for p in caratula)
        + "<w:p><w:pPr><w:sectPr/></w:pPr></w:p>"
        + "".join(_para(p) for p in cuerpo)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}" xmlns:r="{RNS}"><w:body>{body}</w:body></w:document>'
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", xml)
    return path


def _resultado(caratula: list[list[str]], cuerpo: list[list[str]] | None = None):
    path = _docx(caratula, cuerpo)
    try:
        return next(r for r in validate_docx(str(path), REGLAS) if r.rule_id == REGLA)
    finally:
        path.unlink(missing_ok=True)


def test_linea_en_un_solo_run_cumple():
    resultado = _resultado([["Línea de investigación:"], [LINEA]])
    assert resultado.passed, resultado.found


def test_linea_partida_en_dos_runs_cumple():
    """RN-03: el catálogo ve el párrafo completo aunque Word parta el texto."""
    resultado = _resultado(
        [
            ["Línea de investigación:"],
            ["Educación y ", "Ciencias de la Comunicación y Desarrollo Sostenible"],
        ]
    )
    assert resultado.passed, resultado.found


def test_linea_invalida_partida_en_runs_falla_con_el_texto_completo():
    resultado = _resultado(
        [["Línea de investigación:"], ["Educación y Ciencias de la ", "Comunicación"]]
    )
    assert not resultado.passed
    assert "en_lista_faltan" in resultado.found, resultado.found
    assert "educación y ciencias de la comunicación" in resultado.found, resultado.found


def test_linea_valida_solo_fuera_de_la_caratula_no_cumple():
    """La línea del cuerpo no satisface una regla que aplica solo a portada."""
    resultado = _resultado(
        caratula=[["UNIVERSIDAD NACIONAL DE TRUJILLO"], ["Autores:"], ["Ana María Pérez"]],
        cuerpo=[["Línea de investigación:"], [LINEA]],
    )
    assert not resultado.passed
    assert "sin nodos de texto que evaluar" in resultado.found, resultado.found
