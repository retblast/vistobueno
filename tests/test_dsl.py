"""Tests del DSL declarativo: autómatas, analizadores y compilador.

Verifica las piezas nuevas del motor sin depender de plantillas externas:
- DFA puro (reconocimiento de secuencias).
- Analizadores de hoja (XML, regex, lista, imagen).
- Compilador DSL (YAML -> analizadores -> RuleResult).
- Motor con formato DSL vs legacy (paridad de contrato).

Uso:
    pytest tests/test_dsl.py -v
"""

import tempfile
import zipfile
from pathlib import Path

from validator.automata import DFA, GramaticaEstructura, Transicion
from validator.compilador import CompilerDSL
from validator.engine import build_report, validate_docx
from validator.models import RuleResult

# ---------------------------------------------------------------------------
# Helpers: construir un DOCX mínimo en memoria
# ---------------------------------------------------------------------------

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _para(texto: str, estilo: str = "") -> str:
    pPr = ""
    if estilo:
        pPr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>'
    return f'<w:p>{pPr}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _docxml_headings(headings, cover="") -> str:
    """Construye document.xml con `headings` (list[str]) como Título 1 y
    opcionalmente un párrafo de portada que contiene `cover`."""
    paras = []
    if cover:
        paras.append(_para(cover))
    for h in headings:
        paras.append(_para(h, "Ttulo1"))
    paras.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>')
    body = "".join(paras)
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{body}</w:body></w:document>'
    )


def _make_docx(headings, cover="") -> str:
    """Escribe un DOCX mínimo en un archivo temporal y devuelve su ruta."""
    doc = _docxml_headings(headings, cover)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
    return path


# ---------------------------------------------------------------------------
# Tests: DFA puro
# ---------------------------------------------------------------------------


class TestDFA:
    def test_reconoce_secuencia_ok(self):
        dfa = DFA(
            estados=["__inicio__", "intro", "resultados"],
            transiciones=[
                Transicion("__inicio__", "intro", "INTRODUCCION"),
                Transicion("intro", "resultados", "RESULTADOS"),
            ],
            inicial="__inicio__",
            aceptacion=["resultados"],
        )
        ok, faltantes = dfa.reconocer(["PREAMBULO", "INTRODUCCION", "METODOS", "RESULTADOS"])
        assert ok
        assert faltantes == []

    def test_rechaza_secuencia_faltante(self):
        dfa = DFA(
            estados=["__inicio__", "intro", "resultados"],
            transiciones=[
                Transicion("__inicio__", "intro", "INTRODUCCION"),
                Transicion("intro", "resultados", "RESULTADOS"),
            ],
            inicial="__inicio__",
            aceptacion=["resultados"],
        )
        ok, faltantes = dfa.reconocer(["PREAMBULO", "INTRODUCCION"])
        assert not ok
        assert faltantes  # debe reportar qué faltó

    def test_greedy_no_retrocede(self):
        """Una vez reconocida una transición, el puntero no retrocede."""
        dfa = DFA(
            estados=["__inicio__", "a", "b"],
            transiciones=[
                Transicion("__inicio__", "a", "A"),
                Transicion("a", "b", "B"),
            ],
            inicial="__inicio__",
            aceptacion=["b"],
        )
        ok, _ = dfa.reconocer(["A", "A", "B"])
        assert ok

    def test_backtracking_no_cuelga_en_ambiguedad(self):
        """El modo backtracking explora interpretaciones sin colgarse."""
        dfa = DFA(
            estados=["__inicio__", "a", "b"],
            transiciones=[
                Transicion("__inicio__", "a", "X"),
                Transicion("a", "b", "X"),
            ],
            inicial="__inicio__",
            aceptacion=["b"],
            reconocimiento_backtracking=True,
        )
        ok, falt = dfa.reconocer(["X"])
        assert not ok
        assert isinstance(falt, list)

    def test_backtracking_secuencia_completa(self):
        dfa = DFA(
            estados=["__inicio__", "a", "b"],
            transiciones=[
                Transicion("__inicio__", "a", "A"),
                Transicion("a", "b", "B"),
            ],
            inicial="__inicio__",
            aceptacion=["b"],
            reconocimiento_backtracking=True,
        )
        ok, falt = dfa.reconocer(["PREAMBULO", "A", "B"])
        assert ok
        assert falt == []


# ---------------------------------------------------------------------------
# Tests: Gramática BNF
# ---------------------------------------------------------------------------


class TestGramatica:
    def test_secuencias_esperadas(self):
        g = GramaticaEstructura(
            reglas_sintacticas=[
                "TESIS → CARATULA INDICE INTRODUCCION CUERPO",
                "CUERPO → METODOLOGIA RESULTADOS CONCLUSIONES",
            ],
            terminales=[
                "CARATULA",
                "INDICE",
                "INTRODUCCION",
                "METODOLOGIA",
                "RESULTADOS",
                "CONCLUSIONES",
            ],
            no_terminales=["TESIS", "CUERPO"],
            inicio="TESIS",
        )
        secuencias = g.secuencias_esperadas()
        assert [
            "CARATULA",
            "INDICE",
            "INTRODUCCION",
            "METODOLOGIA",
            "RESULTADOS",
            "CONCLUSIONES",
        ] in secuencias

    def test_analizar_ok(self):
        g = GramaticaEstructura(
            reglas_sintacticas=["TESIS → INTRODUCCION RESULTADOS"],
            terminales=["INTRODUCCION", "RESULTADOS"],
            no_terminales=["TESIS"],
            inicio="TESIS",
        )
        ok, faltantes = g.analizar(["PREAMBULO", "INTRODUCCION", "RESULTADOS"])
        assert ok
        assert faltantes == []

    def test_analizar_falta_seccion(self):
        g = GramaticaEstructura(
            reglas_sintacticas=["TESIS → INTRODUCCION RESULTADOS"],
            terminales=["INTRODUCCION", "RESULTADOS"],
            no_terminales=["TESIS"],
            inicio="TESIS",
        )
        ok, faltantes = g.analizar(["INTRODUCCION"])
        assert not ok
        assert "RESULTADOS" in faltantes


