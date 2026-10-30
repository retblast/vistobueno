"""Depósito de documentos validados en DSpace (Actividad 10).

DEPRECADO (decisión del equipo, 2026-10-28): la app NO escribe en la API
de DSpace. El flujo vigente es ficha (SPA) → buzón → userscript; el
archivo lo adjunta el encargado en el formulario oficial. Este módulo se
conserva como evidencia de la Actividad 10 y NO se usa en producción
(validator/api.py no lo importa: `depositar=true` responde "deshabilitado").

Módulo de la capa API que deposita el documento de un estudiante en el
repositorio institucional DSpace de la UNT cuando la validación termina
en semáforo verde. Deshabilitado por defecto: solo deposita cuando
VISTOBUENO_DSPACE=1 y la configuración está completa.

Seguridad de credenciales:
    La configuración se lee EXCLUSIVAMENTE de variables de entorno del
    proceso (os.environ). El módulo nunca carga archivos .env, por lo que no
    existe razón legítima para que uno viva en el repo. La filtración de
    VISTOBUENO_DSPACE_PASSWORD (y del usuario de la cuenta de servicio)
    está bloqueada por el hook de pre-commit (scripts/verificar_secretos.py)
    y por un paso de escaneo en la CI.

El depósito es best-effort: un fallo NUNCA debe romper la respuesta HTTP
de POST /validar (ver wiring en validator/api.py).

Alcance (ver docs/DSPACE_API.md §4 y §8): el flujo sigue el contrato REST
de DSpace 7/8 — login JWT con par CSRF, workspaceitem en la colección
destino, metadatos vía JSON Patch, aceptación de licencia y depósito al
workflow — y está verificado contra un stub local del contrato HAL
(tests/test_dspace.py). La validación contra la instancia institucional
real queda pendiente de la gestión ante la sede: cuenta de servicio,
excepción de la barrera antibot para /server/api y confirmación de las
colecciones destino y del nombre de la sección del formulario
(DSPACE_API.md §7).
"""

import os
import re
from pathlib import Path
from typing import IO, NamedTuple

import httpx

# ---------------------------------------------------------------------------
# Configuración (solo variables de entorno)
# ---------------------------------------------------------------------------

# Nombre de la sección de metadatos del formulario de depósito en DSpace
# 7/8. Es configuración por instancia: en el repositorio de la UNT la
# sección confirmada es `traditionalPeruOne` (el típico
# `traditionalpageone` NO aplica; ver docs/DSPACE_API.md §4).
SECCION_FORMULARIO_POR_DEFECTO = "traditionalPeruOne"

TIMEOUT_SEGUNDOS_POR_DEFECTO = 30

# Variables de entorno requeridas (además del flag VISTOBUENO_DSPACE).
VARS_REQUERIDAS = (
    "VISTOBUENO_DSPACE_URL",
    "VISTOBUENO_DSPACE_USER",
    "VISTOBUENO_DSPACE_PASSWORD",
    "VISTOBUENO_DSPACE_COLECCION",
)

