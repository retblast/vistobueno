"""Tests edgecase del extractor DOCX: validación de entrada y zip bomb.

La API limita la subida a 10 MB COMPRIMIDOS, pero un ZIP hostil puede declarar
partes que se expanden a GBs al leerlas. El extractor debe acotar el tamaño
DESCOMPRIMIDO por parte y lanzar `BadZipFile` (la API lo traduce a 422).

Además, un ZIP válido puede contener un XML truncado, una raíz ajena o un
documento sin `w:body`. El extractor debe rechazarlo con
`InvalidDocumentError` —subclase de `ValueError`— en vez de dejar escapar una
excepción de lxml.

Uso:
    pytest tests/test_extractor_edgecases.py -v
"""

import zipfile

import pytest

from validator.extractor import InvalidDocumentError, extract

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Documento XML mínimo que el extractor admite: raíz `w:document` con `w:body`.
_DOC_MINIMO = f'<w:document xmlns:w="{_W}"><w:body/></w:document>'.encode()


def _make_docx(
    document_xml: bytes,
    *,
    headers: dict | None = None,
    footers: dict | None = None,
    footnotes: bytes | None = b"",
) -> str:
    """Construye un .docx temporal con las partes indicadas.

    Solo se escriben las partes solicitadas; las ausentes provocan KeyError
    en el extractor (comportamiento esperado: la API devuelve 422).
    """
    path = "/tmp/mini_docx.docx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "")
        z.writestr("word/document.xml", document_xml)
        for nombre, contenido in (headers or {}).items():
            z.writestr(nombre, contenido)
        for nombre, contenido in (footers or {}).items():
            z.writestr(nombre, contenido)
        if footnotes is not None:
            z.writestr("word/footnotes.xml", footnotes)
    return path


# ---------------------------------------------------------------------------
# Límite de descompresión (zip bomb)
# ---------------------------------------------------------------------------


def test_documento_sobre_tope_lanza_badzipfile(monkeypatch):
    """document.xml con tope a 3 bytes → BadZipFile (no InvalidDocumentError)."""
    monkeypatch.setattr("validator.extractor.TAMANO_MAXIMO_PARTE_BYTES", 3)
    path = _make_docx(_DOC_MINIMO)
    with pytest.raises(zipfile.BadZipFile):
        extract(path)


def test_documento_abajo_tope_pasa(monkeypatch):
    """document.xml mínimo con tope igual a su tamaño → extrae sin error."""
    monkeypatch.setattr("validator.extractor.TAMANO_MAXIMO_PARTE_BYTES", len(_DOC_MINIMO))
    path = _make_docx(_DOC_MINIMO)
    doc = extract(path)
    assert doc.document is not None


def test_header_sobre_tope_lanza_badzipfile(monkeypatch):
    """header1.xml de 2000 bytes con tope a 1000 → BadZipFile."""
    monkeypatch.setattr("validator.extractor.TAMANO_MAXIMO_PARTE_BYTES", 1_000)
    path = _make_docx(_DOC_MINIMO, headers={"word/header1.xml": b"X" * 2000})
    with pytest.raises(zipfile.BadZipFile, match="header1"):
        extract(path)


def test_footnotes_sobre_tope_lanza_badzipfile(monkeypatch):
    """footnotes.xml de 2000 bytes con tope a 1000 → BadZipFile."""
    monkeypatch.setattr("validator.extractor.TAMANO_MAXIMO_PARTE_BYTES", 1_000)
    path = _make_docx(_DOC_MINIMO, footnotes=b"Y" * 2000)
    with pytest.raises(zipfile.BadZipFile, match="footnotes"):
        extract(path)


# ---------------------------------------------------------------------------
# Validación de la entrada (M1a / VA-11)
# ---------------------------------------------------------------------------


def test_invalid_document_error_es_valueerror():
    """B5 de Int1 traduce `ValueError` a 422; la excepción debe heredar de él."""
    assert issubclass(InvalidDocumentError, ValueError)


def test_xml_truncado_lanza_invalid_document_error():
    """Un XML cortado a la mitad se rechaza de forma controlada."""
    path = _make_docx(b"<w:document")
    with pytest.raises(InvalidDocumentError, match="word/document.xml"):
        extract(path)


def test_raiz_ajena_lanza_invalid_document_error():
    """Un XML bien formado con raíz que no es WordprocessingML se rechaza."""
    path = _make_docx(b'<root xmlns="urn:otro"><body/></root>')
    with pytest.raises(InvalidDocumentError, match="raíz"):
        extract(path)


def test_namespace_ausente_lanza_invalid_document_error():
    """`<document>` sin namespace no es `w:document`."""
    path = _make_docx(b"<document><body/></document>")
    with pytest.raises(InvalidDocumentError, match="raíz"):
        extract(path)


def test_documento_sin_cuerpo_lanza_invalid_document_error():
    """Una raíz válida sin `w:body` se rechaza."""
    path = _make_docx(f'<w:document xmlns:w="{_W}"/>'.encode())
    with pytest.raises(InvalidDocumentError, match="w:body"):
        extract(path)


def test_documento_minimo_valido_se_extrae():
    """El documento mínimo admitido se extrae sin errores."""
    doc = extract(_make_docx(_DOC_MINIMO))
    assert doc.document is not None


def test_header_invalido_lanza_invalid_document_error():
    """Una parte opcional presente con XML roto también se rechaza."""
    path = _make_docx(_DOC_MINIMO, headers={"word/header1.xml": b"<broken"})
    with pytest.raises(InvalidDocumentError, match="header1"):
        extract(path)


def test_footnotes_invalidas_lanzan_invalid_document_error():
    """Notas al pie presentes con XML roto se rechazan."""
    path = _make_docx(_DOC_MINIMO, footnotes=b"<broken")
    with pytest.raises(InvalidDocumentError, match="footnotes"):
        extract(path)


def test_documento_minimo_pasa_extraccion():
    """Un DOCX sintético mínimo se extrae sin errores (regression)."""
    from docx_factory import compilar_docx, configuracion_base

    path = compilar_docx(configuracion_base())
    doc = extract(path)
    assert doc.document is not None
    assert doc.headers
    assert doc.footer is not None
