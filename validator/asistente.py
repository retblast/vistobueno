"""Asistente del encargado — módulo de IA (diseño 16).

- **Funcionalidad 2** — Explicación y priorización del diagnóstico
  (`explicar_y_priorizar`): toma las reglas fallidas y le pide al LLM que
  explique y ordene las correcciones.
- **Funcionalidad 3** — Clasificación asistida del tipo documental
  (`proponer_clasificacion`): cuando la heurística no pudo fijar el tipo
  (`sin_determinar`/`contradictorio`/sin estructura), el LLM propone uno y el
  encargado confirma o corrige (human-in-the-loop).
- **Funcionalidad 5** — Redacción de la respuesta al estudiante
  (`redactar_respuesta`): genera el borrador editable de la observación a
  partir del reporte.

Todo es **advisory**: nunca produce un `RuleResult` ni toca el semáforo
(principio P1 del diseño). La IA **no lee la tesis**: solo recibe el bloque de
fallos (Func 2) o la evidencia que la heurística ya extrajo (Func 3). Eso
protege la privacidad y abarata el cómputo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .llm import LLMClient
from .models import RuleResult, Severity

# Número máximo de intentos ante una respuesta no interpretable (1 reintento).
MAX_INTENTOS = 2

ESFUERZOS_VALIDOS = frozenset({"bajo", "medio", "alto"})


class RespuestaIAInvalida(Exception):
    """La IA no devolvió el JSON esperado ni siquiera tras el reintento."""


# ---------------------------------------------------------------------------
# Modelos advisory (internos del motor; I1 los mapea a DTOs Pydantic)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Explicacion:
    """Explicación en lenguaje llano de por qué falla una regla."""

    rule_id: str
    explicacion: str


@dataclass(frozen=True)
class Prioridad:
    """Orden recomendado de corrección de un fallo."""

    orden: int
    rule_id: str
    razon: str
    esfuerzo: str


@dataclass(frozen=True)
class ExplicacionYPrioridad:
    """Salida advisory de la Funcionalidad 2 (no interviene en el semáforo)."""

    explicaciones: list[Explicacion]
    prioridades: list[Prioridad]
    modelo: str = ""


# ---------------------------------------------------------------------------
# Esquema JSON esperado del modelo
# ---------------------------------------------------------------------------

ESQUEMA_EXPLICACION: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explicaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "explicacion": {"type": "string"},
                },
                "required": ["rule_id", "explicacion"],
            },
        },
        "prioridades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "orden": {"type": "integer"},
                    "rule_id": {"type": "string"},
                    "razon": {"type": "string"},
                    "esfuerzo": {"type": "string", "enum": ["bajo", "medio", "alto"]},
                },
                "required": ["orden", "rule_id", "razon", "esfuerzo"],
            },
        },
    },
    "required": ["explicaciones", "prioridades"],
}

_SYSTEM_PROMPT = """\
Eres un asistente técnico del personal del repositorio de tesis de la FECyC \
(Universidad Nacional de Trujillo). Recibirás, en JSON, la lista de reglas de \
formato que NO se cumplieron en una tesis, y debes ayudar al encargado a \
interpretarlas y priorizar su corrección.

Reglas estrictas:
- Usa EXCLUSIVAMENTE los fallos de la lista; no inventes observaciones ni \
reglas que no aparezcan.
- No decides si la tesis se aprueba: el semáforo es determinista y ajeno a ti.
- Responde en español y SOLO con un objeto JSON válido, sin texto adicional.
- Formato exacto:
  {"explicaciones": [{"rule_id": "...", "explicacion": "..."}],
   "prioridades": [{"orden": 1, "rule_id": "...", "razon": "...",
                    "esfuerzo": "bajo"}]}
- "explicacion": causa probable y qué significa para la entrega, en lenguaje llano.
- "prioridades": orden de corrección (1 = primero), por impacto y esfuerzo.
- Cada "rule_id" debe pertenecer a la lista de fallos.\
"""


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------


def _fallo_a_dict(fallo: RuleResult) -> dict[str, Any]:
    return {
        "rule_id": fallo.rule_id,
        "severidad": fallo.severity.value,
        "mensaje": fallo.message,
        "esperado": fallo.expected,
        "encontrado": fallo.found,
        "referencia": fallo.location,
        "cita": fallo.cita,
    }


def construir_prompt_explicar(
    fallidos: list[RuleResult],
    tipo_documento: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Arma (system, user, json_schema) para la Funcionalidad 2.

    El `user` es solo el bloque de fallos (nunca el texto de la tesis).
    """
    contenido = {
        "tipo_documento": tipo_documento,
        "reglas_validas": sorted({fallo.rule_id for fallo in fallidos}),
        "fallos": [_fallo_a_dict(fallo) for fallo in fallidos],
    }
    user = json.dumps(contenido, ensure_ascii=False, indent=2)
    return _SYSTEM_PROMPT, user, ESQUEMA_EXPLICACION