# Cookie y header del par CSRF que exige DSpace para las operaciones de
# escritura (docs/DSPACE_API.md §2.2).
COOKIE_XSRF = "DSPACE-XSRF-COOKIE"
HEADER_XSRF = "X-XSRF-TOKEN"

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ConfigDSpace:
    """Configuración del depósito leída de variables de entorno.

    Atributos:
        habilitado: Flag de habilitación (VISTOBUENO_DSPACE=1).
        base_url: Base de la API REST (p. ej.
            ``https://repositorio.unitru.edu.pe/server/api``).
        usuario: Cuenta de servicio con permiso de envío (Submit).
        password: Contraseña de la cuenta. NUNCA se commitea al repo.
        coleccion: UUID de la colección destino del depósito.
        seccion: Sección del formulario donde viven los metadatos
            (default ``traditionalpageone``, configuración por instancia).
        timeout: Timeout por solicitud HTTP, en segundos.
        transport: Transporte httpx inyectable (tests). None en producción.
    """

    def __init__(
        self,
        habilitado: bool = False,
        base_url: str = "",
        usuario: str = "",
        password: str = "",
        coleccion: str = "",
        seccion: str = SECCION_FORMULARIO_POR_DEFECTO,
        timeout: float = TIMEOUT_SEGUNDOS_POR_DEFECTO,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.habilitado = habilitado
        self.base_url = base_url
        self.usuario = usuario
        self.password = password
        self.coleccion = coleccion
        self.seccion = seccion
        self.timeout = timeout
        self.transport = transport

    @classmethod
    def desde_entorno(cls, transport: httpx.BaseTransport | None = None) -> ConfigDSpace:
        """Construye la configuración desde os.environ.

        El flag acepta 1/true/yes (mismo criterio que
        VISTOBUENO_NOTIFICACIONES desde el hallazgo B4). El timeout es
        defensivo: un valor no numérico cae al default en lugar de romper
        el request.
        """
        try:
            timeout = float(
                os.environ.get("VISTOBUENO_DSPACE_TIMEOUT", str(TIMEOUT_SEGUNDOS_POR_DEFECTO))
            )
        except ValueError:
            timeout = TIMEOUT_SEGUNDOS_POR_DEFECTO
        return cls(
            habilitado=os.environ.get("VISTOBUENO_DSPACE", "").strip().lower()
            in ("1", "true", "yes"),
            base_url=os.environ.get("VISTOBUENO_DSPACE_URL", ""),
            usuario=os.environ.get("VISTOBUENO_DSPACE_USER", ""),
            password=os.environ.get("VISTOBUENO_DSPACE_PASSWORD", ""),
            coleccion=os.environ.get("VISTOBUENO_DSPACE_COLECCION", ""),
            seccion=os.environ.get("VISTOBUENO_DSPACE_SECCION", SECCION_FORMULARIO_POR_DEFECTO),
            timeout=timeout,
            transport=transport,
        )

    @property
    def faltantes(self) -> list[str]:
        """Nombres de las variables requeridas sin valor configurado."""
        valores = {
            "VISTOBUENO_DSPACE_URL": self.base_url,
            "VISTOBUENO_DSPACE_USER": self.usuario,
            "VISTOBUENO_DSPACE_PASSWORD": self.password,
            "VISTOBUENO_DSPACE_COLECCION": self.coleccion,
        }
        return [var for var, valor in valores.items() if not valor]

    @property
    def enabled(self) -> bool:
        """True solo si el flag está activo y la configuración está completa."""
        return self.habilitado and not self.faltantes


# ---------------------------------------------------------------------------
# Resultado y errores del dominio
# ---------------------------------------------------------------------------


class ResultadoDeposito(NamedTuple):
    """Resultado de un intento de depósito.

    Atributos:
        enviado: True si DSpace aceptó el ítem en su cola de aprobación.
        detalle: Motivo técnico del fallo (o del descarte); en el caso de
            éxito, nota de seguimiento (el ítem queda en revisión de la
            sede). Pensado para el personal del repositorio.
    """

    enviado: bool
    detalle: str | None


class ErrorDeposito(Exception):
    """Fallo del contrato REST de DSpace (status HTTP no 2xx o respuesta inesperada)."""


# ---------------------------------------------------------------------------
# Metadatos del formulario → JSON Patch del workspaceitem
# ---------------------------------------------------------------------------


def metadatos_desde_formulario(
    titulo: str | None = None,
    autores: str | None = None,
    asesor: str | None = None,
    resumen: str | None = None,
    palabras_clave: str | None = None,
) -> dict[str, list[str]]:
    """Convierte los campos del formulario del operador al mapa DSpace.

    Los campos son opcionales: se envían solo los que lleguen con contenido.
    ``autores`` y ``palabras_clave`` aceptan varios valores separados por
    ``;`` o saltos de línea (autores) y ``;`` o ``,`` (palabras clave).

    Returns:
        Mapa clave de metadato → lista ordenada de valores, listo para
        ``operaciones_metadatos``.
    """
    metadatos: dict[str, list[str]] = {}
    if titulo and titulo.strip():
        metadatos["dc.title"] = [titulo.strip()]
    if autores and autores.strip():
        valores = [a.strip() for a in re.split(r"[;\n]", autores) if a.strip()]
        if valores:
            metadatos["dc.contributor.author"] = valores
    if asesor and asesor.strip():
        metadatos["dc.contributor.advisor"] = [asesor.strip()]
    if resumen and resumen.strip():
        metadatos["dc.description.abstract"] = [resumen.strip()]
    if palabras_clave and palabras_clave.strip():
        valores = [p.strip() for p in re.split(r"[;,]", palabras_clave) if p.strip()]
        if valores:
            metadatos["dc.subject"] = valores
    return metadatos


def operaciones_metadatos(
    metadatos: dict[str, list[str]],
    seccion: str = SECCION_FORMULARIO_POR_DEFECTO,
) -> list[dict]:
    """Convierte el mapa de metadatos en operaciones JSON Patch (RFC 6902).

    DSpace inicializa cada metadato con una operación ``add`` cuyo path
    apunta a la sección del formulario y cuyo valor es la lista completa
    de valores (docs/DSPACE_API.md §4.2).
    """
    return [
        {
            "op": "add",
            "path": f"/sections/{seccion}/{clave}",
            "value": [{"value": v} for v in valores],
        }
        for clave, valores in metadatos.items()
    ]


# ---------------------------------------------------------------------------
# Cliente del contrato REST de DSpace (JWT + CSRF)
# ---------------------------------------------------------------------------


class ClienteDSpace:
    """Cliente mínimo del contrato REST de DSpace 7/8.

    Implementa solo el flujo de depósito (docs/DSPACE_API.md §4): login
    JWT con par CSRF, creación del workspaceitem (con el archivo), escritura
    de metadatos vía JSON Patch, aceptación de licencia y depósito al
    workflow. Las respuestas son HAL+JSON; solo se lee lo que el flujo
    necesita (el ``id`` del workspaceitem).
    """

    def __init__(self, config: ConfigDSpace) -> None:
        self._config = config
        self._http = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
            transport=config.transport,
        )
        self._token: str = ""

    def __enter__(self) -> ClienteDSpace:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        """Cierra la conexión HTTP del cliente."""
        self._http.close()

    # --- Piezas comunes del contrato ---

    def _xsrf(self) -> str:
        """Token CSRF vigente (valor de la cookie que DSpace entregó antes)."""
        valor = self._http.cookies.get(COOKIE_XSRF)
        return valor or ""

    def _asegurar_csrf(self) -> None:
        """Obtiene el par CSRF con una llamada sin efectos secundarios.

        ``GET /authn/status`` responde la cookie ``DSPACE-XSRF-COOKIE`` que
        el resto de las operaciones de escritura debe devolver en el header
        ``X-XSRF-TOKEN``.
        """
        if self._xsrf():
            return
        respuesta = self._http.get("/authn/status")
        self._verificar(respuesta, "obtener token CSRF")
        if not self._xsrf():
            raise ErrorDeposito("la API no entregó la cookie de CSRF")

    def _headers_escritura(self) -> dict[str, str]:
        """Cabeceras comunes de las operaciones autenticadas de escritura."""
        headers = {HEADER_XSRF: self._xsrf()}
        if self._token:
            headers["Authorization"] = self._token
        return headers

    def _verificar(self, respuesta: httpx.Response, paso: str) -> None:
        """Levanta ErrorDeposito con contexto si DSpace respondió error.

        El mensaje incluye el status y un recorte del cuerpo: los ``422``
        del formulario de depósito indican exactamente qué campo falló, y
        ese texto es el que el operador necesita ver en ``detalle``.
        """
        if respuesta.status_code >= 400:
            raise ErrorDeposito(f"{paso}: HTTP {respuesta.status_code} — {respuesta.text[:200]}")

    # --- Pasos del flujo de depósito ---

    def login(self) -> str:
        """Autentica a la cuenta de servicio y guarda el Bearer token.

        El login es ``POST`` con form-urlencoded y exige el par CSRF
        obtenido antes; el JWT llega en el header ``Authorization`` de la
        respuesta (docs/DSPACE_API.md §2.2).
        """
        self._asegurar_csrf()
        respuesta = self._http.post(
            "/authn/login",
            data={"user": self._config.usuario, "password": self._config.password},
            headers={HEADER_XSRF: self._xsrf()},
        )
        self._verificar(respuesta, "login")
        token = respuesta.headers.get("Authorization", "")
        if not token:
            raise ErrorDeposito("login: la respuesta no trae el header Authorization")
        self._token = token
        return token

    def crear_workspaceitem(self, archivo: Path) -> int:
        """Crea el envío en progreso en la colección destino, con el DOCX.

        Returns:
            El id del workspaceitem: identifica el resto del flujo.
        """
        contenido: IO[bytes]
        with open(archivo, "rb") as contenido:
            respuesta = self._http.post(
                "/submission/workspaceitems",
                params={"owningCollection": self._config.coleccion},
                files={"file": (archivo.name, contenido, MIME_DOCX)},
                headers=self._headers_escritura(),
            )
        self._verificar(respuesta, "crear workspaceitem")
        item_id = respuesta.json().get("id")
        if item_id is None:
            raise ErrorDeposito("workspaceitem: la respuesta no trae id")
        return int(item_id)

    def escribir_metadatos(self, item_id: int, operaciones: list[dict]) -> None:
        """Aplica las operaciones JSON Patch a la sección del formulario."""
        respuesta = self._http.patch(
            f"/submission/workspaceitems/{item_id}",
            json=operaciones,
            headers=self._headers_escritura(),
        )
        self._verificar(respuesta, "escribir metadatos")

    def aceptar_licencia(self, item_id: int) -> None:
        """Acepta la licencia de distribución del envío.

        TODO(Actividad 10, primera validación real): confirmar el endpoint
        exacto de la instancia (docs/DSPACE_API.md §4.2); hoy se usa el
        ``POST`` de la sección de licencia del workspaceitem.
        """
        respuesta = self._http.post(
            f"/submission/workspaceitems/{item_id}/license",
            headers=self._headers_escritura(),
        )
        self._verificar(respuesta, "aceptar licencia")

    def depositar_workflow(self, item_id: int) -> None:
        """Envía el workspaceitem al workflow de aprobación de la sede.

        TODO(Actividad 10, primera validación real): confirmar el payload
        exacto contra la instancia; hoy se envía el id en el cuerpo.
        """
        respuesta = self._http.post(
            "/workflow/workflowitems",
            json={"workspaceItemId": item_id},
            headers=self._headers_escritura(),
        )
        self._verificar(respuesta, "depositar al workflow")


