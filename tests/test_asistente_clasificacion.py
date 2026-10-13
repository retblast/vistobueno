"""Tests de la Funcionalidad 3 — clasificación asistida (`asistente.proponer_clasificacion`).

Sin `pytest-asyncio`: las corrutinas se ejecutan con `asyncio.run(...)`.
Todo con `StubLLM`; sin red ni GPU en el CI.
"""

import asyncio
import json

import pytest

from validator.asistente import (
    ClasificacionPropuesta,
    EvidenciaClasificacion,
    RespuestaIAInvalida,
    construir_prompt_clasificar,
    parse_clasificacion,
    proponer_clasificacion,
)
from validator.llm import LLMError, StubLLM

CANDIDATOS = ["tinv_cuantitativo", "tinv_cualitativo", "proyecto_cuantitativo"]


def _evidencia(**kwargs) -> EvidenciaClasificacion:
    base = {
        "estado": "sin_determinar",
        "tipos_candidatos": list(CANDIDATOS),
        "tipo_detectado": None,
        "detalle": "sin_determinado (ninguna firma alcanzó su mínimo)",
        "titulos": ["Introducción", "El Problema", "Metodología"],
    }
    base.update(kwargs)
    return EvidenciaClasificacion(**base)


def _respuesta_valida(**kwargs) -> str:
    data = {
        "tipo_propuesto": "tinv_cuantitativo",
        "confianza": 0.87,
        "justificacion": "La estructura coincide con el esquema cuantitativo.",
        "evidencia": ["Variable", "Población y muestra"],
        "alternativas": ["tinv_cualitativo"],
    }
    data.update(kwargs)
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------


def test_prompt_incluye_evidencia_y_catalogo():
    system, user, esquema = construir_prompt_clasificar(_evidencia())

    assert isinstance(system, str) and system
    payload = json.loads(user)
    assert payload["estado_deteccion"] == "sin_determinar"
    assert payload["tipo_detectado"] is None
    assert payload["titulos_detectados"] == ["Introducción", "El Problema", "Metodología"]
    assert payload["tipos_candidatos"] == CANDIDATOS
    assert esquema["properties"]["tipo_propuesto"]["enum"] == CANDIDATOS


def test_prompt_no_incluye_texto_de_tesis():
    # El `user` es solo la evidencia determinista: no hay campo libre de contenido.
    _, user, _ = construir_prompt_clasificar(_evidencia())
    payload = json.loads(user)

    assert set(payload) == {
        "estado_deteccion",
        "tipo_detectado",
        "detalle_deteccion",
        "titulos_detectados",
        "tipos_candidatos",
    }


# ---------------------------------------------------------------------------
# parse_clasificacion (torturas)
# ---------------------------------------------------------------------------


def test_parse_valido():
    salida = parse_clasificacion(json.loads(_respuesta_valida()), CANDIDATOS, modelo="stub")

    assert isinstance(salida, ClasificacionPropuesta)
    assert salida.tipo_propuesto == "tinv_cuantitativo"
    assert salida.confianza == pytest.approx(0.87)
    assert salida.alternativas == ["tinv_cualitativo"]
    assert salida.modelo == "stub"


def test_parse_rechaza_tipo_fuera_del_catalogo():
    data = json.loads(_respuesta_valida(tipo_propuesto="tipo_inventado"))

    with pytest.raises(RespuestaIAInvalida):
        parse_clasificacion(data, CANDIDATOS)


def test_parse_acota_confianza_a_rango():
    data = json.loads(_respuesta_valida(confianza=1.7))

    salida = parse_clasificacion(data, CANDIDATOS)

    assert salida.confianza == 1.0


def test_parse_filtra_evidencia_no_texto_y_alternativas_invalidas():
    data = json.loads(
        _respuesta_valida(
            evidencia=["ok", 42, None],
            alternativas=[
                "tinv_cualitativo",
                "tinv_cualitativo",  # duplicado
                "tinv_cuantitativo",  # es el propuesto
                "inventado",  # fuera del catálogo
            ],
        )
    )

    salida = parse_clasificacion(data, CANDIDATOS)

    assert salida.evidencia == ["ok"]
    assert salida.alternativas == ["tinv_cualitativo"]


@pytest.mark.parametrize(
    "data",
    [
        {"tipo_propuesto": "tinv_cuantitativo"},  # faltan campos
        {"tipo_propuesto": 1, "confianza": 0.5, "justificacion": "x"},
        {"tipo_propuesto": "tinv_cuantitativo", "confianza": "alta", "justificacion": "x"},
        {"tipo_propuesto": "tinv_cuantitativo", "confianza": True, "justificacion": "x"},
        {"tipo_propuesto": "tinv_cuantitativo", "confianza": 0.5, "justificacion": 1},
        {
            "tipo_propuesto": "tinv_cuantitativo",
            "confianza": 0.5,
            "justificacion": "x",
            "evidencia": "no-es-lista",
            "alternativas": [],
        },
        {
            "tipo_propuesto": "tinv_cuantitativo",
            "confianza": 0.5,
            "justificacion": "x",
            "evidencia": [],
            "alternativas": "no-es-lista",
        },
    ],
)
def test_parse_rechaza_estructuras_invalidas(data):
    with pytest.raises(RespuestaIAInvalida):
        parse_clasificacion(data, CANDIDATOS)


# ---------------------------------------------------------------------------
# proponer_clasificacion (orquestación con StubLLM)
# ---------------------------------------------------------------------------


def test_proponer_e2e_con_stub():
    stub = StubLLM(_respuesta_valida())

    salida = asyncio.run(proponer_clasificacion(_evidencia(), client=stub))

    assert salida.tipo_propuesto == "tinv_cuantitativo"
    assert salida.modelo == "stub"
    assert len(stub.llamadas) == 1


def test_proponer_reintenta_una_vez_ante_json_invalido():
    stub = StubLLM(["esto no es json", _respuesta_valida()])

    salida = asyncio.run(proponer_clasificacion(_evidencia(), client=stub))

    assert salida.tipo_propuesto == "tinv_cuantitativo"
    assert len(stub.llamadas) == 2


def test_proponer_falla_tras_dos_respuestas_invalidas():
    stub = StubLLM("nunca-json")

    with pytest.raises(RespuestaIAInvalida):
        asyncio.run(proponer_clasificacion(_evidencia(), client=stub))

    assert len(stub.llamadas) == 2


def test_proponer_propaga_error_de_servicio_sin_reintentar():
    class ClienteCaido:
        modelo = "caido"

        async def chat(self, system, user, json_schema=None):
            raise LLMError("servicio caído")

        async def disponible(self):
            return False

    with pytest.raises(LLMError):
        asyncio.run(proponer_clasificacion(_evidencia(), client=ClienteCaido()))


def test_proponer_acepta_json_entre_vallas_markdown():
    contenido = "```json\n" + _respuesta_valida() + "\n```"
    stub = StubLLM(contenido)

    salida = asyncio.run(proponer_clasificacion(_evidencia(), client=stub))

    assert salida.tipo_propuesto == "tinv_cuantitativo"


def test_proponer_sin_candidatos_es_error_de_uso():
    stub = StubLLM(_respuesta_valida())

    with pytest.raises(ValueError):
        asyncio.run(proponer_clasificacion(_evidencia(tipos_candidatos=[]), client=stub))

    assert stub.llamadas == []
