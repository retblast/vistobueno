"""Regresiones de NM-02 (M12b): bloques obligatorios de la carátula.

Los contraejemplos de `docs/AUDITORIA_NORMATIVA_2026-11-12.md` se reproducen
mutando el DOCX del factory. Cada caso parte del documento base y cambia solo
el nodo indicado:

- `missing_school`: falta ESCUELA PROFESIONAL aunque esté FACULTAD;
- `advisor_36pt`: el nombre del asesor pasa a 36 pt aunque la etiqueta siga
  a 12 pt.

Además se comprueba cada propiedad exigida por REQ-16 y REQ-23 en los dos
bloques (presencia, tamaño, negrita, centrado y casing), con el formato
directo, con estilos y con el texto repartido en varios runs. El motor debe
evaluar TODOS los runs con texto, no solo el primero.

Uso:
    pytest tests/test_m12b_caratula_bloques.py -v
"""

from __future__ import annotations

import copy
import zipfile
from pathlib import Path

import pytest
from docx_factory import compilar_docx, configuracion_base
from lxml import etree

from validator.engine import load_rules, validate_docx

RAIZ = Path(__file__).resolve().parent.parent
RULES = load_rules(str(RAIZ / "reglas_unt.yaml"))

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NS = {"w": W}
_ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑÜ"
_abc = "abcdefghijklmnopqrstuvwxyzáéíóúñü"


@pytest.fixture(scope="module")
def docx_base() -> str:
    path = compilar_docx(configuracion_base())
    yield path
    Path(path).unlink(missing_ok=True)


def _mutar(base: str, destino: Path, mutador) -> None:
    """Copia el DOCX y aplica un mutador a `word/document.xml`."""
    with zipfile.ZipFile(base) as zin, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                root = etree.fromstring(
                    data,
                    etree.XMLParser(resolve_entities=False, no_network=True),
                )
                mutador(root)
                data = etree.tostring(
                    root,
                    xml_declaration=True,
                    encoding="UTF-8",
                    standalone=True,
                )
            zout.writestr(item, data)


def _por_regla(path: str) -> dict:
    return {r.rule_id: r for r in validate_docx(path, RULES)}


def _validar_mutacion(base: str, tmp_path: Path, mutador) -> dict:
    destino = tmp_path / "mutado.docx"
    _mutar(base, destino, mutador)
    return _por_regla(str(destino))


def _parrafo(doc, texto: str):
    """Primer párrafo de la carátula cuyo texto contiene `texto`."""
    found = doc.xpath(
        "//w:body/w:p[contains(translate(normalize-space(.), $abc, $abc2), $t)]",
        namespaces=NS,
        abc=_ABC,
        abc2=_abc,
        t=texto.lower(),
    )
    assert found, f"no aparece el bloque {texto!r}"
    return found[0]


def _runs_con_texto(parrafo) -> list:
    return [
        r
        for r in parrafo.xpath(".//w:r", namespaces=NS)
        if "".join(r.xpath(".//w:t/text()", namespaces=NS)).strip()
    ]


def _rpr(run) -> etree._Element:
    rpr = run.find(f"{{{W}}}rPr")
    if rpr is None:
        rpr = etree.Element(f"{{{W}}}rPr")
        run.insert(0, rpr)
    return rpr


def _cambiar_sz(parrafo, valor: str) -> None:
    for run in _runs_con_texto(parrafo):
        sz = _rpr(run).find(f"{{{W}}}sz")
        if sz is None:
            sz = etree.SubElement(_rpr(run), f"{{{W}}}sz")
        sz.set(f"{{{W}}}val", valor)


def _separar_etiqueta_asesor(parrafo):
    """Parte `Asesor(a):` y el nombre en dos runs, como en la tesis real."""
    run = _runs_con_texto(parrafo)[0]
    t = run.find(f"{{{W}}}t")
    etiqueta, nombre = t.text.split(":", 1)
    t.text = etiqueta + ":"
    nuevo = copy.deepcopy(run)
    nuevo.find(f"{{{W}}}t").text = nombre
    nuevo.find(f"{{{W}}}t").set(XML_SPACE, "preserve")
    run.addnext(nuevo)
    return nuevo


