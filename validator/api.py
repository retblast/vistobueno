"""API FastAPI para VistoBueno — endpoint POST /validar.

Expone el motor de validación de formato de tesis como servicio HTTP.
Recibe un archivo DOCX, lo procesa contra las reglas de formato de la
UNT, y devuelve un reporte estructurado en JSON.

Uso:
    python -m validator.api
    # o con uvicorn directamente:
    uvicorn validator.api:app --reload
"""

import os
import re
import secrets
import tempfile
import threading
import time
import zipfile
from functools import cache
from ipaddress import ip_address
from pathlib import Path
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_models import (
    CampoExtraidoFicha,
    CampoManualFicha,
    ConstanciaRequest,
    DepositoAPI,
    DepositoRecibido,
    EstadoDepositoAPI,
    EstadoNotificacionAPI,
    FichaDeposito,
    FilaRegistroRequest,
    FilasRegistroResponse,
    MetadatosValidacion,
    NotificacionAPI,
    PromptIA,
    ResultadoReglaAPI,
    ResumenValidacion,
    SeveridadAPI,
    ValidarResponse,
)
from .buzon import Buzon
from .constancia import (
    MIME_DOCX as MIME_DOCX_CONSTANCIA,
)
from .constancia import (
    DatosConstancia,
    ErrorConfiguracionConstancia,
    ErrorDatosConstancia,
    _nombre_seguro,
    constancia_en_zip,
    constancias_por_autor,
    filas_a_csv,
    filas_a_tsv,
    filas_a_xlsx,
    llenar_constancia,
)
from .dsl_check import DSLValidationError
from .engine import build_report, load_ficha_rules, load_rules, validate_docx
from .models import RuleResult
from .notificacion import ConfigSMTP, enviar_notificacion
from .prompts import build_ai_help_section

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# F5: la API consume el motor DSL (reglas_unt.yaml, 47 reglas) en lugar del
# YAML legacy (unt_format_rules_schema.yaml, 32 mecánicas). Esto activa las
# 9 reglas F3 (resumen_longitud, referencias_minimo_*, anexos_minimos_*,
# caratula_orcid, proyecto_caratula_texto) y las de la F2 (paginación,
# encabezados/pies) dentro de POST /validar.
REGLAS_YAML_PATH = str(Path(__file__).resolve().parent.parent / "reglas_unt.yaml")

TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB

# Tipos de content-type admitidos. La puerta real NO es esta lista: un DOCX
# es un paquete OPC (ZIP) y algunos clientes lo envían con tipos genéricos.
# El control efectivo es la extensión `.docx` + la firma "PK" del archivo;
# los tres chequeos están en `validar()` (extensión, content-type y firma).
# AUD-13: un .docx legítimo con `application/zip`
# recibía 415 y el frontend lo aceptaba (acepta por MIME o extensión).
TIPOS_ACEPTADOS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",  # un DOCX es un ZIP: algunos clientes lo envían así
    "application/octet-stream",  # algunos navegadores envían esto para .docx
}

EXTENSION_ACEPTADA = ".docx"

# Claves acordadas de la ficha de depósito (v1.7.0, PLAN_FICHA §4).
# Los extraídos los publica el motor en reporte["ficha"] (handover
# HANDOVER_MOTOR_FICHA_DEPOSITO §4); los manuales los teclea el operador.
CAMPOS_EXTRAIDOS_FICHA = (
    "dc.title",
    "dc.contributor.author",
    "dc.contributor.advisor",
    "dc.description.abstract",
    "dc.subject",
    "dc.date.issued",
    "escuela",
    "renati.juror",
)
CAMPOS_MANUALES_FICHA = (
    "matricula",
    "renati.author.dni",
    "renati.advisor.dni",
    "renati.advisor.orcid",
)


# ---------------------------------------------------------------------------
# Control de acceso al buzón (auditoría 2026-10-26, AUD-09)
# ---------------------------------------------------------------------------
# El buzón travela datos personales del estudiante (DNI, ORCID, resumen) y
# su ranura es de "última gana": alguien que llegue desde la red puede
# leerlos o pisar la ficha en vuelo.
#
# El despliegue real es LOCAL: la app corre en la PC del encargado y
# `uvicorn` hace bind a 127.0.0.1. Por eso el control de acceso por
# defecto es el **loopback**: solo los peticiones que llegan desde la
# propia máquina pueden tocar el buzón.
#
# Si alguien expone la API fuera de la máquina (bind a 0.0.0.0 o un
# reverse proxy en otro host), puede exigir además un token compartido
# por header. La comparación es en tiempo constante.

CABECERA_TOKEN_BUZON = "X-VistoBueno-Token"
HOSTS_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})

# Hosts admitidos en el header `Host` de cualquier petición. Además del
# loopback se puede sumar un dominio propio con VISTOBUENO_HOSTS (lista
# separada por comas), por ejemplo si la API vive detrás de un reverse
# proxy en la misma máquina. `*` desactiva el chequeo (no recomendado).
HOSTS_CONFIABLES_DEFAULT = ("127.0.0.1", "localhost", "::1")


def _hosts_confiables() -> frozenset[str]:
    """Hosts admitidos, leídos del entorno en cada petición."""
    extra = os.environ.get("VISTOBUENO_HOSTS", "")
    return frozenset(h.strip().lower() for h in HOSTS_CONFIABLES_DEFAULT if h.strip()) | frozenset(
        h.strip().lower() for h in extra.split(",") if h.strip()
    )


def _host_sin_puerto(valor: str) -> str:
    """Normaliza el header Host: minúsculas, sin puerto y sin corchetes IPv6."""
    host = valor.strip().lower()
    if host.startswith("["):
        cierre = host.find("]")
        return host[1:cierre] if cierre != -1 else host
    return host.split(":", 1)[0]


