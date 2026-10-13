"""Tests de `validator/asistente.py` — Funcionalidad 2 (explicar y priorizar).

Sin `pytest-asyncio`: las corrutinas se ejecutan con `asyncio.run(...)`.
Todo se prueba con `StubLLM`; no hay red ni GPU en el CI.
"""

import asyncio
import json

import pytest

from validator.asistente import (
    ESQUEMA_EXPLICACION,
    ExplicacionYPrioridad,
    RespuestaIAInvalida,
    construir_prompt_explicar,
    explicar_y_priorizar,
    parse_explicacion,
)
from validator.llm import LLMError, StubLLM
from validator.models import RuleResult, Severity


def _fallo(rule_id: str = "margen_superior", **kwargs) -> RuleResult:
    base = {
        "rule_id": rule_id,
        "passed": False,
        "severity": Severity.ERROR,
        "message": "Margen superior incorrecto",
        "expected": "3 cm",
        "found": "2.5 cm",
        "location": "pág. 1",
        "cita": "el margen superior será de 3 cm",
    }
    base.update(kwargs)
    return RuleResult(**base)


def _respuesta_valida(**kwargs) -> str:
    data = {
        "explicaciones": [{"rule_id": "margen_superior", "explicacion": "causa"}],
        "prioridades": [
            {"orden": 1, "rule_id": "margen_superior", "razon": "impacto", "esfuerzo": "bajo"}
        ],
    }
    data.update(kwargs)
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------


def test_prompt_incluye_fallos_reglas_validas_y_tipo():
    system, user, esquema = construir_prompt_explicar(
        [_fallo("margen_superior"), _fallo("sangria_parrafo")],
        tipo_documento="tinv_cuantitativo",
    )

    assert isinstance(system, str) and system
    payload = json.loads(user)
    assert payload["tipo_documento"] == "tinv_cuantitativo"
    assert payload["reglas_validas"] == ["margen_superior", "sangria_parrafo"]
    assert payload["fallos"][0]["rule_id"] == "margen_superior"
    assert payload["fallos"][0]["esperado"] == "3 cm"
    assert esquema is ESQUEMA_EXPLICACION


def test_prompt_no_incluye_texto_de_tesis():
    # El `user` es solo el bloque de fallos: no hay campo libre de contenido.
    _, user, _ = construir_prompt_explicar([_fallo()])
    payload = json.loads(user)

    assert set(payload) == {"tipo_documento", "reglas_validas", "fallos"}


# ---------------------------------------------------------------------------
# parse_explicacion (torturas)
# ---------------------------------------------------------------------------


def test_parse_valido_ordena_prioridades():
    data = {
        "explicaciones": [{"rule_id": "a", "explicacion": "x"}],
        "prioridades": [
            {"orden": 2, "rule_id": "a", "razon": "r", "esfuerzo": "bajo"},
            {"orden": 1, "rule_id": "b", "razon": "r", "esfuerzo": "alto"},
        ],
    }

    salida = parse_explicacion(data, {"a", "b"}, modelo="stub")

    assert [p.orden for p in salida.prioridades] == [1, 2]
    assert salida.explicaciones[0].rule_id == "a"
    assert salida.modelo == "stub"


def test_parse_descarta_reglas_desconocidas():
    data = {
        "explicaciones": [{"rule_id": "fantasma", "explicacion": "x"}],
        "prioridades": [{"orden": 1, "rule_id": "fantasma", "razon": "r", "esfuerzo": "bajo"}],
    }

    salida = parse_explicacion(data, {"margen_superior"})

    assert salida.explicaciones == []
    assert salida.prioridades == []


@pytest.mark.parametrize(
    "data",
    [
        {"explicaciones": []},  # falta prioridades
        {"prioridades": []},  # falta explicaciones
        {"explicaciones": "no-es-lista", "prioridades": []},
        {"explicaciones": ["texto"], "prioridades": []},  # item no es objeto
        {"explicaciones": [{"rule_id": 1, "explicacion": "x"}], "prioridades": []},
        {
            "explicaciones": [],
            "prioridades": [{"orden": "uno", "rule_id": "a", "razon": "r", "esfuerzo": "bajo"}],
        },
        {
            "explicaciones": [],
            "prioridades": [{"orden": True, "rule_id": "a", "razon": "r", "esfuerzo": "bajo"}],
        },
        {
            "explicaciones": [],
            "prioridades": [{"orden": 1, "rule_id": "a", "razon": "r", "esfuerzo": "rápido"}],
        },
        {
            "explicaciones": [],
            "prioridades": [{"orden": 1, "rule_id": "a", "esfuerzo": "bajo"}],
        },  # falta razon
    ],
)
def test_parse_rechaza_estructuras_invalidas(data):
    with pytest.raises(RespuestaIAInvalida):
        parse_explicacion(data, {"a"})


# ---------------------------------------------------------------------------
# explicar_y_priorizar (orquestación con StubLLM)
# ---------------------------------------------------------------------------


def test_explicar_e2e_con_stub():
    stub = StubLLM(_respuesta_valida())

    salida = asyncio.run(explicar_y_priorizar([_fallo()], client=stub))

    assert isinstance(salida, ExplicacionYPrioridad)
    assert salida.explicaciones[0].rule_id == "margen_superior"
    assert salida.prioridades[0].esfuerzo == "bajo"
    assert salida.modelo == "stub"


def test_explicar_sin_fallos_no_llama_a_la_ia():
    stub = StubLLM(_respuesta_valida())

    salida = asyncio.run(explicar_y_priorizar([], client=stub))

    assert salida.explicaciones == []
    assert stub.llamadas == []


def test_explicar_reintenta_una_vez_ante_json_invalido():
    stub = StubLLM(["esto no es json", _respuesta_valida()])

    salida = asyncio.run(explicar_y_priorizar([_fallo()], client=stub))

    assert salida.explicaciones[0].rule_id == "margen_superior"
    assert len(stub.llamadas) == 2


def test_explicar_falla_tras_dos_respuestas_invalidas():
    stub = StubLLM("nunca-json")

    with pytest.raises(RespuestaIAInvalida):
        asyncio.run(explicar_y_priorizar([_fallo()], client=stub))

    assert len(stub.llamadas) == 2


def test_explicar_propaga_error_de_servicio_sin_reintentar():
    class ClienteCaido:
        modelo = "caido"

        async def chat(self, system, user, json_schema=None):
            raise LLMError("servicio caído")

        async def disponible(self):
            return False

    with pytest.raises(LLMError):
        asyncio.run(explicar_y_priorizar([_fallo()], client=ClienteCaido()))


def test_explicar_acepta_json_entre_vallas_markdown():
    contenido = "```json\n" + _respuesta_valida() + "\n```"
    stub = StubLLM(contenido)

    salida = asyncio.run(explicar_y_priorizar([_fallo()], client=stub))

    assert salida.explicaciones[0].rule_id == "margen_superior"


def test_explicar_solo_considera_fallos():
    # Una regla que pasa no debe llegar al prompt ni permitir explicaciones.
    stub = StubLLM(_respuesta_valida())
    aprobada = _fallo("margen_inferior", passed=True)

    asyncio.run(explicar_y_priorizar([aprobada], client=stub))

    assert stub.llamadas == []  # sin fallos, no se llama