# ---------------------------------------------------------------------------
# Depósito (best-effort: nunca lanza)
# ---------------------------------------------------------------------------


def depositar_documento(
    ruta_docx: str | Path,
    metadatos: dict[str, list[str]] | None = None,
    config: ConfigDSpace | None = None,
) -> ResultadoDeposito:
    """Deposita el documento validado en DSpace y devuelve el veredicto.

    Flujo: login → workspaceitem (con el .docx) → metadatos (JSON Patch)
    → licencia → workflow. Devuelve ResultadoDeposito(True, nota) si DSpace
    aceptó el ítem (queda en cola de aprobación de la sede); en cualquier
    otro caso devuelve ResultadoDeposito(False, motivo). NUNCA lanza: un
    fallo del depósito no debe romper la respuesta HTTP de POST /validar.

    Args:
        ruta_docx: Ruta del .docx validado (el archivo temporal del request).
        metadatos: Mapa clave → lista de valores (ver
            ``metadatos_desde_formulario``). None o vacío salta la escritura.
        config: Configuración explícita (tests/scripts); por defecto se lee
            del entorno.

    Returns:
        ResultadoDeposito con el veredicto y, si falló, el motivo.
    """
    cfg = config if config is not None else ConfigDSpace.desde_entorno()
    if not cfg.enabled:
        faltan = ", ".join(cfg.faltantes)
        return ResultadoDeposito(
            enviado=False,
            detalle=f"depósito deshabilitado o sin configurar (faltan: {faltan})",
        )

    try:
        with ClienteDSpace(cfg) as cliente:
            cliente.login()
            item_id = cliente.crear_workspaceitem(Path(ruta_docx))
            if metadatos:
                cliente.escribir_metadatos(item_id, operaciones_metadatos(metadatos, cfg.seccion))
            cliente.aceptar_licencia(item_id)
            cliente.depositar_workflow(item_id)
        return ResultadoDeposito(
            enviado=True,
            detalle="el ítem quedó en la cola de aprobación de la sede",
        )
    except Exception as e:
        # Best-effort: NUNCA lanza (mismo criterio que enviar_notificacion,
        # hallazgo B5). Se registra el motivo técnico para que la respuesta
        # de la API pueda exponerlo al personal del repositorio.
        return ResultadoDeposito(enviado=False, detalle=f"{type(e).__name__}: {e}")
