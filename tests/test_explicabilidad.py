"""Tests de explicabilidad determinista de los fallos (F6).

Cuando una regla de autómata (`automata_secuencia`/`automata_pila`) falla, el
`found` anexa la traza de estados recorrida para que el estudiante entienda
*dónde* se desvió el documento. La traza se humaniza con las etiquetas
`original`/`patron` de cada estado (`caratula` -> "Carátula") y omite el estado
inicial implícito `__inicio__`. Sin IA.

Uso:
    pytest tests/test_explicabilidad.py -v
"""

import tempfile
import zipfile
from pathlib import Path

from docx_factory import aplicar_mutacion, compilar_docx, configuracion_base

from validator.compilador import AutomataPila, _etiquetas_estados
from validator.engine import load_rules, validate_docx
from validator.extractor import extract

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

RAIZ = Path(__file__).resolve().parents[1]


def _para(texto: str, estilo: str = "") -> str:
    pPr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f'<w:p>{pPr}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _make_docx(headings: list[str]) -> str:
    paras = [_para(h, "Ttulo1") for h in headings]
    paras.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>')
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}"><w:body>{"".join(paras)}</w:body></w:document>'
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
    return path


def _regla_secuencia(estados: list[dict]) -> dict:
    return {
        "namespaces": {"w": WNS},
        "reglas": [
            {
                "id": "secuencia_test",
                "tipo": "secuencia",
                "severidad": "error",
                "descripcion": "Secuencia de prueba",
                "automata_secuencia": {
                    "normalizacion": ["mayusculas", "ignorar_indent"],
                    "estados": estados,
                },
            }
        ],
    }


ESTADOS = [
    {"nombre": "introduccion", "patron": "INTRODUCCION", "original": "Introducción"},
    {"nombre": "resultados", "patron": "RESULTADOS", "original": "Resultados"},
]


# ---------------------------------------------------------------------------
# Etiquetas de estado
# ---------------------------------------------------------------------------


class TestEtiquetasEstados:
    def test_prefiere_original_y_la_recorta(self):
        cfg = {
            "estados": [
                {"nombre": "el_problema", "patron": "EL PROBLEMA", "original": "  El Problema"}
            ]
        }
        assert _etiquetas_estados(cfg) == {"el_problema": "El Problema"}

    def test_cae_a_patron_sin_original(self):
        cfg = {"estados": [{"nombre": "resumen", "patron": "RESUMEN"}]}
        assert _etiquetas_estados(cfg) == {"resumen": "RESUMEN"}

    def test_cae_a_nombre_sin_patron_ni_original(self):
        cfg = {"estados": [{"nombre": "anexos"}]}
        assert _etiquetas_estados(cfg) == {"anexos": "anexos"}

    def test_sin_estados_devuelve_vacio(self):
        assert _etiquetas_estados({}) == {}
        assert _etiquetas_estados({"transiciones": [{"desde": "a", "hacia": "b"}]}) == {}


# ---------------------------------------------------------------------------
# Traza legible en el `found`
# ---------------------------------------------------------------------------


class TestTrazaLegible:
    def test_regla_que_falla_traduce_los_estados(self):
        path = _make_docx(["INTRODUCCION"])  # falta RESULTADOS
        try:
            res = validate_docx(path, _regla_secuencia(ESTADOS))[0]
        finally:
            Path(path).unlink(missing_ok=True)

        assert res.passed is False
        assert "reconoció=Introducción" in res.found
        assert "Resultados" in res.found  # faltante (el DFA no llegó al estado)
        assert "introduccion" not in res.found  # nombre de máquina traducido
        assert "__inicio__" not in res.found

    def test_regla_que_pasa_no_anexa_traza(self):
        path = _make_docx(["INTRODUCCION", "RESULTADOS"])
        try:
            res = validate_docx(path, _regla_secuencia(ESTADOS))[0]
        finally:
            Path(path).unlink(missing_ok=True)

        assert res.passed is True
        assert "reconoció=" not in res.found

    def test_estado_sin_etiqueta_conserva_el_nombre(self):
        estados = [
            {"nombre": "introduccion", "patron": "INTRODUCCION", "original": "Introducción"},
            {"nombre": "resultados", "patron": "RESULTADOS"},  # sin original -> patron
        ]
        path = _make_docx(["INTRODUCCION"])
        try:
            res = validate_docx(path, _regla_secuencia(estados))[0]
        finally:
            Path(path).unlink(missing_ok=True)
        assert "RESULTADOS" in res.found


class TestTrazaPDA:
    def test_pda_fallido_usuario_nombres_crudos_sin_romper(self):
        path = _make_docx(["CAP"])  # falta SEC
        try:
            e = extract(path)
            an = AutomataPila(
                {
                    "inicial": "a",
                    "aceptacion": ["c"],
                    "transiciones": [
                        {"desde": "a", "hacia": "b", "patron": "CAP", "push": "cap"},
                        {"desde": "b", "hacia": "c", "patron": "SEC", "pop": "cap"},
                    ],
                }
            )
            ok, _ = an.analizar(e)
        finally:
            Path(path).unlink(missing_ok=True)
        assert ok is False
        assert an.ultima_ruta == ["a", "b"]  # traza cruda disponible para el reporte


# ---------------------------------------------------------------------------
# Integración con la regla real de estructura
# ---------------------------------------------------------------------------


class TestIntegracionEstructura:
    def test_estructura_fallida_muestra_traza_humana(self):
        rules = load_rules(str(RAIZ / "reglas_unt.yaml"))
        cfg = configuracion_base()
        path = compilar_docx(aplicar_mutacion("estructura_tinv_cuantitativo", cfg))
        try:
            res = {r.rule_id: r for r in validate_docx(path, rules)}["estructura_tinv_cuantitativo"]
        finally:
            Path(path).unlink(missing_ok=True)

        assert res.passed is False
        assert "reconoció=" in res.found
        assert "El Problema" in res.found
        assert "el_problema" not in res.found
        assert "Situación problemática" in res.found  # faltante sin indentación
