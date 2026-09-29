"""Tests de la Fase F4: linter del DSL, cache de XPath y traza del autómata.

Cubre:
- Linter (`validator/dsl_check.py`): regex inválida, `comparacion` sin
  `esperado`, estados inalcanzables, ciclos épsilon y el guard de que
  `reglas_unt.yaml` pasa el linter en carga.
- Cache de consultas XPath en `ExtractedDocx` (evaluar una sola vez por
  documento + `contexto` cuerpo).
- Traza del autómata: `ruta_estados` en DFA/PDA y `ultima_ruta` en los
  analizadores de secuencia/pila.

Uso:
    pytest tests/test_f4_ingenieria.py -v
"""

import tempfile
import zipfile
from pathlib import Path

import pytest

from validator.automata import DFA, PDA, Transicion, TransicionPDA
from validator.compilador import AutomataPila, AutomataSecuencia, CompilerDSL
from validator.dsl_check import DSLValidationError, linter
from validator.engine import load_rules, validate_docx
from validator.extractor import extract

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

RAIZ = f"{Path(__file__).resolve().parent.parent}"


def _para(texto: str, estilo: str = "") -> str:
    pPr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f'<w:p>{pPr}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _make_docx(headings, cover="") -> str:
    paras = []
    if cover:
        paras.append(_para(cover))
    for h in headings:
        paras.append(_para(h, "Ttulo1"))
    paras.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>')
    body = "".join(paras)
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{body}</w:body></w:document>'
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
    return path


def _reglas_de(seccion, cfg, **extra):
    regla = {
        "id": extra.pop("id", "regla_f4"),
        "tipo": extra.pop("tipo", "atributo_xml"),
        "severidad": "error",
        "descripcion": "regla de test F4",
        seccion: cfg,
    }
    regla.update(extra)
    return {"namespaces": {"w": WNS}, "reglas": [regla]}


# ---------------------------------------------------------------------------
# Linter
# ---------------------------------------------------------------------------


class TestLinter:
    def test_reglas_unt_pasan_linter(self):
        rules = load_rules(f"{RAIZ}/reglas_unt.yaml")
        assert linter(rules) == []

    def test_reglas_dsl_ejemplo_pasan_linter(self):
        rules = load_rules(f"{RAIZ}/reglas_dsl_ejemplo.yaml")
        assert linter(rules) == []

    def test_regex_invalida_detectada(self):
        data = _reglas_de("patron_texto", {"patron": "("})
        hallazgos = linter(data)
        assert hallazgos
        assert all("regex inválida" in h for h in hallazgos)

    def test_regex_invalida_en_estado_de_automata(self):
        data = _reglas_de(
            "automata_secuencia",
            {"estados": [{"nombre": "intro", "patron": "("}]},
            tipo="secuencia",
        )
        assert any("regex inválida" in h for h in linter(data))

    def test_comparacion_sin_esperado(self):
        data = _reglas_de(
            "atributo_xml",
            {"parte": "document", "xpath": "//w:pgSz", "comparacion": "eq"},
        )
        assert any("requiere 'esperado'" in h for h in linter(data))

    def test_comparacion_sin_atributo(self):
        data = _reglas_de(
            "atributo_xml",
            {"parte": "document", "xpath": "//w:pgSz", "comparacion": "eq", "esperado": "11906"},
        )
        assert any("requiere 'atributo'" in h for h in linter(data))

    def test_estados_inalcanzables_en_pda(self):
        cfg = {
            "inicial": "a",
            "aceptacion": ["z"],
            "transiciones": [
                {"desde": "a", "hacia": "b", "patron": "X"},
                {"desde": "c", "hacia": "d", "patron": "Y"},
            ],
        }
        data = _reglas_de("automata_pila", cfg, tipo="estructura")
        assert any("estados inalcanzables" in h for h in linter(data))
        assert any("aceptación inalcanzable" in h for h in linter(data))

    def test_ciclo_epsilon_en_pda(self):
        cfg = {
            "inicial": "a",
            "aceptacion": ["b"],
            "transiciones": [
                {"desde": "a", "hacia": "a", "patron": "", "consumir": False},
                {"desde": "a", "hacia": "b", "patron": "X"},
            ],
        }
        data = _reglas_de("automata_pila", cfg, tipo="estructura")
        assert any("ciclo de transiciones épsilon" in h for h in linter(data))

    def test_estados_todos_opcionales(self):
        data = _reglas_de(
            "automata_secuencia",
            {
                "estados": [
                    {"nombre": "a", "patron": "A", "opcional": True},
                    {"nombre": "b", "patron": "B", "opcional": True},
                ]
            },
            tipo="secuencia",
        )
        assert any("todos los estados son opcionales" in h for h in linter(data))

    def test_compilar_levanta_error_de_carga(self):
        data = _reglas_de("patron_texto", {"patron": "("})
        with pytest.raises(DSLValidationError):
            CompilerDSL().compilar(data)

    def test_linter_desactivable_al_compilar(self):
        data = _reglas_de("patron_texto", {"patron": "("})
        # Con linter=False se compila igual (el error se descubre en runtime,
        # como ocurría antes de F4).
        compilado = CompilerDSL().compilar(data, linter=False)
        assert len(compilado) == 1


