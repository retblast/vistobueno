"""Papel A4 en todas las secciones aplicables (M2/VA-03).

Antes `papel_tamano` leía solo `//w:sectPr[1]/w:pgSz` con `eq`: una portada
A4 y un cuerpo Letter pasaban, y una sección A4 horizontal legítima fallaba
porque Word guarda `w:w=16838` y `w:h=11906`.

Estos tests fijan el comportamiento nuevo:

- se comparan **todas** las secciones, incluida la carátula y los anexos;
- la orientación se normaliza por lados físicos (corto 11906 / largo
  16838), con o sin `w:orient="landscape"`;
- una sección culpable se identifica por su posición `#N` en el detalle.

Los documentos son sintéticos y no contienen datos reales.

Uso:
    pytest tests/test_papel_secciones.py -v
"""

import os
import tempfile
import zipfile
from pathlib import Path

from validator.engine import load_rules, validate_docx

RAIZ = Path(__file__).resolve().parent.parent
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

A4_VERTICAL = '<w:pgSz w:w="11906" w:h="16838"/>'
A4_HORIZONTAL = '<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
A4_HORIZONTAL_SIN_ORIENT = '<w:pgSz w:w="16838" w:h="11906"/>'
LETTER_VERTICAL = '<w:pgSz w:w="12240" w:h="15840"/>'
LETTER_HORIZONTAL = '<w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>'

RULES = load_rules(str(RAIZ / "reglas_unt.yaml"))


def _p(texto: str, ppr: str = "") -> str:
    ppr_xml = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    return f'<w:p>{ppr_xml}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _sect_break(pg_sz: str) -> str:
    """Párrafo que cierra una sección (sectPr dentro de pPr)."""
    return _p(" ", f"<w:sectPr>{pg_sz}</w:sectPr>")


def _sect_final(pg_sz: str) -> str:
    return f"<w:sectPr>{pg_sz}</w:sectPr>"


def _docx(pg_sizes: list[str], final: str | None = None) -> str:
    """DOCX con una sección por cada `pg_sizes` y un sectPr final opcional.

    Las secciones se cierran con párrafos de salto; el texto de cada una es
    irrelevante para la regla del papel.
    """
    body = _p("UNIVERSIDAD NACIONAL DE TRUJILLO")
    for pg_sz in pg_sizes:
        body += _sect_break(pg_sz) + _p("Contenido de la sección siguiente.")
    body += _sect_final(final if final is not None else pg_sizes[-1])
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{body}</w:body></w:document>'
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


def _papel(path: str):
    for resultado in validate_docx(path, RULES):
        if resultado.rule_id == "papel_tamano":
            return resultado
    return None


# ---------------------------------------------------------------------------
# Todas las secciones
# ---------------------------------------------------------------------------


def test_portada_a4_y_cuerpo_letter_falla():
    """El defecto de VA-03: la segunda sección ya no queda sin revisar."""
    path = _docx([A4_VERTICAL], final=LETTER_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert not regla.passed
    # La sección 2 es la culpable (la portada cumple).
    assert "#2=" in regla.found, regla.found
    assert "27.94 cm" in regla.found or "21.59 cm" in regla.found, regla.found


def test_todas_las_secciones_a4_pasa():
    path = _docx([A4_VERTICAL, A4_VERTICAL], final=A4_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert regla.passed, regla.found


def test_seccion_culpable_se_senala_por_posicion():
    """Con tres secciones, el detalle nombra la del medio y no las conformes."""
    path = _docx([A4_VERTICAL, LETTER_VERTICAL], final=A4_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert not regla.passed
    assert "#2=" in regla.found, regla.found
    assert "#1=" not in regla.found, regla.found
    assert "#3=" not in regla.found, regla.found


def test_caratula_y_anexos_estan_incluidos():
    """El alcance es todo el documento: A4 no depende del contenido."""
    path = _docx([A4_VERTICAL, A4_VERTICAL], final=LETTER_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert not regla.passed, "una sección de anexos con Letter no puede pasar"
    assert "#3=" in regla.found, regla.found


# ---------------------------------------------------------------------------
# Orientación
# ---------------------------------------------------------------------------


def test_a4_horizontal_legitimo_pasa():
    """Word guarda el A4 horizontal como 16838 x 11906: es el mismo papel."""
    path = _docx([A4_VERTICAL, A4_HORIZONTAL], final=A4_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert regla.passed, regla.found


def test_a4_horizontal_sin_orient_pasa():
    """Los conversores desde PDF omiten `w:orient`: la geometría basta."""
    path = _docx([A4_VERTICAL, A4_HORIZONTAL_SIN_ORIENT], final=A4_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert regla.passed, regla.found


def test_letter_horizontal_falla():
    path = _docx([A4_VERTICAL, LETTER_HORIZONTAL], final=A4_VERTICAL)
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert not regla.passed
    assert "#2=" in regla.found, regla.found


def test_papel_ausente_falla():
    """Sin `w:pgSz` no se puede afirmar A4: la regla no puede dar verde."""
    path = _docx([], final="")
    try:
        regla = _papel(path)
    finally:
        os.unlink(path)
    assert regla is not None
    assert not regla.passed
    assert "sin valores que comparar" in regla.found, regla.found
