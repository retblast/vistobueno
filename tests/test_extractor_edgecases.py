"""Tests edgecase del extractor DOCX (defensa contra zip bomb).

La API limita la subida a 10 MB COMPRIMIDOS, pero un ZIP hostil puede declarar
partes que se expanden a GBs al leerlas. El extractor debe acotar el tamaño
DESCOMPRIMIDO por parte y lanzar BadZipFile (la API lo traduce a 422).

Uso:
    pytest tests/test_extractor_edgecases.py -v
"""

import zipfile

import pytest

from validator.extractor import extract

# Documento XML "mínimo y válido": una etiqueta vacía <w></w> (7 bytes).
_DOC_MINIMO = b"<w></w>"


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


def test_documento_sobre_tope_lanza_badzipfile(monkeypatch):
    """document.xml de 7 bytes con tope a 3 bytes → BadZipFile."""
    monkeypatch.setattr("validator.extractor.TAMANO_MAXIMO_PARTE_BYTES", 3)
    path = _make_docx(_DOC_MINIMO)
    with pytest.raises(zipfile.BadZipFile):
        extract(path)


def test_documento_abajo_tope_pasa(monkeypatch):
    """document.xml de 7 bytes con tope a 10 → extrae sin error."""
    monkeypatch.setattr("validator.extractor.TAMANO_MAXIMO_PARTE_BYTES", 10)
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


def test_documento_minimo_pasa_extraccion():
    """Un DOCX sintético mínimo se extrae sin errores (regression)."""
    from tests.docx_factory import compilar_docx, configuracion_base

    path = compilar_docx(configuracion_base())
    doc = extract(path)
    assert doc.document is not None
    assert doc.headers
    assert doc.footer is not None
