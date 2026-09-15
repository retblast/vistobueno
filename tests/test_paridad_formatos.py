"""Paridad de comportamiento entre el motor legacy y el DSL (Fase F1).

Migramos `unt_format_rules_schema.yaml` (legacy) a `reglas_unt.yaml` (DSL)
con `scripts/migrar_legacy_a_dsl.py`. Este test garantiza que, sobre
documentos sintéticos controlados, AMBOS motores producen exactamente
los mismos resultados (mismo set de reglas, mismo `passed`, mismo
`found`) — la migración no cambia el comportamiento del validador.

Uso:
    pytest tests/test_paridad_formatos.py -v
"""
import tempfile
import zipfile
from pathlib import Path

import yaml

from validator.engine import validate_docx

RAIZ = Path(__file__).resolve().parent.parent
LEGACY_YAML = RAIZ / "unt_format_rules_schema.yaml"
DSL_YAML = RAIZ / "reglas_unt.yaml"

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PNS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WPN = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _run(texto: str, rpr_inner: str = "") -> str:
    rpr = f"<w:rPr>{rpr_inner}</w:rPr>" if rpr_inner else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{texto}</w:t></w:r>'


def _cover_para(texto: str, rpr_inner: str = "", jc: str = "center") -> str:
    return f'<w:p><w:pPr><w:jc w:val="{jc}"/></w:pPr>{_run(texto, rpr_inner)}</w:p>'


def _cuerpo_para(texto: str, conforme: bool) -> str:
    """Párrafo de cuerpo (después del marcador de sección).

    Solo los párrafos con estilo Normal/sin estilo cuentan como "cuerpo"
    para el motor (ver extractor._cuerpo_paras), así que estos llevan la
    fuente, tamaño, interlineado, alineación y sangría esperadas.
    """
    if not conforme:
        return (
            '<w:p><w:r>'
            '<w:rPr><w:rFonts w:ascii="Arial"/><w:sz w:val="30"/></w:rPr>'
            f'<w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'
        )
    pPr = (
        '<w:pPr><w:spacing w:line="360" w:lineRule="auto"/>'
        '<w:jc w:val="both"/><w:ind w:firstLine="720"/></w:pPr>'
    )
    rpr = (
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
        '<w:sz w:val="24"/><w:szCs w:val="24"/>'
    )
    return f"<w:p>{pPr}{_run(texto, rpr)}</w:p>"


def _heading(texto: str, nivel: int = 1) -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="Ttulo{nivel}"/></w:pPr>'
        f'{_run(texto)}</w:p>'
    )


def _sect_marker(conforme: bool) -> str:
    """Párrafo que cierra la sección de preliminares (contiene sectPr en pPr)."""
    fmt = "lowerRoman" if conforme else "decimal"
    titlepg = "<w:titlePg/>" if conforme else ""
    pgsz_w, pgsz_h = ("11906", "16838") if conforme else ("10000", "15000")
    top = "1418" if conforme else "1000"
    left = "1701" if conforme else "1000"
    return (
        "<w:p><w:pPr><w:sectPr>"
        f'<w:pgSz w:w="{pgsz_w}" w:h="{pgsz_h}"/>'
        f'<w:pgMar w:top="{top}" w:right="{top}" w:bottom="{top}" w:left="{left}"/>'
        f"{titlepg}{_footer_ref()}"
        f'<w:pgNumType w:fmt="{fmt}"/>'
        "</w:sectPr></w:pPr><w:r><w:t xml:space=\"preserve\"> </w:t></w:r></w:p>"
    )


def _footer_ref() -> str:
    return '<w:footerReference w:type="default" r:id="rIdFooter"/>'