def _separar_asesor_en_dos_parrafos(doc, nombre: str) -> None:
    """Deja `ASESORA:` en un párrafo y el nombre en el siguiente.

    Es la estructura observada en la tesis aprobada por el encargado: el
    selector del patrón de mayúsculas/minúsculas no puede quedarse en el
    párrafo de la etiqueta.
    """
    parrafo = _parrafo(doc, "asesor")
    run = _runs_con_texto(parrafo)[0]
    t = run.find(f"{{{W}}}t")
    t.text = "ASESORA:"
    t.set(XML_SPACE, "preserve")

    nombre_parrafo = copy.deepcopy(parrafo)
    for hijo in list(nombre_parrafo):
        if hijo.tag != f"{{{W}}}pPr":
            nombre_parrafo.remove(hijo)
    nombre_run = copy.deepcopy(run)
    t_nombre = nombre_run.find(f"{{{W}}}t")
    t_nombre.text = nombre
    t_nombre.set(XML_SPACE, "preserve")
    nombre_parrafo.append(nombre_run)
    parrafo.addnext(nombre_parrafo)


def _cambiar_sz_run(run, valor: str) -> None:
    sz = _rpr(run).find(f"{{{W}}}sz")
    if sz is None:
        sz = etree.SubElement(_rpr(run), f"{{{W}}}sz")
    sz.set(f"{{{W}}}val", valor)


def _cambiar_negrita(parrafo, valor: str) -> None:
    for run in _runs_con_texto(parrafo):
        b = _rpr(run).find(f"{{{W}}}b")
        if b is None:
            b = etree.SubElement(_rpr(run), f"{{{W}}}b")
        b.set(f"{{{W}}}val", valor)


def _cambiar_jc(parrafo, valor: str) -> None:
    ppr = parrafo.find(f"{{{W}}}pPr")
    if ppr is None:
        ppr = etree.Element(f"{{{W}}}pPr")
        parrafo.insert(0, ppr)
    jc = ppr.find(f"{{{W}}}jc")
    if jc is None:
        jc = etree.SubElement(ppr, f"{{{W}}}jc")
    jc.set(f"{{{W}}}val", valor)


def _cambiar_caso(parrafo, mayusculas: bool, tras_asesor: bool = False) -> None:
    for t in parrafo.xpath(".//w:t", namespaces=NS):
        if not t.text:
            continue
        if tras_asesor and ":" in t.text:
            etiqueta, nombre = t.text.split(":", 1)
            t.text = etiqueta + ":" + (nombre.upper() if mayusculas else nombre.lower())
        else:
            t.text = t.text.upper() if mayusculas else t.text.lower()


def _dividir_runs(parrafo) -> None:
    """Parte el primer run con texto en dos, conservando su formato."""
    run = _runs_con_texto(parrafo)[0]
    t = run.find(f"{{{W}}}t")
    mitad = max(1, len(t.text or "") // 2)
    primero, segundo = (t.text or "")[:mitad], (t.text or "")[mitad:]
    t.text = primero
    t.set(XML_SPACE, "preserve")
    otro = copy.deepcopy(run)
    otro.find(f"{{{W}}}t").text = segundo
    otro.find(f"{{{W}}}t").set(XML_SPACE, "preserve")
    run.addnext(otro)


# ---------------------------------------------------------------------------
# Contraejemplos de la auditoría (deben fallar tras NM-02)
# ---------------------------------------------------------------------------


def test_missing_school_falla_aunque_este_la_facultad(docx_base: str, tmp_path: Path):
    """REQ-16: FACULTAD no satisface la exigencia de ESCUELA PROFESIONAL."""

    def mutar(doc):
        bloque = _parrafo(doc, "escuela profesional")
        bloque.getparent().remove(bloque)

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_facultad_escuela_tamano"].passed


def test_advisor_36pt_falla_aunque_la_etiqueta_este_correcta(docx_base: str, tmp_path: Path):
    """REQ-23: 36 pt en el nombre del asesor no lo salva la etiqueta a 12 pt."""

    def mutar(doc):
        nombre = _separar_etiqueta_asesor(_parrafo(doc, "asesor"))
        _cambiar_sz_run(nombre, "72")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_autores_tamano"].passed


# ---------------------------------------------------------------------------
# Cada bloque y cada propiedad (REQ-16 y REQ-23)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bloque", ["facultad", "escuela profesional"])
def test_facultad_y_escuela_con_tamano_correcto_cumplen(
    docx_base: str, tmp_path: Path, bloque: str
):
    base = _por_regla(docx_base)
    assert base["caratula_facultad_escuela_tamano"].passed

    def mutar(doc):
        _cambiar_sz(_parrafo(doc, bloque), "20")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_facultad_escuela_tamano"].passed


@pytest.mark.parametrize("bloque", ["facultad", "escuela profesional"])
def test_facultad_y_escuela_con_negrita_correcta_cumplen(
    docx_base: str, tmp_path: Path, bloque: str
):
    assert _por_regla(docx_base)["caratula_facultad_negrita_mayusculas"].passed

    def mutar(doc):
        _cambiar_negrita(_parrafo(doc, bloque), "0")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_facultad_negrita_mayusculas"].passed


@pytest.mark.parametrize("bloque", ["facultad", "escuela profesional"])
def test_facultad_y_escuela_en_mayusculas_cumplen(docx_base: str, tmp_path: Path, bloque: str):
    def mutar(doc):
        _cambiar_caso(_parrafo(doc, bloque), mayusculas=False)

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_facultad_negrita_mayusculas"].passed


@pytest.mark.parametrize("bloque", ["facultad", "escuela profesional"])
def test_facultad_y_escuela_centrados_cumplen(docx_base: str, tmp_path: Path, bloque: str):
    def mutar(doc):
        _cambiar_jc(_parrafo(doc, bloque), "left")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["alineacion_caratula_todos_elementos"].passed


def test_asesor_con_negrita_cumple(docx_base: str, tmp_path: Path):
    regla = "caratula_asesor_negrita"
    assert _por_regla(docx_base)[regla].passed

    def mutar(doc):
        _cambiar_negrita(_parrafo(doc, "asesor"), "0")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado[regla].passed


def test_asesor_centrado_cumple(docx_base: str, tmp_path: Path):
    def mutar(doc):
        _cambiar_jc(_parrafo(doc, "asesor"), "left")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["alineacion_caratula_todos_elementos"].passed


def test_nombre_del_asesor_en_mayusculas_falla(docx_base: str, tmp_path: Path):
    """REQ-23 pide mayúsculas y minúsculas en el nombre, no TODO mayúsculas."""

    def mutar(doc):
        _cambiar_caso(_parrafo(doc, "asesor"), mayusculas=True, tras_asesor=True)

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_asesor_negrita"].passed


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("Dra. Lucía Elena Mendoza Ruiz", True),
        ("DRA. LUCÍA ELENA MENDOZA RUIZ", False),
    ],
)
def test_nombre_del_asesor_en_parrafo_separado(
    docx_base: str, tmp_path: Path, nombre: str, esperado: bool
):
    """La tesis aprobada separa `ASESORA:` del nombre en el párrafo siguiente."""

    def mutar(doc):
        _separar_asesor_en_dos_parrafos(doc, nombre)

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert resultado["caratula_asesor_negrita"].passed is esperado


