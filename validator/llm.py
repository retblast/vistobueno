"""Cliente LLM local para el módulo de IA de VistoBueno (diseño 16).

Base técnica del asistente del encargado: una interfaz `LLMClient` con dos
implementaciones reales de prueba:

- `OllamaClient`: habla con un servidor Ollama local por HTTP (`/api/chat`).
- `StubLLM`: respuestas deterministas, sin red, para la suite y el CI.

Reglas de diseño no negociables (docs/diseno/16_modulo_ia.md):

- **Nada de secretos**: `OLLAMA_URL` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT` son
  configuración, no credenciales; no afectan a `scripts/verificar_secretos.py`.
- **Bajo demanda**: el cliente nunca se invoca dentro de `POST /validar`.
- **La salida jamás toca el semáforo**: este módulo solo produce texto/JSON
  advisory; el motor determinista queda intacto.
- **Opt-in explícito**: si `OLLAMA_URL` no está definida, el módulo está
  deshabilitado (`LLMNoDisponible`), igual que la notificación SMTP.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

# Valor por defecto documentado del servicio Ollama (no habilita el módulo por
# sí solo: hace falta definir OLLAMA_URL).
DEFAULT_URL = "http://127.0.0.1:11434"

# Modelo por defecto: CPU-friendly (Qwen2.5 3B cuantizado Q4_K_M). En un
# servidor con GPU se cambia OLLAMA_MODEL a "qwen2.5:7b".
DEFAULT_MODEL = "qwen2.5:3b"

DEFAULT_TIMEOUT_S = 180.0

_API_CHAT = "/api/chat"
_API_TAGS = "/api/tags"


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class ErrorIA(Exception):
    """Error base del módulo de IA."""


class LLMNoDisponible(ErrorIA):
    """El módulo de IA no está configurado (falta OLLAMA_URL)."""


class LLMError(ErrorIA):
    """El servicio LLM no respondió o devolvió algo inválido."""


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMConfig:
    """Configuración del cliente LLM, leída del entorno.

    Atributos:
        url: URL base del servicio Ollama. Vacío = módulo deshabilitado.
        model: Nombre del modelo (p. ej. "qwen2.5:3b").
        timeout_s: Tiempo máximo de espera por respuesta, en segundos.
    """

    url: str = ""
    model: str = DEFAULT_MODEL
    timeout_s: float = DEFAULT_TIMEOUT_S

    @classmethod
    def desde_entorno(cls) -> LLMConfig:
        """Construye la configuración desde os.environ.

        La conversión del timeout es defensiva: un valor no numérico cae al
        valor por defecto en lugar de romper el arranque del módulo.
        """
        url = os.environ.get("OLLAMA_URL", "").strip()
        model = os.environ.get("OLLAMA_MODEL", "").strip() or DEFAULT_MODEL
        timeout_raw = os.environ.get("OLLAMA_TIMEOUT", "").strip()
        try:
            timeout_s = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT_S
        except ValueError:
            timeout_s = DEFAULT_TIMEOUT_S
        return cls(url=url, model=model, timeout_s=timeout_s)


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------


class LLMClient(Protocol):
    """Contrato mínimo que consume el módulo `asistente`."""

    @property
    def modelo(self) -> str:
        """Nombre del modelo en uso (para metadatos/estado)."""
        ...

    async def chat(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Devuelve la respuesta del modelo como texto.

        Si `json_schema` no es None, se le pide al modelo salida JSON.
        """
        ...

    async def disponible(self) -> bool:
        """True si el servicio responde y el modelo puede usarse."""
        ...


# ---------------------------------------------------------------------------
# Implementación real (Ollama)
# ---------------------------------------------------------------------------