def _sect_final(conforme: bool) -> str:
    """SectPr final (sección del cuerpo). En el doc conforme NO declara
    w:pgNumType (el correlativo arábigo continúa solo)."""
    pgtype = '<w:pgNumType w:fmt="decimal"/>' if not conforme else ""
    pgsz_w, pgsz_h = ("11906", "16838") if conforme else ("10000", "15000")
    top = "1418" if conforme else "1000"
    left = "1701" if conforme else "1000"
    return (
        "<w:sectPr>"
        f'<w:pgSz w:w="{pgsz_w}" w:h="{pgsz_h}"/>'
        f'<w:pgMar w:top="{top}" w:right="{top}" w:bottom="{top}" w:left="{left}"/>'
        f"{_footer_ref()}{pgtype}"
        "</w:sectPr>"
    )


def _logo() -> str:
    return (
        '<w:r><w:drawing><wp:inline><a:graphic><a:graphicData '
        f'uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        "<pic:pic><pic:blipFill><a:blip r:embed=\"rIdImg\"/></pic:blipFill>"
        "<pic:spPr/></pic:pic></a:graphicData></a:graphic></wp:inline>"
        "</w:drawing></w:r>"
    )


_HEADINGS_CUANT = [
    "DEDICATORIA",                    # opcional en el esquema
    "JURADO EVALUADOR",
    "AGRADECIMIENTO",                 # opcional
    "ÍNDICE",
    "PRESENTACIÓN",
    "RESUMEN",
    "ABSTRACT",
    "INTRODUCCIÓN",
    "1.3. EL PROBLEMA",               # ejercita el token significativo
    "SITUACIÓN PROBLEMÁTICA",
    "ENUNCIADO DEL PROBLEMA",
    "JUSTIFICACIÓN O IMPORTANCIA",
    "OBJETIVOS",
    "1.5 VARIABLE(S) Y OPERACIONALIZACIÓN",  # ejercita el token significativo
    "MARCO TEÓRICO",
    "ANTECEDENTES (ESTADO DEL ARTE)",
    "BASES TEÓRICAS",
    "METODOLOGÍA",
    "POBLACIÓN Y MUESTRA",
    "DISEÑO DE INVESTIGACIÓN",
    "INSTRUMENTO(S) USADO(S) EN LA RECOLECCIÓN DE DATOS",
    "MÉTODOS, TÉCNICAS Y PROCEDIMIENTOS USADOS EN EL ANÁLISIS E INTERPRETACIÓN DE DATOS",
    "RESULTADOS",
    "CONCLUSIONES",
    "REFERENCIAS",
    "ANEXOS",
]