# ---------------------------------------------------------------------------
# Parseo y validación de la respuesta
# ---------------------------------------------------------------------------


def _extraer_json(crudo: str) -> dict[str, Any]:
    """Extrae un objeto JSON del texto devuelto por el modelo.

    Aunque Ollama con `format="json"` devuelve JSON puro, se tolera que el
    modelo envuelva la respuesta en vallas Markdown (```json ... ```).
    """
    texto = crudo.strip()
    if texto.startswith("```"):
        _, _, resto = texto.partition("\n")
        texto = resto if resto else texto
        if texto.rstrip().endswith("```"):
            texto = texto.rstrip()[:-3]
        texto = texto.strip()

    try:
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        raise RespuestaIAInvalida(f"la IA no devolvió JSON válido: {e}") from e
    if not isinstance(data, dict):
        raise RespuestaIAInvalida("se esperaba un objeto JSON en la respuesta de la IA")
    return data


def parse_explicacion(
    data: dict[str, Any],
    rule_ids_validos: set[str],
    modelo: str = "",
) -> ExplicacionYPrioridad:
    """Valida y normaliza la respuesta del modelo al modelo advisory.

    Descarta silenciosamente las entradas cuyo `rule_id` no esté entre los
    fallos reales: la IA no puede introducir observaciones inventadas.
    Lanza `RespuestaIAInvalida` si la estructura no es la esperada.
    """
    explicaciones_raw = data.get("explicaciones")
    prioridades_raw = data.get("prioridades")
    if not isinstance(explicaciones_raw, list) or not isinstance(prioridades_raw, list):
        raise RespuestaIAInvalida("faltan las listas 'explicaciones' y/o 'prioridades'")

    explicaciones: list[Explicacion] = []
    for item in explicaciones_raw:
        if not isinstance(item, dict):
            raise RespuestaIAInvalida("una 'explicacion' no es un objeto JSON")
        rule_id = item.get("rule_id")
        explicacion = item.get("explicacion")
        if not isinstance(rule_id, str) or not isinstance(explicacion, str):
            raise RespuestaIAInvalida("una 'explicacion' tiene campos inválidos")
        if rule_id not in rule_ids_validos:
            continue
        explicaciones.append(Explicacion(rule_id=rule_id, explicacion=explicacion))

    prioridades: list[Prioridad] = []
    for item in prioridades_raw:
        if not isinstance(item, dict):
            raise RespuestaIAInvalida("una 'prioridad' no es un objeto JSON")
        orden = item.get("orden")
        rule_id = item.get("rule_id")
        razon = item.get("razon")
        esfuerzo = item.get("esfuerzo")
        if not isinstance(orden, int) or isinstance(orden, bool):
            raise RespuestaIAInvalida("una 'prioridad' tiene 'orden' inválido")
        if not isinstance(rule_id, str) or not isinstance(razon, str):
            raise RespuestaIAInvalida("una 'prioridad' tiene campos inválidos")
        if not isinstance(esfuerzo, str) or esfuerzo not in ESFUERZOS_VALIDOS:
            raise RespuestaIAInvalida("una 'prioridad' tiene 'esfuerzo' inválido")
        if rule_id not in rule_ids_validos:
            continue
        prioridades.append(Prioridad(orden=orden, rule_id=rule_id, razon=razon, esfuerzo=esfuerzo))

    prioridades.sort(key=lambda p: p.orden)
    return ExplicacionYPrioridad(
        explicaciones=explicaciones,
        prioridades=prioridades,
        modelo=modelo,
    )


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------


