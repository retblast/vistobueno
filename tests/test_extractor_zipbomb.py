"""Tests de la defensa contra zip bombs en el extractor (hallazgo R2).

La API limita la subida a 10 MB COMPRIMIDOS, pero un paquete OPC hostil puede
declarar una parte que se expande a GBs al leerla. El extractor debe acotar el
tamaño DESCOMPRIMIDO por parte y rechazar el archivo con `BadZipFile` (la API
lo traduce a 422) en vez de agotar la memoria.

Uso:
    pytest tests/test_extractor_zipbomb.py -v
"""

import os
import zipfile

import pytest
from _xml_constants import CONTENT_TYPES, RELS
from docx_factory import compilar_docx, configuracion_base

from validator.extractor import TAMANO_MAXIMO_PARTE_BYTES, extract


def _docx_con_parte_gigante(path: str) -> None:
    """Escribe un DOCX con un `word/document.xml` que se expande sobre la cota.

    El contenido es altamente comprimible (`zlib` lo reduce a unos KB), de
    modo que la parte COMPRIMIDA es diminuta —igual que una zip bomb real—
    pero la DESCOMPRIMIDA supera `TAMANO_MAXIMO_PARTE_BYTES`.
    """
    cuerpo_gigante = b"<w:p><w:r><w:t>" + b"a" * (TAMANO_MAXIMO_PARTE_BYTES + 1024)
    cuerpo_gigante += b"</w:t></w:r></w:p>"
    documento = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b"<w:document xmlns:w="
        b'"http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body>" + cuerpo_gigante + b"</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", documento)


def test_parte_gigante_se_rechaza(tmp_path):
    """Un document.xml que expande sobre la cota lanza BadZipFile."""
    ruta = str(tmp_path / "bomba.docx")
    _docx_con_parte_gigante(ruta)

    with pytest.raises(zipfile.BadZipFile):
        extract(ruta)


def test_parte_gigante_comprimida_es_diminuta(tmp_path):
    """La bomba comprimida pesa KBs: no la detiene el límite de subida de 10 MB."""
    ruta = str(tmp_path / "bomba.docx")
    _docx_con_parte_gigante(ruta)

    # El archivo completo pesa mucho menos que la parte descomprimida: el
    # filtro de 10 MB de la API no lo detendría, por eso la cota vive aquí.
    assert os.path.getsize(ruta) < TAMANO_MAXIMO_PARTE_BYTES


def test_docx_normal_sigue_extrayendose(tmp_path):
    """Un DOCX dentro de la cota se extrae sin cambios (no hay regresión)."""
    ruta = compilar_docx(configuracion_base())

    doc = extract(ruta)

    assert doc.document is not None
    assert doc.headers  # el factory siempre trae header1.xml
    assert doc.footer is not None


def test_api_responde_422_ante_zip_bomb(tmp_path):
    """Integración: POST /validar con una zip bomb da 422, no 500.

    Verifica que el BadZipFile del extractor llegue al mapeo de errores de la
    API como "archivo corrupto" (código 422), en vez de reventar el servidor.
    """
    from conftest import CLIENTE, MIME_DOCX

    ruta = str(tmp_path / "bomba.docx")
    _docx_con_parte_gigante(ruta)

    with open(ruta, "rb") as f:
        respuesta = CLIENTE.post("/validar", files={"archivo": ("tesis.docx", f, MIME_DOCX)})

    assert respuesta.status_code == 422
