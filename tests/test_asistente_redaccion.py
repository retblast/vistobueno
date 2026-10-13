"""Tests de la Funcionalidad 5 — redacción de la respuesta (`asistente.redactar_respuesta`).

Sin `pytest-asyncio`: las corrutinas se ejecutan con `asyncio.run(...)`.
Todo con `StubLLM`; sin red ni GPU en el CI.
"""

import asyncio
import json

import pytest

from validator.asistente import (
    RedaccionRespuesta,
    RespuestaIAInvalida,
    construir_prompt_redactar,
    parse_redaccion,
    redactar_respuesta,
)
from validator.llm import LLMError, StubLLM
from validator.models import RuleResult, Severity


def _fallo(rule_id: str = "margen_superior", severity: Severity = Severity.ERROR) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        passed=False,
        severity=severity,
        message="Margen superior incorrecto",
        expected="3 cm",
        found="2.5 cm",
        location="pág. 1",
        cita="el margen superior será de 3 cm",
    )


def _respuesta_valida(**kwargs) -> str:
    data = {
        "texto": "Estimado estudiante: su tesis presenta observaciones de formato...",
        "asunto": "Observaciones de formato de su tesis",
    }
    data.update(kwargs)
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------


def test_prompt_ordena_errores_antes_que_avisos():
    system, user, esquema = construir_prompt_redactar(
        [_fallo("aviso", Severity.WARNING), _fallo("bloqueante", Severity.ERROR)],
        tipo_documento="tinv_cuantitativo",
    )

    assert isinstance(system, str) and system
    payload = json.loads(user)
    assert payload["tipo_documento"] == "tinv_cuantitativo"
    assert [f["rule_id"] for f in payload["fallos"]] == ["bloqueante", "aviso"]
    assert esquema is not None


def test_prompt_no_incluye_texto_de_tesis():
    _, user, _ = construir_prompt_redactar([_fallo()])
    payload = json.loads(user)

    assert set(payload) == {"tipo_documento", "fallos"}


# ---------------------------------------------------------------------------
# parse_redaccion (torturas)
# ---------------------------------------------------------------------------


def test_parse_valido():
    salida = parse_redaccion(json.loads(_respuesta_valida()), modelo="stub")

    assert isinstance(salida, RedaccionRespuesta)
    assert salida.asunto == "Observaciones de formato de su tesis"
    assert salida.texto.startswith("Estimado estudiante")
    assert salida.modelo == "stub"


@pytest.mark.parametrize(
    "data",
    [
        {"asunto": "solo asunto"},  # falta texto
        {"texto": "solo texto"},  # falta asunto
        {"texto": "", "asunto": "x"},  # texto vacío
        {"texto": "   ", "asunto": "x"},  # texto en blanco
        {"texto": "x", "asunto": ""},  # asunto vacío
        {"texto": 1, "asunto": "x"},  # texto no es str
        {"texto": "x", "asunto": None},  # asunto no es str
    ],
)
def test_parse_rechaza_estructuras_invalidas(data):
    with pytest.raises(RespuestaIAInvalida):
        parse_redaccion(data)


# ---------------------------------------------------------------------------
# redactar_respuesta (orquestación con StubLLM)
# ---------------------------------------------------------------------------


def test_redactar_e2e_con_stub():
    stub = StubLLM(_respuesta_valida())

    salida = asyncio.run(redactar_respuesta([_fallo()], client=stub))

    assert salida.modelo == "stub"
    assert salida.asunto
    assert len(stub.llamadas) == 1


def test_redactar_sin_fallos_no_llama_a_la_ia():
    stub = StubLLM(_respuesta_valida())

    salida = asyncio.run(redactar_respuesta([], client=stub))

    assert salida == RedaccionRespuesta(texto="", asunto="", modelo="stub")
    assert stub.llamadas == []


def test_redactar_reintenta_una_vez_ante_json_invalido():
    stub = StubLLM(["esto no es json", _respuesta_valida()])

    salida = asyncio.run(redactar_respuesta([_fallo()], client=stub))

    assert salida.asunto
    assert len(stub.llamadas) == 2


def test_redactar_falla_tras_dos_respuestas_invalidas():
    stub = StubLLM("nunca-json")

    with pytest.raises(RespuestaIAInvalida):
        asyncio.run(redactar_respuesta([_fallo()], client=stub))

    assert len(stub.llamadas) == 2


def test_redactar_propaga_error_de_servicio_sin_reintentar():
    class ClienteCaido:
        modelo = "caido"

        async def chat(self, system, user, json_schema=None):
            raise LLMError("servicio caído")

        async def disponible(self):
            return False

    with pytest.raises(LLMError):
        asyncio.run(redactar_respuesta([_fallo()], client=ClienteCaido()))


def test_redactar_acepta_json_entre_vallas_markdown():
    contenido = "```json\n" + _respuesta_valida() + "\n```"
    stub = StubLLM(contenido)

    salida = asyncio.run(redactar_respuesta([_fallo()], client=stub))

    assert salida.asunto