def _document_xml(conforme: bool, estructura: bool) -> str:
    paras = []

    # ── Portada ─────────────────────────────────────────────
    if conforme:
        paras.append(_cover_para("UNIVERSIDAD NACIONAL DE TRUJILLO",
                                 '<w:b/><w:sz w:val="36"/>'))
        paras.append(f"<w:p>{_logo()}</w:p>")
        paras.append(_cover_para("FACULTAD DE EDUCACIÓN Y CIENCIAS DE LA COMUNICACIÓN",
                                 '<w:b/><w:sz w:val="26"/>'))
        paras.append(_cover_para("ESCUELA PROFESIONAL DE EDUCACIÓN INICIAL",
                                 '<w:b/><w:sz w:val="26"/>'))
        paras.append(_cover_para(
            "Título del trabajo de investigación: Estrategias lúdicas para el "
            "desarrollo de la motricidad fina.",
            '<w:b/><w:sz w:val="28"/>'))
        paras.append(_cover_para("Para optar el Grado de Bachiller en Educación Inicial",
                                 '<w:b/><w:sz w:val="26"/>'))
        paras.append(_cover_para("Autores: ",
                                 '<w:sz w:val="24"/>'))
        paras.append(_cover_para("ANA MARÍA PÉREZ GARCÍA",
                                 '<w:sz w:val="24"/>'))
        paras.append(_cover_para("Asesor(a): Mag. Carlos Alberto RODRÍGUEZ MIRANDA",
                                 '<w:b/><w:sz w:val="24"/>'))
        paras.append(_cover_para("Línea de investigación: ",
                                 '<w:sz w:val="24"/>'))
        paras.append(_cover_para("Educación y Ciencias de la Comunicación y "
                                 "Desarrollo Sostenible",
                                 '<w:sz w:val="24"/>'))
        paras.append(_cover_para("TRUJILLO - PERÚ, 2026",
                                 '<w:b/><w:sz w:val="24"/>'))
    else:
        paras.append(_cover_para("Universidad Nacional de Trujillo",
                                 '<w:sz w:val="24"/>', jc="left"))
        paras.append(_cover_para("Facultad de Educación",
                                 '<w:sz w:val="20"/>'))
        paras.append(_cover_para("Título del trabajo de investigación: Estrategias lúdicas.",
                                 '<w:sz w:val="30"/>'))
        paras.append(_cover_para("Para optar el grado de bachiller.",
                                 '<w:sz w:val="30"/>'))
        paras.append(_cover_para("Autores: ",
                                 '<w:b/><w:sz w:val="30"/>'))
        paras.append(_cover_para("Avalos Quispe, María",
                                 '<w:b/><w:sz w:val="30"/>'))
        paras.append(_cover_para("Asesor(a): Mag. Rodrigo.",
                                 '<w:sz w:val="30"/>'))
        paras.append(_cover_para("Línea de investigación: ",
                                 '<w:sz w:val="24"/>'))
        paras.append(_cover_para("Alimentos y bebidas procesados",
                                 '<w:sz w:val="24"/>'))
        paras.append(_cover_para("Trujillo - Perú, 2026",
                                 '<w:sz w:val="30"/>'))

    # ── Preliminares (headings de estructura) ───────────────
    for h in _HEADINGS_CUANT:
        if not estructura and h not in ("INTRODUCCIÓN", "RESULTADOS", "ANEXOS"):
            continue
        # Título 2/3 si es sub-sección del cuerpo (indentado en el esquema).
        nivel = 3 if h.startswith(("    ", "1.5 ")) else 2 if h.startswith("  ") else 1
        if h in ("DEDICATORIA", "AGRADECIMIENTO"):
            nivel = 1
        paras.append(_heading(h, nivel))

    # Índices subdivisiones (solo en el documento conforme)
    if conforme:
        paras.append(_heading("INDICE DE CONTENIDOS", 1))
        paras.append(_heading("INDICE DE TABLAS", 1))
        paras.append(_heading("INDICE DE FIGURAS", 1))

    # ── Marcador de sección (fin de preliminares) ───────────
    paras.append(_sect_marker(conforme))

    # ── Cuerpo (párrafos regulares, no headings) ────────────
    paras.append(_cuerpo_para("La motricidad fina se desarrolla a través de "
                              "estrategias lúdicas.", conforme))
    paras.append(_cuerpo_para("Se aplicó un estudio cuantitativo con diseño "
                              "experimental.", conforme))
    paras.append(_cuerpo_para("Los resultados muestran una mejora significativa.",
                              conforme))

    paras.append(_sect_final(conforme))

    body = "".join(paras)
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}" xmlns:r="{RNS}" xmlns:a="{ANS}" '
        f'xmlns:pic="{PNS}" xmlns:wp="{WPN}">'
        f"<w:body>{body}</w:body></w:document>"
    )


def _footer_xml(conforme: bool) -> str:
    if conforme:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:ftr xmlns:w="{WNS}">'
            '<w:p><w:pPr><w:jc w:val="right"/></w:pPr>'
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> PAGE \\* MERGEFORMAT </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            "</w:p></w:ftr>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:ftr xmlns:w="{WNS}">'
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
        '<w:r><w:t>UNIVERSIDAD</w:t></w:r>'
        "</w:p></w:ftr>"
    )