async def explicar_y_priorizar(
    resultados: list[RuleResult],
    *,
    client: LLMClient,
    tipo_documento: str | None = None,
) -> ExplicacionYPrioridad:
    """Explica y prioriza los fallos usando el cliente LLM dado.

    - Si no hay fallos, no llama a la IA (devuelve una salida vacía).
    - Ante una respuesta no interpretable, reintenta una vez (MAX_INTENTOS).
    - `LLMError` (servicio caído) se propaga sin consumir el reintento.
    """
    fallidos = [r for r in resultados if not r.passed]
    rule_ids = {r.rule_id for r in fallidos}
    if not fallidos:
        return ExplicacionYPrioridad(explicaciones=[], prioridades=[], modelo=client.modelo)

    system, user, esquema = construir_prompt_explicar(fallidos, tipo_documento)

    ultimo_error: RespuestaIAInvalida | None = None
    for _ in range(MAX_INTENTOS):
        crudo = await client.chat(system, user, json_schema=esquema)
        try:
            data = _extraer_json(crudo)
            return parse_explicacion(data, rule_ids, modelo=client.modelo)
        except RespuestaIAInvalida as e:
            ultimo_error = e

    raise RespuestaIAInvalida(f"la IA no devolvió un formato interpretable: {ultimo_error}")


# ---------------------------------------------------------------------------
# Funcionalidad 3 — Clasificación asistida del tipo documental (diseño 16, §6.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenciaClasificacion:
    """Evidencia determinista con la que la IA propone un tipo documental.

    La arma el llamador (la API) a partir del resultado de
    `deteccion_tipo_documento`; **no** incluye el texto de la tesis, solo lo
    que la heurística ya extrajo (privacidad, P4 del diseño).

    Atributos:
        estado: "sin_determinar", "contradictorio" o "sin_estructura".
        tipos_candidatos: catálogo de tipos entre los que elegir (obligatorio).
        tipo_detectado: el tipo que publicó la heurística, si alguno.
        detalle: el `found` de la detección (firmas buscadas / declaración).
        titulos: títulos detectados en el documento (evidencia estructural).
    """

    estado: str
    tipos_candidatos: list[str]
    tipo_detectado: str | None = None
    detalle: str = ""
    titulos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClasificacionPropuesta:
    """Propuesta advisory de tipo documental (Funcionalidad 3).

    Solo sirve para que el encargado confirme o corrija: la IA propone, el
    humano decide (human-in-the-loop, P2 del diseño). Nunca cambia el tipo por
    sí sola.
    """

    tipo_propuesto: str
    confianza: float
    justificacion: str
    evidencia: list[str]
    alternativas: list[str]
    modelo: str = ""


def _esquema_clasificacion(tipos_candidatos: list[str]) -> dict[str, Any]:
    """Esquema JSON de la Func 3, con el catálogo de tipos como `enum`."""
    return {
        "type": "object",
        "properties": {
            "tipo_propuesto": {"type": "string", "enum": list(tipos_candidatos)},
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
            "justificacion": {"type": "string"},
            "evidencia": {"type": "array", "items": {"type": "string"}},
            "alternativas": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "tipo_propuesto",
            "confianza",
            "justificacion",
            "evidencia",
            "alternativas",
        ],
    }


_SYSTEM_PROMPT_CLASIFICAR = """\
Eres un asistente técnico del personal del repositorio de tesis de la FECyC \
(Universidad Nacional de Trujillo). La detección automática del tipo de \
documento no pudo fijarlo y debes proponer el tipo más probable para que el \
encargado lo confirme o lo corrija.

Reglas estrictas:
- Propón EXCLUSIVAMENTE uno de los tipos de "tipos_candidatos"; no inventes \
tipos nuevos.
- Básate SOLO en la evidencia recibida (declaración del Anexo 10, firmas \
buscadas, títulos detectados); no supongas contenido que no aparezca.
- No decides la validación: el semáforo es determinista y ajeno a ti; tu \
propuesta solo asiste al encargado.
- Responde en español y SOLO con un objeto JSON válido, sin texto adicional.
- Formato exacto:
  {"tipo_propuesto": "...", "confianza": 0.0, "justificacion": "...",
   "evidencia": ["..."], "alternativas": ["..."]}
- "confianza": número entre 0 y 1.
- "justificacion": por qué ese tipo, en lenguaje llano.
- "alternativas": otros tipos plausibles del catálogo, del más al menos probable.\
"""