class MiddlewareHostConfiable:
    """Rechaza peticiones con un header `Host` ajeno (400).

    Cierra el *DNS rebinding*: la página del atacante se sirve desde su
    dominio (Host: atacante.example) aunque su DNS resuelva a 127.0.0.1.
    El navegador conserva el Host del dominio en la petición, así que el
    chequeo corta el ataque en todos los navegadores; no depende de
    Private Network Access (mitigación solo de Chrome).

    El puerto se ignora y se admite IPv6 literal ("[::1]:8000").
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        hosts = _hosts_confiables()
        if "*" in hosts:
            await self.app(scope, receive, send)
            return
        host = _host_sin_puerto(Headers(scope=scope).get("host", ""))
        if host in hosts:
            await self.app(scope, receive, send)
            return
        respuesta = PlainTextResponse("Host no permitido", status_code=400)
        await respuesta(scope, receive, send)


def _token_api() -> str:
    """Token compartido de la API; vacío significa "no se exige token"."""
    return (os.environ.get("VISTOBUENO_API_TOKEN") or "").strip()


def _es_loopback(host: str | None) -> bool:
    """True si el host del par es la propia máquina.

    Acepta el nombre "localhost" y cualquier dirección del rango
    loopback: 127.0.0.0/8 completo (no solo 127.0.0.1) y ::1.
    """
    valor = (host or "").strip().lower()
    if valor in HOSTS_LOOPBACK:
        return True
    try:
        return ip_address(valor).is_loopback
    except ValueError:
        return False


async def verificar_acceso_local(request: Request) -> None:
    """Dependency de todos los endpoints: loopback o token compartido.

    La API se despliega en la PC del operador y `uvicorn` hace bind a
    127.0.0.1: el loopback es la frontera de confianza del MVP
    (auditoría 2026-10-26, AUD-09). El control cubre **toda** la API
    porque el buzón y el papeleo manejan datos personales (DNI, ORCID,
    resumen) y documentos oficiales: un `curl` desde otro equipo no
    puede validar, leer la ficha ni generar constancias.

    Reglas:

    - **Peer del loopback**: siempre permitido. La SPA y el userscript
      hablan con `127.0.0.1` y no envían token.
    - **Peer de otra máquina**: permitido solo si hay un token
      configurado (`VISTOBUENO_API_TOKEN`) y el header coincide.

    El token se comprueba **antes** de rechazar al peer remoto: sin ese
    orden, el token no serviría para el único caso que documenta (API
    expuesta fuera de la máquina).
    """
    host = request.client.host if request.client else None
    if _es_loopback(host):
        return
    token = _token_api()
    recibido = request.headers.get(CABECERA_TOKEN_BUZON, "")
    if token and secrets.compare_digest(recibido.encode(), token.encode()):
        return
    if not token:
        raise HTTPException(
            status_code=403,
            detail=(
                "La API de VistoBueno solo se sirve desde la máquina donde "
                "corre la app (loopback). Si la API se expone a otros "
                "equipos, define VISTOBUENO_API_TOKEN y envía el header "
                f"'{CABECERA_TOKEN_BUZON}'."
            ),
        )
    raise HTTPException(
        status_code=403,
        detail=(
            "Falta o no coincide el token de la API. Envía el header "
            f"'{CABECERA_TOKEN_BUZON}' con el valor de "
            "VISTOBUENO_API_TOKEN."
        ),
    )


# ---------------------------------------------------------------------------
# Limitador de peticiones (auditoría 2026-10-26, AUD-12)
# ---------------------------------------------------------------------------
# POST /validar recompila el DSL en cada request: el recurso a proteger es
# el CPU del proceso. El límite vive en memoria (sin base de datos, como el
# buzón): se reinicia con el servidor y no se comparte entre workers (el
# despliegue documentado es de UN worker).
#
# Es una mitigación mínima: si algún día la API se expone fuera de la
# máquina, el límite real va en el reverse proxy (ver README).

MAXIMO_PETICIONES_DEFAULT = 60
VENTANA_PETICIONES_DEFAULT = 60.0

# Cupo adaptativo por CPU (AUD-12, segunda iteración). El límite por
# número de peticiones asume que todas cuestan lo mismo, y no es cierto:
# la misma validación tarda ~60 ms en un equipo y ~250 ms en otro. El
# cupo acumula los segundos de trabajo MEDIDOS y se fuga a
# `presupuesto_segundos` por ventana, así que se ajusta solo al hardware
# sin constantes por modelo de PC.
PRESUPUESTO_CPU_DEFAULT = 2.0  # segundos de trabajo por ventana
COSTE_CPU_MINIMO = 0.01
COSTE_CPU_MAXIMO = 10.0  # un documento patológico no bloquea media hora


class LimitadorPeticiones:
    """Ventana fija por IP: cuenta las peticiones de un intervalo.

    Attributes:
        _peticiones: IP → (cantidad, inicio de la ventana).
        _lock: el acceso puede ser concurrente (endpoints en threadpool).
    """

    def __init__(self) -> None:
        self._peticiones: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def registrar(self, ip: str, maximo: int, ventana: float) -> tuple[bool, float]:
        """Registra una petición.

        Returns:
            (permitido, segundos para reintentar). Si no está permitida,
            los segundos son el tiempo que falta para que venza la ventana.
        """
        ahora = time.monotonic()
        with self._lock:
            cantidad, inicio = self._peticiones.get(ip, (0, ahora))
            if ahora - inicio >= ventana:
                cantidad, inicio = 0, ahora
            cantidad += 1
            self._peticiones[ip] = (cantidad, inicio)
            if cantidad > maximo:
                return False, max(ventana - (ahora - inicio), 0.0)
            self._purgar(ahora, ventana)
            return True, 0.0

    def _purgar(self, ahora: float, ventana: float) -> None:
        """Descarta las entradas vencidas (evita que el dict crezca sin fin)."""
        if len(self._peticiones) <= 1000:
            return
        self._peticiones = {
            ip: datos for ip, datos in self._peticiones.items() if ahora - datos[1] < ventana
        }

    def limpiar(self) -> None:
        """Vacía el estado (tests y reinicio del flujo)."""
        with self._lock:
            self._peticiones.clear()


class LimitadorCPU:
    """Cupo adaptativo por presupuesto de CPU (cubo con fugas).

    `_deuda` acumula los segundos de trabajo medidos y se fuga a
    `presupuesto_segundos / ventana_segundos` por segundo. Una petición
    entra si la deuda está por debajo del presupuesto. El presupuesto es
    el mismo en cualquier equipo; lo que cambia es cuántas peticiones
    caben en él:

    - equipo rápido (~60 ms por validación): ~33 seguidas con 2 s;
    - equipo lento (~250 ms por validación): ~8 seguidas;
    - tasa sostenida: 2 s de CPU por minuto en ambos casos.

    El coste se mide en el endpoint (`registrar_coste`) después de la
    operación pesada, así que no hay números mágicos por hardware.

    Attributes:
        _deuda: segundos de trabajo acumulados; se recorta al consultar.
        _lock: el cupo se consulta desde endpoints concurrentes.
    """

    def __init__(
        self,
        *,
        presupuesto_segundos: float = PRESUPUESTO_CPU_DEFAULT,
        ventana_segundos: float = VENTANA_PETICIONES_DEFAULT,
    ) -> None:
        self._presupuesto = max(presupuesto_segundos, 0.0)
        self._ventana = max(ventana_segundos, 0.1)
        self._tasa = self._presupuesto / self._ventana
        self._deuda = 0.0
        self._ultimo = time.monotonic()
        self._lock = threading.Lock()

    def _fugar(self, ahora: float) -> None:
        """Descuenta la deuda por el tiempo transcurrido (llamar con el lock)."""
        if ahora <= self._ultimo:
            return
        self._deuda = max(0.0, self._deuda - (ahora - self._ultimo) * self._tasa)
        self._ultimo = ahora

    def adquirir(self) -> tuple[bool, float]:
        """Consulta si entra una petición más.

        Returns:
            (permitido, segundos para reintentar). La deuda se cobra al
            terminar, con el coste real (`registrar_coste`).
        """
        with self._lock:
            self._fugar(time.monotonic())
            if self._deuda < self._presupuesto:
                return True, 0.0
            falta = (
                (self._deuda - self._presupuesto) / self._tasa if self._tasa > 0 else self._ventana
            )
            return False, max(falta, 1.0)

    def registrar_coste(self, segundos: float) -> None:
        """Suma a la deuda el coste real de la operación pesada."""
        with self._lock:
            self._deuda += min(max(segundos, COSTE_CPU_MINIMO), COSTE_CPU_MAXIMO)

    def limpiar(self) -> None:
        """Vacía el estado (tests y reinicio del flujo)."""
        with self._lock:
            self._deuda = 0.0
            self._ultimo = time.monotonic()


_LIMITADOR_PETICIONES = LimitadorPeticiones()
_LIMITADOR_CPU_VALIDACION = LimitadorCPU()
# El papeleo (DOCX/XLSX) pesa más que una validación: menos presupuesto.
_LIMITADOR_CPU_PAPELES = LimitadorCPU(presupuesto_segundos=1.0)


def _config_limite_peticiones() -> tuple[int, float]:
    """Límite por IP y ventana, leídos del entorno en cada request.

    Returns:
        (máximo de peticiones, ventana en segundos). Un máximo de 0
        desactiva el límite.
    """
    try:
        maximo = int(os.environ.get("VISTOBUENO_RATE_LIMIT_MAX", MAXIMO_PETICIONES_DEFAULT))
    except ValueError:
        maximo = MAXIMO_PETICIONES_DEFAULT
    try:
        ventana = float(
            os.environ.get("VISTOBUENO_RATE_LIMIT_VENTANA_SEG", VENTANA_PETICIONES_DEFAULT)
        )
    except ValueError:
        ventana = VENTANA_PETICIONES_DEFAULT
    return max(0, maximo), max(ventana, 0.1)


def _rechazar_por_limite(reintentar: float, recurso: str) -> None:
    """Respuesta 429 uniforme de los cupos."""
    raise HTTPException(
        status_code=429,
        headers={"Retry-After": str(int(reintentar) + 1)},
        detail=(
            f"Demasiadas peticiones de {recurso} seguidas. "
            "Espera unos segundos antes de reintentar."
        ),
    )


async def limitar_validaciones(request: Request) -> None:
    """Dependency de POST /validar: corta los abusos de CPU con 429.

    Si `VISTOBUENO_RATE_LIMIT_MAX` está definido se usa la ventana fija
    por IP (comportamiento previo; `0` la desactiva). Si no, se usa el
    cupo adaptativo por CPU, que se ajusta a la velocidad del equipo.
    """
    if "VISTOBUENO_RATE_LIMIT_MAX" in os.environ:
        maximo, ventana = _config_limite_peticiones()
        if maximo <= 0:
            return
        ip = request.client.host if request.client else "desconocido"
        permitido, reintentar = _LIMITADOR_PETICIONES.registrar(ip, maximo, ventana)
        if not permitido:
            _rechazar_por_limite(reintentar, "validación")
        return
    permitido, reintentar = _LIMITADOR_CPU_VALIDACION.adquirir()
    if not permitido:
        _rechazar_por_limite(reintentar, "validación")


async def limitar_papeleo() -> None:
    """Dependency de /constancia y /fila-registro: cupo adaptativo por CPU."""
    permitido, reintentar = _LIMITADOR_CPU_PAPELES.adquirir()
    if not permitido:
        _rechazar_por_limite(reintentar, "documentos")


@cache
def _get_rules() -> dict:
    """Carga el YAML de reglas una sola vez (cacheado en memoria)."""
    return load_rules(REGLAS_YAML_PATH)


@cache
def _get_ficha_rules() -> dict:
    """Carga el ruleset de captura de la ficha (diseño 17), una sola vez.

    Devuelve ``{}`` si el archivo no existe (despliegue sin ficha): la
    respuesta sigue trayendo los campos acordados con ``detectado=false``.
    """
    return load_ficha_rules()


# ---------------------------------------------------------------------------
# Mapeo motor interno → DTO API
# ---------------------------------------------------------------------------


def _rule_result_a_dto(r: RuleResult) -> ResultadoReglaAPI:
    """Convierte un RuleResult del motor a un ResultadoReglaAPI (DTO)."""
    return ResultadoReglaAPI(
        rule_id=r.rule_id,
        paso=r.passed,
        severidad=SeveridadAPI(r.severity.value),
        mensaje=r.message,
        esperado=r.expected,
        encontrado=r.found,
        ubicacion=r.location,
        fuente=r.fuente,
        cita=r.cita,
        aplicable=r.aplicable,
    )


def _extraer_metadata_tipo_documento(
    resultados_motor: list[RuleResult],
) -> dict:
    """Extrae los campos opcionales de tipo de documento de la detección.

    La regla `deteccion_tipo_documento` siempre se ejecuta; su `encontrado`
    contiene la decisión como texto. Se parsea para publicar:

    - `tipo_documento_declarado`: lo que dice el Anexo 10 (None si no declaró).
    - `tipo_documento_inferido`: lo que se dedujo de las firmas (None si no se
      pudo inferir).
    - `tipo_documento_estado`: "vigente" si se determinó un tipo,
      "sin_determinar" si no se pudo, "contradictorio" si el Anexo 10 y las
      firmas no coinciden.

    El parseo es determinista sobre el texto que genera el motor mismo, por
    lo que no hay riesgo de desalineación.
    """
    detector = next((r for r in resultados_motor if r.rule_id == "deteccion_tipo_documento"), None)
    if detector is None or not detector.found:
        return {
            "tipo_documento_declarado": None,
            "tipo_documento_inferido": None,
            "tipo_documento_estado": "sin_determinar",
        }

    encontrado = detector.found
    declarado = re.search(r"declarado=([a-z_]+)", encontrado)
    inferido = re.search(r"inferido=([a-z_]+)", encontrado)
    contradice = "contradictorio:" in encontrado
    sin_determinar = encontrado.startswith("sin_determinado")

    if contradice:
        estado = "contradictorio"
    elif sin_determinar:
        estado = "sin_determinar"
    else:
        estado = "vigente"

    # declarado e inferido son Optional[Match[str]]; en contradice ambos existen
    declarado_val = declarado.group(1) if declarado else None
    inferido_val = inferido.group(1) if inferido else None

    return {
        "tipo_documento_declarado": declarado_val,
        "tipo_documento_inferido": inferido_val,
        "tipo_documento_estado": estado,
    }


def _valor_utilizable(valor: object) -> bool:
    """True si el valor capturado sirve para el formulario de DSpace.

    Contrato de la ficha (auditoría 2026-10-26, AUD-25 y AUD-26): un
    campo con `detectado=true` debe traer un valor **utilizable**. El
    motor puede publicar capturas vacías o con la forma equivocada (por
    ejemplo, el asesor vacío o la línea de ciudad en vez del año), y
    ese dato viaja al formulario oficial, a la constancia y al
    registro. La API no lo publica como detectado: lo deja para que el
    operador lo teclee.
    """
    if valor is None:
        return False
    if isinstance(valor, str):
        return bool(valor.strip())
    if isinstance(valor, list):
        # Una lista sirve si tiene al menos un elemento con texto.
        return any(isinstance(item, str) and item.strip() for item in valor)
    return True


def _forma_valida(campo: str, valor: object) -> bool:
    """True si el valor además tiene la forma que espera el campo.

    Solo `dc.date.issued` tiene forma estricta: el formulario pide un
    año. El chequeo es de **valor completo**, no de "contiene": la
    captura real de AUD-26 es el párrafo del título, que termina en
    ", Trujillo 2024". Un `contains` dejaría pasar ese texto y el
    ítem se publicaría con la fecha equivocada.
    """
    if campo != "dc.date.issued":
        return True
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    if not isinstance(valor, str):
        return False
    return bool(re.fullmatch(r"(?:19|20)\d{2}", valor.strip()))


def _ficha_desde_reporte(reporte: dict) -> FichaDeposito:
    """Construye la ficha de depósito a partir del reporte del motor.

    El motor publica las extracciones en `reporte["ficha"]` como un
    dict campo→dato, cada dato con la forma acordada del handover §4:
    `{"valor": …, "pagina": …, "detectado": …}`. Si un campo no fue
    capturado (p. ej. `renati.juror`, viabilidad negativa del diseño
    17), viaja con `detectado=false` y `valor=null`: el contrato es
    estable y el frontend puede construirse ya.

    Un campo solo viaja con `detectado=true` si su valor es **utilizable**
    y tiene la **forma** que espera el campo (ver `_valor_utilizable` y
    `_forma_valida`). Si no, viaja con `detectado=false` y `valor=null`:
    el operador lo teclea en la pantalla de ficha.

    Los manuales siempre viajan vacíos desde el servidor: los llena el
    operador en la pantalla.
    """
    datos_motor = reporte.get("ficha") or {}
    extraidos = []
    for campo in CAMPOS_EXTRAIDOS_FICHA:
        dato = datos_motor.get(campo) or {}
        valor = dato.get("valor")
        detectado = (
            bool(dato.get("detectado")) and _valor_utilizable(valor) and _forma_valida(campo, valor)
        )
        extraidos.append(
            CampoExtraidoFicha(
                campo=campo,
                valor=valor if detectado else None,
                pagina=dato.get("pagina") if detectado else None,
                detectado=detectado,
            )
        )
    manuales = [CampoManualFicha(campo=c, valor=None) for c in CAMPOS_MANUALES_FICHA]
    return FichaDeposito(extraidos=extraidos, manuales=manuales)


def _construir_respuesta(
    resultados_motor: list,
    reporte: dict,
    prompts_data: list,
    archivo_nombre: str,
    archivo_tamano: int,
    rules_data: dict,
) -> ValidarResponse:
    """Ensambla la respuesta completa de la API a partir de la salida del motor."""
    resultados_dto = [
        _rule_result_a_dto(r)
        for r in resultados_motor
        # Las reglas de CAPTURA (diseño 17) no son reglas de validación:
        # no viajan en `resultados`; sus datos van en `ficha_deposito`.
        if not r.captura
    ]
    resumen_motor = reporte["resumen"]

    # La ficha solo materializa con semáforo verde (invariante del
    # contrato v1.7.0): un documento con errores bloqueantes no se
    # deposita, y no hay nada que pre-llenar.
    ficha = _ficha_desde_reporte(reporte) if reporte["semaforo"] == "verde" else None

    return ValidarResponse(
        semaforo=reporte["semaforo"],
        resumen=ResumenValidacion(
            total=resumen_motor["total"],
            total_evaluadas=resumen_motor["total_evaluadas"],
            reglas_no_aplicables=resumen_motor["reglas_no_aplicables"],
            fallidos_error=resumen_motor["fallidos_error"],
            fallidos_warning=resumen_motor["fallidos_warning"],
        ),
        resultados=resultados_dto,
        como_preguntar_a_una_ia=[
            PromptIA(rule_id=p["rule_id"], prompt=p["prompt"]) for p in prompts_data
        ],
        metadatos=MetadatosValidacion(
            archivo_nombre=archivo_nombre,
            archivo_tamano_bytes=archivo_tamano,
            reglas_evaluadas=resumen_motor["total_evaluadas"],
            reglas_totales=resumen_motor["total"],
            version_esquema=rules_data.get("version", "desconocido"),
            **_extraer_metadata_tipo_documento(resultados_motor),
        ),
        ficha_deposito=ficha,
    )


def _validar_correo(correo: str | None) -> str | None:
    """Valida el correo electrónico del estudiante (campo opcional).

    - `None` o cadena vacía → `None` (el frontend puede omitirlo o enviar "").
    - Si se envía, debe tener formato de correo válido; si no, lanza 422
      con mensaje descriptivo en español.

    El valor normalizado retornado es el destinatario de la notificación de
    observaciones (Actividad 6): se envía un correo cuando el semáforo es
    "rojo", la notificación está habilitada y el servidor SMTP acepta el envío.
    """
    if correo is None:
        return None
    correo_limpio = correo.strip()
    if not correo_limpio:
        return None

    try:
        resultado = validate_email(correo_limpio, check_deliverability=False)
        return resultado.normalized
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Correo electrónico inválido: '{correo_limpio}'. "
                f"Formato esperado: usuario@dominio."
            ),
        ) from e


# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="VistoBueno API",
    description="API de validación automática de formato de tesis — UNT FECyC",
    version="1.11.0",
)
# DNS rebinding: se valida el header Host antes de cualquier endpoint.
app.add_middleware(MiddlewareHostConfiable)


@app.post(
    "/validar",
    response_model=ValidarResponse,
    summary="Validar formato de tesis",
    description=(
        "Recibe un archivo DOCX de tesis y devuelve un reporte de validación "
        "contra las reglas de formato de la Universidad Nacional de Trujillo."
    ),
    responses={
        400: {"description": "Sin archivo en la solicitud"},
        403: {"description": "Petición desde otro equipo o sin token válido"},
        413: {"description": "Archivo excede el tamaño máximo (10 MB)"},
        415: {"description": "Tipo de archivo no soportado"},
        422: {"description": "Archivo corrupto, no es DOCX válido o correo inválido"},
        429: {"description": "Demasiadas peticiones de validación seguidas"},
        500: {"description": "Error interno del validador"},
    },
    dependencies=[Depends(verificar_acceso_local), Depends(limitar_validaciones)],
)
async def validar(
    archivo: UploadFile = File(..., description="Archivo .docx a validar"),
    incluir_prompts_ia: bool = Query(
        default=True,
        description="Incluir la sección 'Cómo preguntar a una IA' en la respuesta",
    ),
    correo: str | None = Form(
        default=None,
        description=(
            "Correo electrónico del estudiante (opcional). "
            "Destinatario de las observaciones cuando se solicita el envío "
            "(campo `notificar`)."
        ),
        # Swagger prellenaba "string" y un Execute sin editar enviaba
        # basura; con ejemplo vacío el campo se deja en blanco solo
        # (revisión del PR #55, hallazgo 2).
        examples=[""],
    ),
    notificar: bool = Form(
        default=False,
        description=(
            "Solicitar el envío del correo de observaciones al estudiante "
            "(opt-in del operador). Solo aplica con semáforo rojo y un "
            "`correo` válido."
        ),
    ),
    depositar: bool = Form(
        default=False,
        description=(
            "DEPRECADO (decisión 2026-10-28): el depósito automático en DSpace "
            "queda fuera del flujo. El flujo oficial es la ficha (SPA) → buzón → "
            "userscript, y el archivo lo adjunta el encargado en el formulario "
            "oficial de DSpace. El campo se conserva para no romper el "
            "contrato, pero ya no dispara ninguna llamada."
        ),
    ),
    titulo: str | None = Form(
        default=None,
        description=(
            "DEPRECADO: metadato dc.title que usaba el depósito automático. "
            "El título de la ficha de depósito lo captura el motor del DOCX."
        ),
        examples=[""],
    ),
    autores: str | None = Form(
        default=None,
        description=(
            "DEPRECADO: metadato dc.contributor.author que usaba el depósito "
            "automático. Los autores los captura el motor del DOCX y el "
            "operador los corrige en la pantalla de ficha."
        ),
        examples=[""],
    ),
    asesor: str | None = Form(
        default=None,
        description=(
            "DEPRECADO: metadato dc.contributor.advisor que usaba el depósito "
            "automático. El asesor lo captura el motor del DOCX."
        ),
        examples=[""],
    ),
    resumen: str | None = Form(
        default=None,
        description=(
            "DEPRECADO: metadato dc.description.abstract que usaba el depósito "
            "automático. El resumen lo captura el motor del DOCX."
        ),
        examples=[""],
    ),
    palabras_clave: str | None = Form(
        default=None,
        description=(
            "DEPRECADO: metadato dc.subject que usaba el depósito automático. "
            "Las palabras clave las captura el motor del DOCX."
        ),
        examples=[""],
    ),
):
    # --- Validación: ¿hay archivo? ---
    if archivo.filename is None or archivo.filename == "":
        raise HTTPException(
            status_code=400,
            detail="Campo 'archivo' requerido. Envíe un archivo .docx en el campo 'archivo' del formulario multipart.",
        )

    # --- Validación: extensión ---
    if not archivo.filename.lower().endswith(EXTENSION_ACEPTADA):
        raise HTTPException(
            status_code=415,
            detail=(
                f"Tipo de archivo no soportado: '{archivo.filename}'. "
                f"Solo se aceptan archivos .docx "
                f"({EXTENSION_ACEPTADA})."
            ),
        )

    # --- Validación: content-type (advisory, no definitivo) ---
    content_type = archivo.content_type or ""
    if content_type and content_type not in TIPOS_ACEPTADOS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Content-Type no soportado: '{content_type}'. Solo se aceptan archivos .docx."
            ),
        )

    # --- Validación: correo electrónico (opcional) ---
    correo_normalizado = _validar_correo(correo)

    # --- Leer contenido (con tope) ---
    # Leer a lo sumo TAMANO_MAXIMO_BYTES + 1: evita cargar en memoria
    # un upload arbitrariamente grande antes de validar el tamaño.
    # Nota: por eso el 413 no reporta el tamaño exacto recibido.
    try:
        contenido = await archivo.read(TAMANO_MAXIMO_BYTES + 1)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail="No se pudo leer el archivo enviado.",
        ) from e

    # --- Validación: tamaño ---
    tamano = len(contenido)
    if tamano > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=("El archivo excede el tamaño máximo permitido (10 MB)."),
        )

    if tamano == 0:
        raise HTTPException(
            status_code=422,
            detail="El archivo está vacío.",
        )

    # --- Validación: magic bytes de un ZIP/DOCX (cabecera PK) ---
    # Un DOCX es un paquete OPC (ZIP). Toda imagen ZIP válida comienza con
    # la firma local 'PK\x03\x04'. Verificarla antes de escribir el temporal
    # permite rechazar rápido archivos renombrados a .docx sin abrirlos.
    if not contenido.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=422,
            detail=(
                "El archivo no es un ZIP/DOCX válido: cabecera incorrecta "
                "(se esperaba la firma 'PK')."
            ),
        )

    # --- Guardar en archivo temporal y procesar ---
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=EXTENSION_ACEPTADA) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name

        rules_data = _get_rules()

        # El escaneo del DOCX es lo ÚNICO cuyos errores significan "el
        # archivo del usuario está mal". El 422 se acota a esta llamada
        # (hallazgo B6): pydantic.ValidationError es subclase de ValueError,
        # así que un bug interno del mapeo a DTO o del motor respondía 422
        # culpando al documento del estudiante. Ahora esos caen al 500
        # genérico del bloque exterior.
        # El motor es síncrono y CPU-intenso (recompila el DSL en cada
        # request): se despacha al threadpool para no congelar el event
        # loop mientras dura la validación. Se pasa el ruleset de captura
        # de la ficha (diseño 17) en la MISMA pasada: sus capturas viajan
        # en reporte["ficha"] y no afectan semáforo ni resumen.
        inicio_cpu = time.perf_counter()
        try:
            resultados_motor = await run_in_threadpool(
                validate_docx, tmp_path, rules_data, _get_ficha_rules()
            )
        except DSLValidationError as e:
            # Reglas rotas = error de configuración del servidor, no del
            # documento del estudiante.
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del validador: configuración de reglas inválida: {e}",
            ) from e
        except zipfile.BadZipFile as e:
            # Archivo no es un ZIP válido (truncado, corrupto, etc.)
            raise HTTPException(
                status_code=422,
                detail=(
                    "No se pudo procesar el archivo DOCX: archivo corrupto o no es un DOCX válido."
                ),
            ) from e
        except KeyError as e:
            # El ZIP es válido pero falta word/document.xml (u otra parte
            # esencial del formato DOCX). El extractor lanza KeyError al
            # intentar leer el archivo interno del paquete OPC.
            raise HTTPException(
                status_code=422,
                detail=(
                    f"El archivo no contiene un documento Word válido: archivo interno faltante ({e})."
                ),
            ) from e
        except ValueError as e:
            # El extractor no encontró una parte esperada del DOCX
            # (lanzado por ExtractedDocx.xpath cuando una parte no está
            # disponible).
            raise HTTPException(
                status_code=422,
                detail=(f"El archivo no contiene un documento Word válido: {e}."),
            ) from e
        finally:
            # El cupo adaptativo descuenta lo que tardó de verdad la
            # operación en ESTE equipo (no un número fijo por petición).
            _LIMITADOR_CPU_VALIDACION.registrar_coste(time.perf_counter() - inicio_cpu)

        reporte = build_report(resultados_motor)

        # Prompts de IA (solo si se solicitan)
        prompts_data = []
        if incluir_prompts_ia:
            fallidos = [r for r in resultados_motor if not r.passed]
            prompts_data = build_ai_help_section(fallidos)

        respuesta = _construir_respuesta(
            resultados_motor=resultados_motor,
            reporte=reporte,
            prompts_data=prompts_data,
            archivo_nombre=archivo.filename,
            archivo_tamano=tamano,
            rules_data=rules_data,
        )

        # --- Notificación de observaciones (Actividad 6, best-effort) ---
        # El estado se expone al personal del repositorio (herramienta de
        # uso interno): "enviado" permite informar "enviamos las observaciones
        # al correo del estudiante"; "fallo" incluye el motivo técnico.
        # El envío es opt-in por solicitud (`notificar`): el operador decide
        # cuándo el reporte está listo para llegarle al estudiante. Se exige
        # además semáforo "rojo" y un `correo` válido, y el servidor debe
        # tener la notificación habilitada. enviar_notificacion() NUNCA
        # lanza: un fallo de SMTP no debe romper la respuesta HTTP.
        estado = EstadoNotificacionAPI.SIN_CORREO
        detalle: str | None = None
        if correo_normalizado:
            if not notificar:
                estado = EstadoNotificacionAPI.NO_SOLICITADO
            elif respuesta.semaforo != "rojo":
                estado = EstadoNotificacionAPI.SIN_OBSERVACIONES
            else:
                config_smtp = ConfigSMTP.desde_entorno()
                if not config_smtp.enabled:
                    estado = EstadoNotificacionAPI.DESHABILITADO
                    # Nota de configuración para el personal del repositorio
                    # (hallazgo B3): sin esto, "casilla marcada → 200 OK →
                    # nada" era indistinguible de un envío silencioso. El
                    # detalle indica cómo habilitar el servidor.
                    detalle = (
                        "El servidor no tiene la notificación habilitada: "
                        "configure VISTOBUENO_NOTIFICACIONES=1 y VISTOBUENO_SMTP_HOST."
                    )
                else:
                    # smtplib es bloqueante (timeout de hasta 10 s): fuera
                    # del event loop, o un SMTP caído congela toda la API.
                    resultado_envio = await run_in_threadpool(
                        enviar_notificacion,
                        respuesta,
                        correo_normalizado,
                        config=config_smtp,
                    )
                    if resultado_envio.enviado:
                        estado = EstadoNotificacionAPI.ENVIADO
                    else:
                        estado = EstadoNotificacionAPI.FALLO
                        detalle = resultado_envio.detalle
        respuesta.notificacion = NotificacionAPI(estado=estado, detalle=detalle)

        # --- Depósito en DSpace (Actividad 10) — DEPRECADO ---
        # Decisión del equipo (2026-10-28, auditoría de comportamiento): la
        # app NO escribe en la API de DSpace. El flujo oficial es la ficha
        # (SPA) → buzón → userscript, que rellena el formulario oficial; el
        # archivo lo adjunta el encargado en ese formulario.
        # Por eso `depositar=true` ya NO dispara ninguna llamada: responde
        # "deshabilitado" con la nota que explica el flujo vigente. El campo
        # y el DTO `deposito` se conservan para no romper el contrato.
        estado_dep = EstadoDepositoAPI.SIN_SOLICITUD
        detalle_dep: str | None = None
        if depositar:
            estado_dep = EstadoDepositoAPI.DESHABILITADO
            detalle_dep = (
                "El depósito automático está deshabilitado: el flujo oficial es "
                "el formulario de DSpace + el userscript de VistoBueno; el "
                "archivo lo adjunta el encargado en el formulario oficial."
            )
        respuesta.deposito = DepositoAPI(estado=estado_dep, detalle=detalle_dep)

        return respuesta

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del validador: {type(e).__name__}: {e}",
        ) from e
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Buzón de una ranura: comunicación con el userscript de depósito
# ---------------------------------------------------------------------------

# Instancia única del buzón (una ranura de ficha + una de depósito, TTL 1h).
# Es la única pieza de estado del servidor: ver docs/PLAN_FICHA_DEPOSITO.md §6.
_BUZON = Buzon()


@app.post(
    "/ficha-pendiente",
    status_code=204,
    summary="Publicar la ficha completada en el buzón",
    description=(
        "La SPA publica la ficha (extraídos + manuales) para que el "
        "userscript de depósito la lea desde el navegador del operador. "
        "El buzón tiene UNA ranura con TTL de 1 hora: publicar de nuevo "
        "reemplaza la ficha anterior ('última gana'). "
        "Solo se sirve desde la máquina donde corre la app (loopback); "
        "si hay token configurado, exige el header "
        f"'{CABECERA_TOKEN_BUZON}'."
    ),
    responses={403: {"description": "Petición desde otro equipo o sin token válido"}},
    dependencies=[Depends(verificar_acceso_local)],
)
async def publicar_ficha_pendiente(ficha: FichaDeposito) -> None:
    _BUZON.publicar_ficha(ficha.model_dump())


@app.get(
    "/ficha-pendiente",
    response_model=FichaDeposito,
    summary="Leer la ficha pendiente del buzón",
    description=(
        "El userscript lee aquí la ficha a rellenar en el formulario "
        "oficial de DSpace. 404 cuando no hay ficha o la publicada "
        "expiró (TTL de 1 hora). Solo se sirve desde la máquina donde "
        "corre la app (loopback); si hay token configurado, exige el "
        f"header '{CABECERA_TOKEN_BUZON}'."
    ),
    responses={
        403: {"description": "Petición desde otro equipo o sin token válido"},
        404: {"description": "Sin ficha pendiente: vacía o expirada"},
    },
    dependencies=[Depends(verificar_acceso_local)],
)
async def leer_ficha_pendiente() -> FichaDeposito:
    ficha = _BUZON.leer_ficha()
    if ficha is None:
        raise HTTPException(
            status_code=404,
            detail="Sin ficha pendiente: vacía o expirada (TTL de 1 hora).",
        )
    return FichaDeposito(**ficha)


@app.post(
    "/deposito",
    status_code=204,
    summary="Reportar un depósito realizado",
    description=(
        "El userscript reporta el depósito desde la página del ítem "
        "archivado: handle del ítem, título y el timestamp del clic en "
        "Depositar. La SPA lo recoge sondeando GET /deposito y arma la "
        "constancia y la fila del registro. Solo se sirve desde la "
        "máquina donde corre la app (loopback); si hay token configurado, "
        f"exige el header '{CABECERA_TOKEN_BUZON}'."
    ),
    responses={403: {"description": "Petición desde otro equipo o sin token válido"}},
    dependencies=[Depends(verificar_acceso_local)],
)
async def reportar_deposito(datos: DepositoRecibido) -> None:
    _BUZON.reportar_deposito(datos.model_dump())


@app.get(
    "/deposito",
    response_model=DepositoRecibido,
    summary="Leer el depósito reportado",
    description=(
        "La SPA sondea aquí mientras espera el handle del ítem. 404 "
        "cuando no hay reporte o expiró (TTL de 1 hora). Por seguridad, "
        "la SPA debe cotejar el `titulo` reportado con la ficha en vuelo "
        "antes de usar el handle. Solo se sirve desde la máquina donde "
        "corre la app (loopback); si hay token configurado, exige el "
        f"header '{CABECERA_TOKEN_BUZON}'."
    ),
    responses={
        403: {"description": "Petición desde otro equipo o sin token válido"},
        404: {"description": "Sin depósito reportado: vacío o expirado"},
    },
    dependencies=[Depends(verificar_acceso_local)],
)
async def leer_deposito_reportado() -> DepositoRecibido:
    datos = _BUZON.leer_deposito()
    if datos is None:
        raise HTTPException(
            status_code=404,
            detail="Sin depósito reportado: vacío o expirado (TTL de 1 hora).",
        )
    return DepositoRecibido(**datos)


# ---------------------------------------------------------------------------
# Constancia de depósito (Modelo B) y fila de registro
# ---------------------------------------------------------------------------

# Plantilla oficial de la constancia. Vive en recursos/ (no versionada:
# es un artefacto institucional). Ruta sobreescribible por entorno.
PLANTILLA_CONSTANCIA_POR_DEFECTO = (
    Path(__file__).resolve().parent.parent / "recursos" / "TESIS DIGITAL MODELO B-2026.docx"
)


def _ruta_plantilla_constancia() -> Path:
    """Ruta de la plantilla del Modelo B (configurable por entorno)."""
    return Path(
        os.environ.get("VISTOBUENO_PLANTILLA_CONSTANCIA", str(PLANTILLA_CONSTANCIA_POR_DEFECTO))
    )


def _firma_operador() -> str:
    """Firma del responsable (columna FIRMA del registro), por entorno."""
    return os.environ.get("VISTOBUENO_FIRMA", "").strip()


def _constancias_de_solicitud(solicitud: FilaRegistroRequest) -> list[DatosConstancia]:
    """Valida la solicitud y arma los datos: una constancia por autor.

    Errores:

    - 422: timestamp que no es ISO 8601, o falta un dato de la ficha
      (título, autores, matrículas alineadas).
    - 500: configuración del servidor (firma o plantilla).
    """
    try:
        momento = _parsear_timestamp(solicitud.timestamp)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Timestamp inválido: '{solicitud.timestamp}'. Use ISO 8601 (p. ej. 2026-10-19T18:10:00).",
        ) from e

    firma = _firma_operador()
    if not firma:
        raise HTTPException(
            status_code=500,
            detail=(
                "El servidor no tiene la firma del responsable configurada: "
                "defina VISTOBUENO_FIRMA (nombre que va en la columna FIRMA del registro)."
            ),
        )

    try:
        return constancias_por_autor(solicitud.ficha.model_dump(), solicitud.handle, momento, firma)
    except ErrorDatosConstancia as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _parsear_timestamp(texto: str):
    """Parsea el timestamp ISO 8601 reportado por el userscript."""
    from datetime import datetime

    return datetime.fromisoformat(texto)


def _nombre_archivo_constancia(datos: DatosConstancia) -> str:
    """Nombre de descarga: 'constancia - {autor sanitizado}.docx'.

    Delega a _nombre_seguro en constancia.py para que el nombre del
    zip y el del docx sean consistentes entre sí.
    """
    return f"constancia - {_nombre_seguro(datos.autor)}.docx"


@app.post(
    "/constancia",
    summary="Descargar la constancia de UN autor (Modelo B lleno, o paquete zip)",
    description=(
        "Genera la constancia de depósito del Modelo B con los MERGEFIELD "
        "reemplazados por los valores de la ficha. Una constancia POR "
        "AUTOR: la SPA descarga una por cada estudiante iterando "
        "`indice_autor`. Devuelve el .docx como descarga binaria. Con "
        "`formato=zip` devuelve en su lugar un paquete con la constancia "
        ".docx y la fila del registro del autor como .csv (hallazgo 11: "
        '"POST /constancia podría incluirlo").'
    ),
    responses={
        200: {"description": "Constancia .docx (o paquete .zip con formato=zip)"},
        403: {"description": "Petición desde otro equipo o sin token válido"},
        422: {
            "description": "Timestamp inválido, falta un dato de la ficha o índice fuera de rango"
        },
        429: {"description": "Demasiadas generaciones de documentos seguidas"},
        500: {"description": "Firma o plantilla sin configurar en el servidor"},
    },
    dependencies=[Depends(verificar_acceso_local), Depends(limitar_papeleo)],
)
async def descargar_constancia(
    solicitud: ConstanciaRequest,
    formato: Literal["docx", "zip"] = Query(
        default="docx",
        description=(
            "docx: la constancia (retrocompatible). zip: constancia + "
            "registro.csv del autor en un solo paquete (hallazgo 11: "
            "'la constancia podría incluirlo')"
        ),
    ),
) -> Response:
    datos = _constancias_de_solicitud(solicitud)
    if solicitud.indice_autor >= len(datos):
        raise HTTPException(
            status_code=422,
            detail=(
                f"indice_autor={solicitud.indice_autor} fuera de rango: "
                f"la ficha trae {len(datos)} autor(es)."
            ),
        )
    objetivo = datos[solicitud.indice_autor]
    inicio_cpu = time.perf_counter()
    try:
        if formato == "zip":
            return Response(
                content=constancia_en_zip(_ruta_plantilla_constancia(), objetivo),
                media_type="application/zip",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{_nombre_archivo_constancia(objetivo)}.zip"'
                    )
                },
            )
        contenido = llenar_constancia(_ruta_plantilla_constancia(), objetivo)
    except ErrorConfiguracionConstancia as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        _LIMITADOR_CPU_PAPELES.registrar_coste(time.perf_counter() - inicio_cpu)
    return Response(
        content=contenido,
        media_type=MIME_DOCX_CONSTANCIA,
        headers={
            "Content-Disposition": f'attachment; filename="{_nombre_archivo_constancia(objetivo)}"'
        },
    )


@app.post(
    "/fila-registro",
    response_model=FilasRegistroResponse,
    summary="Generar las filas del registro (TSV, una por autor)",
    description=(
        "Devuelve las filas listas para pegar en el registro oficial de la "
        "biblioteca (XLSX): una por autor, en el orden exacto de columnas. "
        "La app JAMÁS escribe el registro oficial: el operador pega la fila. "
        "Con `formato` en `tsv`, `csv` o `xlsx` devuelve en su lugar un "
        "ARCHIVO descargable listo para abrir en Excel/LibreOffice "
        "(hallazgo 11 de la revisión del PR #55): elimina los errores de "
        "pegado (encoding, tabs perdidos, columnas desalineadas)."
    ),
    responses={
        200: {"description": "Lista de filas TSV (json) o archivo descargable (tsv/csv/xlsx)"},
        403: {"description": "Petición desde otro equipo o sin token válido"},
        422: {"description": "Timestamp inválido, falta un dato de la ficha o formato desconocido"},
        429: {"description": "Demasiadas generaciones de documentos seguidas"},
        500: {"description": "Firma sin configurar en el servidor"},
    },
    dependencies=[Depends(verificar_acceso_local), Depends(limitar_papeleo)],
)
async def generar_fila_registro(
    solicitud: FilaRegistroRequest,
    formato: Literal["json", "tsv", "csv", "xlsx"] = Query(
        default="json",
        description="json: la lista TSV (retrocompatible). tsv/csv/xlsx: archivo descargable",
    ),
):
    datos = _constancias_de_solicitud(solicitud)
    inicio_cpu = time.perf_counter()
    try:
        filas = [d.fila_registro() for d in datos]

        if formato == "json":
            return FilasRegistroResponse(filas=filas)

        if formato == "tsv":
            return Response(
                content=filas_a_tsv(filas).encode("utf-8"),
                media_type="text/tab-separated-values; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="registro_vistobueno.tsv"'},
            )
        if formato == "csv":
            return Response(
                content=filas_a_csv(filas).encode("utf-8"),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="registro_vistobueno.csv"'},
            )
        # formato == "xlsx"
        return Response(
            content=filas_a_xlsx(filas),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="registro_vistobueno.xlsx"'},
        )
    finally:
        _LIMITADOR_CPU_PAPELES.registrar_coste(time.perf_counter() - inicio_cpu)


# ---------------------------------------------------------------------------
# Punto de entrada para ejecución directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    # Bind local por defecto: la API maneja datos personales y documentos
    # oficiales. Para exponerla en la red hay que pedirlo explícitamente
    # (VISTOBUENO_HOST) y definir el token.
    # `proxy_headers=False`: un X-Forwarded-For no puede falsificar el
    # peer y saltar el control de loopback (ver README).
    host = (os.environ.get("VISTOBUENO_HOST") or "127.0.0.1").strip()
    if not _es_loopback(host) and not _token_api():
        raise SystemExit(
            "VISTOBUENO_HOST expone la API fuera de la máquina local: "
            "define VISTOBUENO_API_TOKEN antes de arrancar."
        )
    uvicorn.run(app, host=host, port=8000, proxy_headers=False)
