"""Tests de `validator/llm.py` (Paso 0 del módulo de IA, diseño 16).

Sin `pytest-asyncio` en el entorno Nix: las corrutinas se ejecutan con
`asyncio.run(...)` dentro de tests síncronos.

El cliente real (`OllamaClient`) se prueba con `httpx.MockTransport`, sin red.
"""

import asyncio
import json

import httpx
import pytest

from validator.llm import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_S,
    LLMConfig,
    LLMError,
    LLMNoDisponible,
    OllamaClient,
    StubLLM,
    estado_ia,
    get_llm_client,
)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


def test_config_sin_entorno_no_habilita(monkeypatch):
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)

    config = LLMConfig.desde_entorno()

    assert config.url == ""
    assert config.model == DEFAULT_MODEL
    assert config.timeout_s == DEFAULT_TIMEOUT_S


def test_config_lee_variables_de_entorno(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "42")

    config = LLMConfig.desde_entorno()

    assert config.url == "http://127.0.0.1:11434"
    assert config.model == "qwen2.5:7b"
    assert config.timeout_s == 42.0


def test_config_timeout_invalido_usa_default(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT", "no-es-un-numero")

    assert LLMConfig.desde_entorno().timeout_s == DEFAULT_TIMEOUT_S


def test_config_modelo_vacio_usa_default(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "   ")

    assert LLMConfig.desde_entorno().model == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# get_llm_client
# ---------------------------------------------------------------------------


def test_get_llm_client_sin_url_lanza_no_disponible(monkeypatch):
    monkeypatch.delenv("OLLAMA_URL", raising=False)

    with pytest.raises(LLMNoDisponible):
        get_llm_client()


def test_get_llm_client_con_url_devuelve_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")

    cliente = get_llm_client()

    assert isinstance(cliente, OllamaClient)
    assert cliente.modelo == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# OllamaClient.chat (con MockTransport)
# ---------------------------------------------------------------------------


def _transport(datos: dict | None, status: int = 200):
    """Transport falso que devuelve `datos` y captura la última petición."""
    capturado: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["request"] = request
        if datos is None:
            return httpx.Response(status)
        return httpx.Response(status, json=datos)

    return httpx.MockTransport(handler), capturado


def test_ollama_chat_devuelve_contenido_y_arma_payload():
    transport, capturado = _transport({"message": {"content": '{"ok": true}'}})
    cliente = OllamaClient(LLMConfig(url="http://llm:11434", model="qwen2.5:3b"), transport)

    salida = asyncio.run(cliente.chat("sys", "usr", json_schema={"type": "object"}))

    assert salida == '{"ok": true}'
    peticion = capturado["request"]
    assert peticion.url.path == "/api/chat"
    cuerpo = json.loads(peticion.content)
    assert cuerpo["model"] == "qwen2.5:3b"
    assert cuerpo["stream"] is False
    assert cuerpo["format"] == "json"
    assert cuerpo["messages"][0] == {"role": "system", "content": "sys"}
    assert cuerpo["messages"][1] == {"role": "user", "content": "usr"}


def test_ollama_chat_sin_schema_no_pide_json():
    transport, capturado = _transport({"message": {"content": "texto"}})
    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), transport)

    asyncio.run(cliente.chat("sys", "usr", json_schema=None))

    cuerpo = json.loads(capturado["request"].content)
    assert "format" not in cuerpo


def test_ollama_chat_error_de_servicio():
    transport, _ = _transport(None, status=500)
    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), transport)

    with pytest.raises(LLMError):
        asyncio.run(cliente.chat("sys", "usr"))


def test_ollama_chat_respuesta_malformada():
    transport, _ = _transport({"algo": "sin message.content"})
    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), transport)

    with pytest.raises(LLMError):
        asyncio.run(cliente.chat("sys", "usr"))


def test_ollama_chat_error_de_red():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada", request=request)

    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), httpx.MockTransport(handler))

    with pytest.raises(LLMError):
        asyncio.run(cliente.chat("sys", "usr"))


# ---------------------------------------------------------------------------
# OllamaClient.disponible
# ---------------------------------------------------------------------------


def test_ollama_disponible_true():
    transport, _ = _transport({"models": []}, status=200)
    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), transport)

    assert asyncio.run(cliente.disponible()) is True


def test_ollama_disponible_false_si_servicio_no_responde():
    transport, _ = _transport(None, status=503)
    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), transport)

    assert asyncio.run(cliente.disponible()) is False


def test_ollama_disponible_false_si_falla_conexion():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin ruta", request=request)

    cliente = OllamaClient(LLMConfig(url="http://llm:11434"), httpx.MockTransport(handler))

    assert asyncio.run(cliente.disponible()) is False


# ---------------------------------------------------------------------------
# StubLLM
# ---------------------------------------------------------------------------


def test_stub_repite_una_sola_respuesta():
    stub = StubLLM("fija")

    assert asyncio.run(stub.chat("s", "u")) == "fija"
    assert asyncio.run(stub.chat("s", "u")) == "fija"
    assert stub.modelo == "stub"
    assert asyncio.run(stub.disponible()) is True


def test_stub_consume_lista_en_orden():
    stub = StubLLM(['{"a": 1}', '{"b": 2}'])

    assert asyncio.run(stub.chat("s", "u")) == '{"a": 1}'
    assert asyncio.run(stub.chat("s", "u")) == '{"b": 2}'


def test_stub_registra_llamadas():
    stub = StubLLM("x")
    esquema = {"type": "object"}

    asyncio.run(stub.chat("sys", "usr", json_schema=esquema))

    assert stub.llamadas == [("sys", "usr", esquema)]


def test_stub_sin_respuestas_lanza():
    stub = StubLLM([])

    with pytest.raises(LLMError):
        asyncio.run(stub.chat("s", "u"))


# ---------------------------------------------------------------------------
# estado_ia
# ---------------------------------------------------------------------------


def test_estado_ia_sin_url(monkeypatch):
    monkeypatch.delenv("OLLAMA_URL", raising=False)

    assert asyncio.run(estado_ia()) == {"disponible": False, "modelo": ""}


def test_estado_ia_disponible_con_cliente_inyectado():
    stub = StubLLM("x", modelo="qwen2.5:3b")

    assert asyncio.run(estado_ia(client=stub)) == {
        "disponible": True,
        "modelo": "qwen2.5:3b",
    }


def test_estado_ia_no_disponible_si_cliente_caido():
    transport, _ = _transport(None, status=503)
    cliente = OllamaClient(LLMConfig(url="http://llm:11434", model="qwen2.5:3b"), transport)

    assert asyncio.run(estado_ia(client=cliente)) == {"disponible": False, "modelo": ""}