class OllamaClient:
    """Cliente HTTP para un servidor Ollama local (API compatible OpenAI)."""

    def __init__(
        self,
        config: LLMConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        # `transport` solo se usa en los tests (httpx.MockTransport); en
        # producción queda None y httpx usa su transporte por defecto.
        self._transport = transport

    @property
    def modelo(self) -> str:
        return self.config.model

    def _nuevo_cliente(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=self.config.timeout_s)

    async def chat(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            # temperature 0 para acercar la salida al determinismo posible.
            "options": {"temperature": 0},
        }
        if json_schema is not None:
            # Ollama con format="json" devuelve el primer JSON válido; la
            # validación del esquema la hace el parser de cada feature.
            payload["format"] = "json"

        try:
            async with self._nuevo_cliente() as client:
                respuesta = await client.post(self.config.url + _API_CHAT, json=payload)
        except httpx.HTTPError as e:
            raise LLMError(f"no se pudo contactar el servicio LLM: {e}") from e

        if respuesta.status_code != 200:
            raise LLMError(f"el servicio LLM respondió con estado {respuesta.status_code}")

        try:
            data = respuesta.json()
            contenido = data["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise LLMError("el servicio LLM devolvió una respuesta con formato inesperado") from e

        if not isinstance(contenido, str):
            raise LLMError("el servicio LLM devolvió contenido que no es texto")
        return contenido

    async def disponible(self) -> bool:
        try:
            async with self._nuevo_cliente() as client:
                respuesta = await client.get(self.config.url + _API_TAGS)
        except httpx.HTTPError:
            return False
        return respuesta.status_code == 200


# ---------------------------------------------------------------------------
# Implementación de prueba (CI)
# ---------------------------------------------------------------------------


class StubLLM:
    """Cliente determinista para tests y CI; nunca toca la red.

    Si se configura una sola respuesta, `chat` la repite indefinidamente.
    Si se configura una lista, las consume en orden (útil para probar el
    reintento ante JSON inválido).
    """

    def __init__(self, respuestas: list[str] | str | None = None, modelo: str = "stub") -> None:
        if respuestas is None:
            respuestas = ["{}"]
        if isinstance(respuestas, str):
            respuestas = [respuestas]
        self._respuestas = list(respuestas)
        self._modelo = modelo
        # Registro de invocaciones para inspección en los tests.
        self.llamadas: list[tuple[str, str, dict[str, Any] | None]] = []

    @property
    def modelo(self) -> str:
        return self._modelo

    async def chat(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        self.llamadas.append((system, user, json_schema))
        if not self._respuestas:
            raise LLMError("StubLLM sin respuestas configuradas")
        if len(self._respuestas) == 1:
            return self._respuestas[0]
        return self._respuestas.pop(0)

    async def disponible(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Composición
# ---------------------------------------------------------------------------


def get_llm_client(config: LLMConfig | None = None) -> LLMClient:
    """Devuelve el cliente LLM según el entorno.

    Lanza `LLMNoDisponible` si no hay `OLLAMA_URL` configurada (módulo
    deshabilitado), patrón equivalente al de `notificacion.ConfigSMTP`.
    """
    cfg = config if config is not None else LLMConfig.desde_entorno()
    if not cfg.url:
        raise LLMNoDisponible(
            "módulo de IA no disponible: defina OLLAMA_URL para habilitarlo "
            "(p. ej. OLLAMA_URL=http://127.0.0.1:11434)"
        )
    return OllamaClient(cfg)


async def estado_ia(
    config: LLMConfig | None = None,
    *,
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """Estado del módulo de IA para el frontend (botón habilitado/deshabilitado).

    Nunca lanza: si el módulo está deshabilitado o el servicio no responde,
    devuelve `{"disponible": False, "modelo": ""}` (o el modelo conocido).
    """
    if client is None:
        try:
            client = get_llm_client(config)
        except LLMNoDisponible:
            return {"disponible": False, "modelo": ""}
    try:
        disponible = await client.disponible()
    except ErrorIA:
        disponible = False
    return {"disponible": disponible, "modelo": client.modelo if disponible else ""}
