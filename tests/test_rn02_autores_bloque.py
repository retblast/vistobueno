"""RN-02: negrita y capitalidad de TODOS los autores de la carátula.

Antes solo se medía el primer párrafo detrás de «AUTORES:». En las tesis
reales hay dos nombres separados por su ORCID; aquí se fija que:

- se revisan todos los párrafos de nombre hasta «ASESOR(A):»;
- las líneas ORCID quedan fuera (su formato no es el del nombre);
- la negrita se mide por run con `all_eq`;
- la capitalidad se mide sobre el nombre completo, aunque Word lo parta en
  varios runs.

Se conserva el criterio EVALUADO: mayúsculas y minúsculas, no el literal
«todo en mayúsculas» del manual, pendiente de decisión de biblioteca.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from validator.engine import load_rules, validate_docx

RAIZ = Path(__file__).resolve().parent.parent
REGLAS = load_rules(str(RAIZ / "reglas_unt.yaml"))
NEGRITA = "caratula_autores_mayusculas_sin_negrita"

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
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


def _run(texto: str, negrita: bool = False) -> str:
    rpr = "<w:rPr><w:b/></w:rPr>" if negrita else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{texto}</w:t></w:r>'


def _para(runs: list[tuple[str, bool]]) -> str:
    return "<w:p>" + "".join(_run(texto, negrita) for texto, negrita in runs) + "</w:p>"


def _docx(paras: list[list[tuple[str, bool]]]) -> Path:
    """DOCX mínimo con la carátula cerrada por un salto de sección."""
    body = (
        "".join(_para(p) for p in paras)
        + "<w:p><w:pPr><w:sectPr/></w:pPr></w:p>"
        + _para([("INTRODUCCIÓN", False)])
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{body}</w:body></w:document>'
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", xml)
    return path


def _resultado(paras: list[list[tuple[str, bool]]]):
    path = _docx(paras)
    try:
        return next(r for r in validate_docx(str(path), REGLAS) if r.rule_id == NEGRITA)
    finally:
        path.unlink(missing_ok=True)


def _caratula_dos_autores(
    segundo: list[tuple[str, bool]] | None = None,
    orcid_negrita: bool = False,
    asesor_mayusculas: bool = False,
) -> list[list[tuple[str, bool]]]:
    segundo = segundo or [("Blanca Esther Torres Ruiz", False)]
    return [
        [("AUTORES:", False)],
        [("Ana María Pérez García", False)],
        [("https://orcid.org/0000-0002-1825-0097", orcid_negrita)],
        segundo,
        [("https://orcid.org/0000-0002-1694-233X", orcid_negrita)],
        [("ASESORA:", True)],
        [
            (
                "DRA. CECILIA VÁSQUEZ MONDRAGÓN"
                if asesor_mayusculas
                else "Dra. Cecilia Vásquez Mondragón",
                True,
            )
        ],
    ]


def test_dos_autores_sin_negrita_y_con_mayusculas_minusculas_cumplen():
    resultado = _resultado(_caratula_dos_autores())
    assert resultado.passed, resultado.found


def test_segundo_autor_con_negrita_falla():
    """RN-02: la negrita del segundo autor ya no pasa inadvertida."""
    resultado = _resultado(_caratula_dos_autores(segundo=[("Blanca Esther Torres Ruiz", True)]))
    assert not resultado.passed
    assert "1 incumplen" in resultado.found, resultado.found
    assert "=1" in resultado.found, resultado.found


def test_orcid_en_negrita_y_mayusculas_no_cuenta_como_autor():
    """Las líneas ORCID se excluyen de negrita y de capitalidad."""
    paras = _caratula_dos_autores(orcid_negrita=True)
    paras[2] = [("ORCID: 0000-0002-1825-0097", True)]
    paras[4] = [("ORCID: 0000-0002-1694-233X", True)]
    resultado = _resultado(paras)
    assert resultado.passed, resultado.found


def test_orcid_desnudo_entre_parentesis_terminado_en_x_no_cuenta_como_autor():
    """Revisión de retblast: el código entre paréntesis no lleva la palabra ORCID.

    El manual lo pide entre paréntesis y `caratula_orcid` admite la `X` final
    (ISO 7064). Sin la exclusión por '(', ese run en negrita y con mayúscula
    se tomaba como un nombre y ponía la regla en rojo.
    """
    paras = _caratula_dos_autores()
    paras[2] = [("(0000-0002-1825-0097)", True)]
    paras[4] = [("(0000-0002-1694-233X)", True)]
    resultado = _resultado(paras)
    assert resultado.passed, resultado.found


def test_orcid_desnudo_no_exime_al_segundo_autor_en_negrita():
    """Excluir el ORCID no puede desactivar la negrita de los nombres."""
    paras = _caratula_dos_autores(segundo=[("Blanca Esther Torres Ruiz", True)])
    paras[2] = [("(0000-0002-1825-0097)", True)]
    paras[4] = [("(0000-0002-1694-233X)", True)]
    resultado = _resultado(paras)
    assert not resultado.passed
    assert "1 incumplen" in resultado.found, resultado.found


def test_nombre_partido_con_las_mayusculas_en_un_run_cumple():
    """La capitalidad se decide sobre el nombre completo, no por run."""
    resultado = _resultado(
        _caratula_dos_autores(segundo=[("BLANCA ESTHER ", False), ("Torres Ruiz", False)])
    )
    assert resultado.passed, resultado.found


def test_segundo_autor_todo_en_mayusculas_falla():
    """El criterio EVALUADO (altas y bajas) se aplica a cada autor."""
    resultado = _resultado(_caratula_dos_autores(segundo=[("BLANCA ESTHER TORRES RUIZ", False)]))
    assert not resultado.passed
    assert "incumplen" in resultado.found, resultado.found


def test_bloque_termina_antes_del_asesor():
    """El texto del asesor, aunque vaya en mayúsculas, no es un autor."""
    resultado = _resultado(_caratula_dos_autores(asesor_mayusculas=True))
    assert resultado.passed, resultado.found