# ---------------------------------------------------------------------------
# Formato efectivo: estilos y texto partido en varios runs
# ---------------------------------------------------------------------------


def test_bloques_con_formato_heredado_de_estilos_cumplen():
    """El tamaño, la negrita y el centrado pueden venir de `styles.xml`."""
    cfg = configuracion_base()
    for bloque in ("facultad", "escuela"):
        cfg["portada"][bloque].pop("negrita")
        cfg["portada"][bloque].pop("sz")
        cfg["portada"][bloque]["estilo_caracter"] = "Caratula13"
        cfg["portada"][bloque]["estilo_parrafo"] = "CentradoCaratula"
        cfg["portada"][bloque]["sin_jc"] = True
    cfg["styles"] = {
        "estilos": {
            "Caratula13": {
                "type": "character",
                "rpr": '<w:b/><w:sz w:val="26"/>',
            },
            "CentradoCaratula": {
                "type": "paragraph",
                "ppr": '<w:jc w:val="center"/>',
            },
        }
    }
    path = compilar_docx(cfg)
    try:
        resultado = _por_regla(path)
        assert resultado["caratula_facultad_escuela_tamano"].passed, resultado[
            "caratula_facultad_escuela_tamano"
        ].found
        assert resultado["caratula_facultad_negrita_mayusculas"].passed, resultado[
            "caratula_facultad_negrita_mayusculas"
        ].found
        assert resultado["alineacion_caratula_todos_elementos"].passed, resultado[
            "alineacion_caratula_todos_elementos"
        ].found
    finally:
        Path(path).unlink(missing_ok=True)


def test_run_incorrecto_en_escuela_partida_falla(docx_base: str, tmp_path: Path):
    """Con el texto en dos runs, un solo run a 10 pt debe detectarse."""

    def mutar(doc):
        bloque = _parrafo(doc, "escuela profesional")
        _dividir_runs(bloque)
        _cambiar_sz(bloque, "20")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_facultad_escuela_tamano"].passed


def test_run_incorrecto_en_nombre_del_asesor_partido_falla(docx_base: str, tmp_path: Path):
    """La etiqueta a 12 pt no salva un run del nombre a 36 pt."""

    def mutar(doc):
        bloque = _parrafo(doc, "asesor")
        _dividir_runs(bloque)
        _cambiar_sz_run(_runs_con_texto(bloque)[1], "72")

    resultado = _validar_mutacion(docx_base, tmp_path, mutar)
    assert not resultado["caratula_autores_tamano"].passed