# ---------------------------------------------------------------------------
# Cache de XPath
# ---------------------------------------------------------------------------


class TestCacheXPath:
    def test_misma_consulta_devuelve_objeto_cacheado(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            e = extract(path)
            n1 = e.xpath("document", "//w:body/w:p", "todos")
            n2 = e.xpath("document", "//w:body/w:p", "todos")
            assert n1 is n2
            # Consultas distintas (contexto o xpath) generan claves propias.
            e.xpath("document", "//w:body/w:p", "cuerpo")
            e.xpath("document", "//w:sectPr", "todos")
            assert len(e._cache) == 3
        finally:
            Path(path).unlink(missing_ok=True)

    def test_analizadores_comparten_cache(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            e = extract(path)
            cfg = {
                "parte": "document",
                "contexto": "todos",
                "xpath": "//w:body/w:p",
            }
            from validator.analizadores import AnalizadorXML

            a1 = AnalizadorXML({**cfg, "comparacion": "exists"})
            a2 = AnalizadorXML({**cfg, "comparacion": "exists"})
            ok1, _ = a1.analizar(e)
            ok2, _ = a2.analizar(e)
            assert ok1 and ok2
            assert len(e._cache) == 1
        finally:
            Path(path).unlink(missing_ok=True)

    def test_parte_inexistente_levanta_error(self):
        path = _make_docx(headings=["INTRODUCCION"])
        try:
            e = extract(path)
            with pytest.raises(ValueError):
                e.xpath("footer", "//w:t", "todos")
        finally:
            Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Traza del autómata
# ---------------------------------------------------------------------------


class TestTraza:
    def _dfa(self):
        return DFA(
            estados=["__inicio__", "intro", "resultados"],
            transiciones=[
                Transicion("__inicio__", "intro", "INTRODUCCION"),
                Transicion("intro", "resultados", "RESULTADOS"),
            ],
            inicial="__inicio__",
            aceptacion=["resultados"],
        )

    def test_dfa_ruta_estados_aceptado(self):
        dfa = self._dfa()
        ok, _ = dfa.reconocer(["PREAMBULO", "INTRODUCCION", "METODOS", "RESULTADOS"])
        assert ok
        assert dfa.ruta_estados == ["__inicio__", "intro", "resultados"]

    def test_dfa_ruta_estados_rechazado(self):
        dfa = self._dfa()
        ok, _ = dfa.reconocer(["PREAMBULO", "INTRODUCCION"])
        assert not ok
        assert dfa.ruta_estados[-1] == "intro"

    def test_dfa_backtracking_ruta(self):
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
        ok, _ = dfa.reconocer(["PREAMBULO", "A", "B"])
        assert ok
        assert dfa.ruta_estados == ["__inicio__", "a", "b"]

    def test_pda_ruta_estados(self):
        pda = PDA(
            estados=["a", "b", "c"],
            transiciones=[
                TransicionPDA("a", "b", "CAP", push="cap"),
                TransicionPDA("b", "c", "SEC", pop="cap"),
            ],
            inicial="a",
            aceptacion=["c"],
        )
        ok, _ = pda.reconocer(["CAP", "SEC"])
        assert ok
        assert pda.ruta_estados == ["a", "b", "c"]

    def test_automatasecuencia_ultima_ruta(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            e = extract(path)
            an = AutomataSecuencia(
                {
                    "estados": [
                        {"nombre": "introduccion", "patron": "INTRODUCCION"},
                        {"nombre": "resultados", "patron": "RESULTADOS"},
                    ]
                }
            )
            ok, _ = an.analizar(e)
            assert ok
            assert an.ultima_ruta == ["__inicio__", "introduccion", "resultados"]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_automatapila_ultima_ruta(self):
        cfg = {
            "inicial": "a",
            "aceptacion": ["c"],
            "transiciones": [
                {"desde": "a", "hacia": "b", "patron": "CAP", "push": "cap"},
                {"desde": "b", "hacia": "c", "patron": "SEC", "pop": "cap"},
            ],
        }
        path = _make_docx(headings=["CAP", "SEC"])
        try:
            e = extract(path)
            an = AutomataPila(cfg)
            ok, _ = an.analizar(e)
            assert ok
            assert an.ultima_ruta == ["a", "b", "c"]
        finally:
            Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Integración: el linter no rompe el motor y reglas_unt sigue validando.
# ---------------------------------------------------------------------------


class TestIntegracion:
    def test_validate_docx_corre_con_linter_activo(self):
        rules = load_rules(f"{RAIZ}/reglas_unt.yaml")
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            resultados = validate_docx(path, rules)
            # 48 del YAML + 1 centinela: docx mínimo sin clasificar -> el paso
            # 6 agrega `tipo_documento_no_determinado`.
            assert len(resultados) == 49
        finally:
            Path(path).unlink(missing_ok=True)