def construir_prompt_clasificar(
    evidencia: EvidenciaClasificacion,
) -> tuple[str, str, dict[str, Any]]:
    """Arma (system, user, json_schema) para la Funcionalidad 3.

    El `user` es solo la evidencia determinista (nunca el texto de la tesis).
    """
    contenido = {
        "estado_deteccion": evidencia.estado,
        "tipo_detectado": evidencia.tipo_detectado,
        "detalle_deteccion": evidencia.detalle,
        "titulos_detectados": list(evidencia.titulos),
        "tipos_candidatos": list(evidencia.tipos_candidatos),
    }
    user = json.dumps(contenido, ensure_ascii=False, indent=2)
    return _SYSTEM_PROMPT_CLASIFICAR, user, _esquema_clasificacion(list(evidencia.tipos_candidatos))


def parse_clasificacion(
    data: dict[str, Any],
    tipos_candidatos: list[str],
    modelo: str = "",
) -> ClasificacionPropuesta:
    """Valida y normaliza la propuesta del modelo.

    Lanza `RespuestaIAInvalida` si la estructura no es la esperada o si el tipo
    propuesto no pertenece al catálogo. Filtra `evidencia` a textos y
    `alternativas` a tipos válidos distintos del propuesto (deduplicados, en
    orden), de modo que la IA no pueda introducir observaciones inventadas.
    """
    candidatos = list(tipos_candidatos)

    tipo = data.get("tipo_propuesto")
    if not isinstance(tipo, str) or tipo not in candidatos:
        raise RespuestaIAInvalida("la IA propuso un tipo fuera del catálogo de candidatos")

    confianza = data.get("confianza")
    if isinstance(confianza, bool) or not isinstance(confianza, (int, float)):
        raise RespuestaIAInvalida("la propuesta tiene 'confianza' inválida")

    justificacion = data.get("justificacion")
    if not isinstance(justificacion, str):
        raise RespuestaIAInvalida("la propuesta tiene 'justificacion' inválida")

    evidencia_raw = data.get("evidencia")
    if not isinstance(evidencia_raw, list):
        raise RespuestaIAInvalida("la propuesta tiene 'evidencia' inválida")

    alternativas_raw = data.get("alternativas")
    if not isinstance(alternativas_raw, list):
        raise RespuestaIAInvalida("la propuesta tiene 'alternativas' inválida")

    evidencia = [e for e in evidencia_raw if isinstance(e, str)]
    alternativas: list[str] = []
    for alt in alternativas_raw:
        if isinstance(alt, str) and alt in candidatos and alt != tipo and alt not in alternativas:
            alternativas.append(alt)

    return ClasificacionPropuesta(
        tipo_propuesto=tipo,
        # Campo advisory: se acota a [0, 1] en lugar de fallar, para no
        # descartar una propuesta útil por un decimal fuera de rango.
        confianza=min(1.0, max(0.0, float(confianza))),
        justificacion=justificacion,
        evidencia=evidencia,
        alternativas=alternativas,
        modelo=modelo,
    )


async def proponer_clasificacion(
    evidencia: EvidenciaClasificacion,
    *,
    client: LLMClient,
) -> ClasificacionPropuesta:
    """Propone un tipo documental a partir de la evidencia determinista.

    - Ante una respuesta no interpretable, reintenta una vez (MAX_INTENTOS).
    - `LLMError` (servicio caído) se propaga sin consumir el reintento.
    - Sin catálogo de tipos no hay nada que elegir: es un error de uso.
    """
    if not evidencia.tipos_candidatos:
        raise ValueError("se requiere al menos un tipo candidato para clasificar")

    system, user, esquema = construir_prompt_clasificar(evidencia)

    ultimo_error: RespuestaIAInvalida | None = None
    for _ in range(MAX_INTENTOS):
        crudo = await client.chat(system, user, json_schema=esquema)
        try:
            data = _extraer_json(crudo)
            return parse_clasificacion(data, evidencia.tipos_candidatos, modelo=client.modelo)
        except RespuestaIAInvalida as e:
            ultimo_error = e

    raise RespuestaIAInvalida(f"la IA no devolvió un formato interpretable: {ultimo_error}")


# ---------------------------------------------------------------------------
# Funcionalidad 5 — Redacción de la respuesta al estudiante (diseño 16, §6.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedaccionRespuesta:
    """Borrador advisory de la observación que el encargado enviará (Func 5).

    El texto es **editable**: el encargado lo revisa antes de enviar. La IA solo
    lo redacta; no envía nada (el envío sigue siendo el flujo SMTP de
    `notificacion.py`, área de I1).
    """

    texto: str
    asunto: str
    modelo: str = ""


