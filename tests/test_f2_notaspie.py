"""Tests de notas al pie (F2 ítem 3).

Cubre:
- `ExtractedDocx.footnotes`: lee la parte opcional `word/footnotes.xml`
  (`None` cuando el DOCX no la tiene).
- `AnalizadorNotaPie` (`nota_pie` / `operacion: numeracion_consistente`):
  ids consecutivos sin saltos/repetidos, y existencia en `footnotes.xml`.
  Documento sin notas al pie pasa (n/a documentado). Al fallar fija
  `ultimo_nodo` (primera `w:footnoteReference`), de modo que el motor anexa
  "; página N" a la `location` (trabajo "ubicación de NotaPie por página").
- Regla `notas_al_pie_consistencia` end-to-end contra `reglas_unt.yaml`:
  la base (sin notas) cumple, la mutación `notas_pie_ids=[1,2,4]` la invalida
  y no altera otras reglas.

Uso:
    pytest tests/test_f2_notaspie.py -v
"""

import re
from pathlib import Path

from docx_factory import (
    aplicar_mutacion,
    compilar_docx,
    configuracion_base,
)

from validator.engine import load_rules, validate_docx
from validator.extractor import extract

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

RAIZ = Path(__file__).resolve().parent.parent
YAML_PATH = RAIZ / "reglas_unt.yaml"


def _doc_con_notas(ids: list, con_part: bool = True) -> str:
    """DOCX mínimo con referencias w:footnoteReference (y parte footnotes.xml)."""
    refs = "".join(f'<w:r><w:footnoteReference w:id="{i}"/></w:r>' for i in ids)
    body = f"<w:p>{refs}</w:p><w:sectPr/>"
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{body}</w:body></w:document>'
    )
    return _escribir_docx(doc, ids if con_part else None)


def _escribir_docx(doc: str, ids: list | None) -> str:
    import tempfile
    import zipfile

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        if ids is not None:
            separadores = (
                '<w:footnote w:id="-1"><w:p/></w:footnote><w:footnote w:id="0"><w:p/></w:footnote>'
            )
            notas = "".join(
                f'<w:footnote w:id="{i}"><w:p><w:r><w:t>{i}</w:t></w:r></w:p></w:footnote>'
                for i in ids
            )
            z.writestr(
                "word/footnotes.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:footnotes xmlns:w="{WNS}">{separadores}{notas}</w:footnotes>',
            )
    return path


# ---------------------------------------------------------------------------
# Extracción de la parte footnotes
# ---------------------------------------------------------------------------


def test_part_footnotes_opcional():
    path = compilar_docx(configuracion_base())
    try:
        ext = extract(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert ext.footnotes is None


def test_part_footnotes_con_archivo():
    path = _doc_con_notas([1, 2], con_part=True)
    try:
        ext = extract(path)
        assert ext.footnotes is not None
        ids = {int(e.get(f"{{{WNS}}}id")) for e in ext.footnotes.iter() if e.get(f"{{{WNS}}}id")}
    finally:
        Path(path).unlink(missing_ok=True)
    assert ids == {-1, 0, 1, 2}


# ---------------------------------------------------------------------------
# AnalizadorNotaPie (numeracion_consistente)
# ---------------------------------------------------------------------------


def _validar_nota_pie(path: str) -> tuple[bool, str]:
    rules = load_rules(str(YAML_PATH))
    res = validate_docx(path, rules)
    r = next(x for x in res if x.rule_id == "notas_al_pie_consistencia")
    return r.passed, r.found


def _analizador_nota():
    """Compila una regla `nota_pie` y devuelve su AnalizadorNotaPie."""
    regla = {
        "id": "notas_al_pie_consistencia",
        "tipo": "nota_pie",
        "severidad": "warning",
        "nota_pie": {"operacion": "numeracion_consistente"},
    }
    from validator.compilador import CompilerDSL

    compilada = CompilerDSL().compilar({"reglas": [regla]})[0]
    return compilada.analizadores[0], None


def test_sin_notas_pasa_na():
    # End-to-end: la base (sin notas) cumple.
    path = compilar_docx(configuracion_base())
    try:
        passed, _ = _validar_nota_pie(path)
        ext = extract(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert passed
    # A nivel de analizador, el detalle documenta el n/a (la base no las tiene).
    an = _analizador_nota()
    ok, detalle = an[0].analizar(ext)
    assert ok and "n/a" in detalle


def test_consecutivas_pasan():
    path = _doc_con_notas([1, 2, 3], con_part=True)
    try:
        passed, detalle = _validar_nota_pie(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert passed, detalle


def test_con_salto_falla():
    path = _doc_con_notas([1, 2, 4], con_part=True)
    try:
        passed, detalle = _validar_nota_pie(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert not passed
    assert "consecutivas=False" in detalle


def test_repetidas_falla():
    path = _doc_con_notas([1, 1, 2], con_part=True)
    try:
        passed, _ = _validar_nota_pie(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert not passed


def test_sin_part_footnotes_pasa_por_numeracion():
    path = _doc_con_notas([1, 2, 3], con_part=False)
    try:
        passed, _ = _validar_nota_pie(path)
    finally:
        Path(path).unlink(missing_ok=True)
    # Sin la parte footnotes.xml, la existencia no se puede verificar -> pasa
    # por numeración (ids consecutivos). El detalle refleja eso.
    assert passed


# ---------------------------------------------------------------------------
# End-to-end con la factory (mutación de las 49 reglas)
# ---------------------------------------------------------------------------


def _resultado_por(cfg, rule_id):
    rules = load_rules(str(YAML_PATH))
    path = compilar_docx(cfg)
    try:
        res = validate_docx(path, rules)
    finally:
        Path(path).unlink(missing_ok=True)
    return next(r for r in res if r.rule_id == rule_id)


def test_notas_base_pasa():
    r = _resultado_por(configuracion_base(), "notas_al_pie_consistencia")
    assert r.passed, f"{r.found!r}"


def test_mutacion_con_salto_falla_solo_esa_regla():
    cfg = aplicar_mutacion("notas_al_pie_consistencia", configuracion_base())
    r = _resultado_por(cfg, "notas_al_pie_consistencia")
    assert not r.passed, r.found
    # Las otras reglas que dependen del marcador/cuerpo siguen pasando.
    for rid in ("encabezado_membrete", "encabezado_formato", "sangria_parrafo"):
        r2 = _resultado_por(cfg, rid)
        assert r2.passed, f"{rid}: {r2.found!r}"


def test_fallo_de_notas_enriquece_ubicacion_con_pagina():
    # El párrafo con w:footnoteReference está en el cuerpo, así que sí tiene
    # página -> el ítem 1 anexa "; página N" a la ubicación. Se comprueba el
    # sufijo real (no basta con el "página" del texto fijo de la ubicación).
    cfg = aplicar_mutacion("notas_al_pie_consistencia", configuracion_base())
    r = _resultado_por(cfg, "notas_al_pie_consistencia")
    assert not r.passed
    assert re.search(r"; página \d+$", r.location), r.location


def test_notas_que_pasan_no_llevan_pagina():
    # Sin fallo no se enriquece: la ubicación queda tal cual la declara el YAML.
    r = _resultado_por(configuracion_base(), "notas_al_pie_consistencia")
    assert r.passed
    assert not re.search(r"; página \d+$", r.location or ""), r.location