# ---------------------------------------------------------------------------
# Tests: Compilador DSL
# ---------------------------------------------------------------------------


class TestCompiladorDSL:
    RULES_ATTR = {
        "namespaces": {"w": WNS},
        "reglas": [
            {
                "id": "papel_tamano",
                "tipo": "atributo_xml",
                "severidad": "error",
                "descripcion": "Tamaño A4",
                "valor_esperado": "210 x 297 mm",
                "atributo_xml": {
                    "parte": "document",
                    "xpath": "//w:sectPr[1]/w:pgSz",
                    "atributo": "@w:w",
                    "comparacion": "eq",
                    "esperado": "11906",
                },
            }
        ],
    }

    RULES_SECUENCIA = {
        "namespaces": {"w": WNS},
        "reglas": [
            {
                "id": "estructura_simple",
                "tipo": "secuencia",
                "severidad": "error",
                "descripcion": "Estructura mínima",
                "automata_secuencia": {
                    "estados": [
                        {"nombre": "introduccion", "patron": "INTRODUCCION"},
                        {"nombre": "resultados", "patron": "RESULTADOS"},
                    ]
                },
            }
        ],
    }

    RULES_GRAMATICA = {
        "namespaces": {"w": WNS},
        "reglas": [
            {
                "id": "estructura_gramatica",
                "tipo": "estructura",
                "severidad": "warning",
                "descripcion": "Estructura por gramática",
                "gramatica_estructura": {
                    "reglas_sintacticas": ["TESIS → INTRODUCCION RESULTADOS"],
                    "terminales": ["INTRODUCCION", "RESULTADOS"],
                    "no_terminales": ["TESIS"],
                    "inicio": "TESIS",
                },
            }
        ],
    }

    def test_compila_reglas_a_analizadores(self):
        compilado = CompilerDSL().compilar(self.RULES_ATTR)
        assert len(compilado) == 1
        assert compilado[0].rule["id"] == "papel_tamano"
        assert len(compilado[0].analizadores) == 1

    def test_atributo_xml_cumple(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            resultados = validate_docx(path, self.RULES_ATTR)
            assert len(resultados) == 1
            assert resultados[0].rule_id == "papel_tamano"
            assert resultados[0].passed is True
            assert resultados[0].severity.value == "error"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_secuencia_cumple(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            resultados = validate_docx(path, self.RULES_SECUENCIA)
            assert len(resultados) == 1
            assert resultados[0].passed is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_secuencia_no_cumple(self):
        path = _make_docx(headings=["INTRODUCCION"])
        try:
            resultados = validate_docx(path, self.RULES_SECUENCIA)
            assert resultados[0].passed is False
            assert "faltantes" in resultados[0].found
        finally:
            Path(path).unlink(missing_ok=True)

    def test_gramatica_cumple(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            resultados = validate_docx(path, self.RULES_GRAMATICA)
            assert len(resultados) == 1
            assert resultados[0].passed is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_caratula_por_parrafo(self):
        """La carátula se satisface con el primer párrafo de portada."""
        reglas = {
            "namespaces": {"w": WNS},
            "reglas": [
                {
                    "id": "estructura_con_caratula",
                    "tipo": "secuencia",
                    "severidad": "error",
                    "automata_secuencia": {
                        "estados": [
                            {"nombre": "caratula", "patron": "universidad"},
                            {"nombre": "resultados", "patron": "RESULTADOS"},
                        ]
                    },
                }
            ],
        }
        path = _make_docx(
            headings=["RESULTADOS"],
            cover="Universidad Nacional de Trujillo",
        )
        try:
            resultados = validate_docx(path, reglas)
            assert resultados[0].passed is True
        finally:
            Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests: contrato del motor (paridad DSL = legacy)
# ---------------------------------------------------------------------------


class TestContratoMotor:
    def test_validate_docx_devuelve_ruleresult(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            resultados = validate_docx(path, TestCompiladorDSL.RULES_ATTR)
            assert all(isinstance(r, RuleResult) for r in resultados)
            d = resultados[0].to_dict()
            assert set(d.keys()) == {
                "rule_id",
                "passed",
                "severity",
                "message",
                "expected",
                "found",
                "location",
                "fuente",
                "cita",
                "ficha",
            }
        finally:
            Path(path).unlink(missing_ok=True)

    def test_build_report_estructura(self):
        path = _make_docx(headings=["INTRODUCCION"])
        try:
            resultados = validate_docx(path, TestCompiladorDSL.RULES_SECUENCIA)
            reporte = build_report(resultados)
            assert set(reporte.keys()) == {"semaforo", "resultados", "resumen", "ficha"}
            assert reporte["semaforo"] == "rojo"
            assert reporte["resumen"]["total"] == 1
            assert reporte["resumen"]["fallidos_error"] == 1
        finally:
            Path(path).unlink(missing_ok=True)
