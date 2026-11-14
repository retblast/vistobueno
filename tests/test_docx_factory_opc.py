"""Regresión de integridad OPC del factory (M11 / VA-17).

El DOCX sintético debe ser un paquete OPC válido, no solo un ZIP que el
extractor sabe leer: `python-docx` tiene que abrirlo y cada relación interna
debe apuntar a una parte existente, declarada en `[Content_Types].xml`.

Antes de M11 el documento base fallaba con
`KeyError: "There is no item named 'media/logo.png' in the archive"` porque
las relaciones de cabecera, pie e imagen vivían en `_rels/.rels` (raíz) y el
PNG nunca se escribía.
"""

import posixpath
import xml.etree.ElementTree as ET
import zipfile

import docx
import pytest
from _docx_builder import compilar_docx, configuracion_base
from _mutations import aplicar_mutacion
from _xml_constants import RNS

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE_DOC_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)


def _config_con_notas() -> dict:
    return aplicar_mutacion("notas_al_pie_consistencia", configuracion_base())


def _relaciones(z: zipfile.ZipFile, parte_rels: str) -> dict[str, ET.Element]:
    raiz = ET.fromstring(z.read(parte_rels))
    return {rel.get("Id"): rel for rel in raiz}


def _parte_destino(parte_rels: str, target: str) -> str:
    """Resuelve un `Target` relativo al directorio de la parte que lo declara."""
    # `word/_rels/document.xml.rels` declara destinos relativos a `word/`.
    directorio = posixpath.dirname(posixpath.dirname(parte_rels))
    return posixpath.normpath(posixpath.join(directorio, target))


def _rels_del_paquete(z: zipfile.ZipFile) -> list[str]:
    return sorted(n for n in z.namelist() if n.endswith(".rels"))


def _ids_referenciadas(xml: bytes) -> set[str]:
    """Ids de relación usados en una parte (`r:id` y `r:embed`)."""
    raiz = ET.fromstring(xml)
    return {
        valor
        for nodo in raiz.iter()
        for clave, valor in nodo.attrib.items()
        if clave in (f"{{{RNS}}}id", f"{{{RNS}}}embed")
    }


@pytest.mark.parametrize("con_notas", [False, True])
def test_el_documento_base_abre_con_python_docx(con_notas):
    cfg = _config_con_notas() if con_notas else configuracion_base()
    documento = docx.Document(compilar_docx(cfg))

    assert documento.paragraphs
    assert documento.sections


@pytest.mark.parametrize("con_notas", [False, True])
def test_todos_los_destinos_internos_existen(con_notas):
    cfg = _config_con_notas() if con_notas else configuracion_base()

    with zipfile.ZipFile(compilar_docx(cfg)) as z:
        partes = set(z.namelist())
        for parte_rels in _rels_del_paquete(z):
            for rel in _relaciones(z, parte_rels).values():
                if rel.get("TargetMode") == "External":
                    continue
                destino = _parte_destino(parte_rels, rel.get("Target"))
                assert destino in partes, f"{parte_rels}: {rel.get('Id')} -> {destino}"


@pytest.mark.parametrize("con_notas", [False, True])
def test_cada_id_referenciado_esta_declarado_en_su_parte(con_notas):
    cfg = _config_con_notas() if con_notas else configuracion_base()
    esperado = {
        "word/document.xml": "word/_rels/document.xml.rels",
        "word/header1.xml": "word/_rels/header1.xml.rels",
    }

    with zipfile.ZipFile(compilar_docx(cfg)) as z:
        for parte, parte_rels in esperado.items():
            declaradas = set(_relaciones(z, parte_rels))
            assert _ids_referenciadas(z.read(parte)) <= declaradas, parte


def test_la_raiz_solo_declara_el_documento_principal():
    with zipfile.ZipFile(compilar_docx(configuracion_base())) as z:
        relaciones = _relaciones(z, "_rels/.rels")

    assert [rel.get("Type") for rel in relaciones.values()] == [OFFICE_DOC_REL]
    assert relaciones["rId1"].get("Target") == "word/document.xml"


def test_cabecera_pie_imagen_y_hipervinculo_viven_en_document_xml_rels():
    with zipfile.ZipFile(compilar_docx(configuracion_base())) as z:
        relaciones = _relaciones(z, "word/_rels/document.xml.rels")

    destinos = {rel.get("Target"): rel for rel in relaciones.values()}
    assert destinos["header1.xml"].get("Type", "").endswith("/header")
    assert destinos["footer1.xml"].get("Type", "").endswith("/footer")
    assert destinos["media/logo.png"].get("Type", "").endswith("/image")
    assert destinos["https://orcid.org/0000-0002-1825-0097"].get("TargetMode") == "External"


def test_el_logo_es_un_png_valido_en_la_parte_correcta():
    with zipfile.ZipFile(compilar_docx(configuracion_base())) as z:
        assert "word/media/logo.png" in z.namelist()
        png = z.read("word/media/logo.png")

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert png[12:16] == b"IHDR"


@pytest.mark.parametrize("con_notas", [False, True])
def test_todas_las_partes_tienen_tipo_de_contenido(con_notas):
    cfg = _config_con_notas() if con_notas else configuracion_base()

    with zipfile.ZipFile(compilar_docx(cfg)) as z:
        partes = [n for n in z.namelist() if n != "[Content_Types].xml"]
        raiz = ET.fromstring(z.read("[Content_Types].xml"))

    defaults = {n.get("Extension") for n in raiz.findall(f"{{{CT_NS}}}Default")}
    overrides = {n.get("PartName").lstrip("/") for n in raiz.findall(f"{{{CT_NS}}}Override")}
    for parte in partes:
        extension = parte.rsplit(".", 1)[-1]
        assert parte in overrides or extension in defaults, parte


def test_las_notas_de_pie_declaran_su_parte_y_su_relacion():
    with zipfile.ZipFile(compilar_docx(_config_con_notas())) as z:
        partes = set(z.namelist())
        relaciones = _relaciones(z, "word/_rels/document.xml.rels")
        content_types = ET.fromstring(z.read("[Content_Types].xml"))

    assert "word/footnotes.xml" in partes
    assert any(
        rel.get("Target") == "footnotes.xml" and rel.get("Type", "").endswith("/footnotes")
        for rel in relaciones.values()
    )
    overrides = {n.get("PartName") for n in content_types.findall(f"{{{CT_NS}}}Override")}
    assert "/word/footnotes.xml" in overrides