ESQUEMA_REDACCION: dict[str, Any] = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
        "asunto": {"type": "string"},
    },
    "required": ["texto", "asunto"],
}

_SYSTEM_PROMPT_REDACTAR = """\
Eres un asistente técnico del personal del repositorio de tesis de la FECyC \
(Universidad Nacional de Trujillo). Debes redactar, en nombre del encargado, \
la observación formal que se enviará al estudiante sobre los incumplimientos de \
formato de su tesis.

Reglas estrictas:
- Usa EXCLUSIVAMENTE los fallos de la lista; no inventes observaciones, \
secciones ni reglas que no aparezcan.
- No decides la aprobación: el semáforo es determinista y ajeno a ti; solo \
comunicas lo que el motor ya detectó.
- Ordena las correcciones por prioridad: primero los errores (bloquean la \
entrega), después las advertencias.
- Tono institucional, respetuoso y claro, en español.
- El encargado revisará y editará tu texto antes de enviarlo.
- Responde SOLO con un objeto JSON válido, sin texto adicional.
- Formato exacto: {"texto": "...", "asunto": "..."}
- "asunto": línea de asunto breve del correo.
- "texto": cuerpo del correo (saludo, resumen de lo accionable, lista de \
correcciones por prioridad y cierre institucional).\
"""


def _orden_para_redaccion(fallidos: list[RuleResult]) -> list[RuleResult]:
    """Errores primero, después advertencias; dentro de cada grupo, el orden
    original del reporte. Es el orden en que el estudiante debe corregir."""
    return sorted(fallidos, key=lambda r: 0 if r.severity is Severity.ERROR else 1)


def construir_prompt_redactar(
    fallidos: list[RuleResult],
    tipo_documento: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Arma (system, user, json_schema) para la Funcionalidad 5.

    El `user` es solo el bloque de fallos ordenado por severidad (nunca el
    texto de la tesis).
    """
    ordenados = _orden_para_redaccion(fallidos)
    contenido = {
        "tipo_documento": tipo_documento,
        "fallos": [_fallo_a_dict(fallo) for fallo in ordenados],
    }
    user = json.dumps(contenido, ensure_ascii=False, indent=2)
    return _SYSTEM_PROMPT_REDACTAR, user, ESQUEMA_REDACCION


def parse_redaccion(data: dict[str, Any], modelo: str = "") -> RedaccionRespuesta:
    """Valida la respuesta del modelo al borrador advisory.

    Lanza `RespuestaIAInvalida` si falta el `texto` o el `asunto`, o si no son
    cadenas no vacías.
    """
    texto = data.get("texto")
    asunto = data.get("asunto")
    if not isinstance(texto, str) or not texto.strip():
        raise RespuestaIAInvalida("la redacción no trae un 'texto' válido")
    if not isinstance(asunto, str) or not asunto.strip():
        raise RespuestaIAInvalida("la redacción no trae un 'asunto' válido")
    return RedaccionRespuesta(texto=texto.strip(), asunto=asunto.strip(), modelo=modelo)


async def redactar_respuesta(
    resultados: list[RuleResult],
    *,
    client: LLMClient,
    tipo_documento: str | None = None,
) -> RedaccionRespuesta:
    """Redacta la observación al estudiante a partir de los fallos del reporte.

    - Si no hay fallos, no llama a la IA (no hay nada que comunicar).
    - Ante una respuesta no interpretable, reintenta una vez (MAX_INTENTOS).
    - `LLMError` (servicio caído) se propaga sin consumir el reintento.
    """
    fallidos = [r for r in resultados if not r.passed]
    if not fallidos:
        return RedaccionRespuesta(texto="", asunto="", modelo=client.modelo)

    system, user, esquema = construir_prompt_redactar(fallidos, tipo_documento)

    ultimo_error: RespuestaIAInvalida | None = None
    for _ in range(MAX_INTENTOS):
        crudo = await client.chat(system, user, json_schema=esquema)
        try:
            data = _extraer_json(crudo)
            return parse_redaccion(data, modelo=client.modelo)
        except RespuestaIAInvalida as e:
            ultimo_error = e

    raise RespuestaIAInvalida(f"la IA no devolvió un formato interpretable: {ultimo_error}")