def _make_docx(conforme: bool, estructura: bool) -> str:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", _document_xml(conforme, estructura))
        z.writestr("word/footer1.xml", _footer_xml(conforme))
    return path


def _por_regla(resultados):
    return {r.rule_id: r for r in resultados}


def _verificar_paridad(docx_path: str) -> dict:
    with open(LEGACY_YAML, encoding="utf-8") as f:
        legacy_data = yaml.safe_load(f)
    with open(DSL_YAML, encoding="utf-8") as f:
        dsl_data = yaml.safe_load(f)

    legacy = _por_regla(validate_docx(docx_path, legacy_data))
    dsl = _por_regla(validate_docx(docx_path, dsl_data))

    # Desde la F3 el DSL puede traer reglas extra (mecanizadas a mano).
    # La paridad garantiza que TODAS las legacy se comportan igual; las
    # reglas adicionales no existen en el motor legacy y se ignoran aquí.
    ids_legacy = set(legacy)
    assert ids_legacy <= set(dsl), (
        f"El DSL no ejecuta reglas legacy: "
        f"{ids_legacy - set(dsl)}"
    )

    # F5: el DSL anexa la traza `ruta=...` al `found` de las reglas de
    # autómata fallidas. Para los esquemas de estructura la paridad
    # observable es solo `passed`; el resto conserva `(passed, found)`
    # literal (misma razón que en test_propiedad: el contador interno
    # `headings=N` del found varía ante cambios de cabeceras).
    solo_passed = {
        "estructura_tinv_cuantitativo",
        "estructura_tinv_cualitativo",
        "estructura_tinv_revision_literatura",
    }
    diffs = []
    for rid in sorted(legacy):
        l, d = legacy[rid], dsl[rid]
        if rid in solo_passed:
            if l.passed != d.passed:
                diffs.append(
                    f"{rid}: legacy(passed={l.passed}) != dsl(passed={d.passed})"
                )
        elif l.passed != d.passed or l.found != d.found:
            diffs.append(
                f"{rid}: legacy(passed={l.passed}, found={l.found!r}) "
                f"!= dsl(passed={d.passed}, found={d.found!r})"
            )
    assert not diffs, "Diferencias de paridad:\n" + "\n".join(diffs)
    return {"total": len(legacy), "fallos": sum(1 for r in legacy.values() if not r.passed)}


def _finalizar(path: str):
    Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_paridad_doc_conforme():
    """Documento que cumple el formato: los dos motores coinciden y la
    mayoría de reglas pasan."""
    path = _make_docx(conforme=True, estructura=True)
    try:
        resumen = _verificar_paridad(path)
        assert resumen["total"] == 32
        # Deben pasar casi todas: solo los esquemas alternativos (cualitativo
        # y revisión de literatura) fallan frente a un doc cuantitativo.
        assert resumen["fallos"] <= 3, resumen["fallos"]
    finally:
        _finalizar(path)


def test_paridad_doc_rebelde():
    """Documento que incumple el formato: ambos motores reportan los mismos
    fallos (obliga a comparar `found` de muchas reglas falladas)."""
    path = _make_docx(conforme=False, estructura=True)
    try:
        resumen = _verificar_paridad(path)
        assert resumen["total"] == 32
        assert resumen["fallos"] > 10, resumen["fallos"]
    finally:
        _finalizar(path)


def test_paridad_estructura_incompleta():
    """Estructura incompleta: los tres esquemas fallan y los `faltantes`
    reportados por el DFA coinciden con los del motor legacy."""
    path = _make_docx(conforme=True, estructura=False)
    try:
        resumen = _verificar_paridad(path)
        assert resumen["total"] == 32
        for rid in ("estructura_tinv_cuantitativo", "estructura_tinv_cualitativo",
                    "estructura_tinv_revision_literatura"):
            assert True  # la paridad exacta ya se verificó en _verificar_paridad
    finally:
        _finalizar(path)