"""Tests unitarios del módulo de notificación (validator/notificacion.py).

Cobertura:
- ConfigSMTP: defaults (deshabilitado), activación por entorno, parsing
  defensivo de puerto.
- plantilla_correo: registro formal, escape HTML de contenido adversario,
  inclusión de rule_id/cita/ubicación, versión texto plano, caso defensivo
  verde.
- enviar_notificacion: envío mocked (encabezados Date/Message-ID, From/To,
  STARTTLS/login condicionales), fallo best-effort (nunca lanza, expone
  motivo en detalle), deshabilitado por defecto.
- Guardia de contrato: POST /validar expone el estado de la notificación
  (campo `notificacion` con `estado` y `detalle`).
- E2E: POST /validar contra un sink SMTP real (aiosmtpd) — enviado,
  deshabilitado, fallo de conexión y sin correo.
"""

import email
import html
import smtplib
import socket

import pytest
from aiosmtpd.controller import Controller
from conftest import CLIENTE, MIME_DOCX
from docx_factory import aplicar_mutacion, compilar_docx, configuracion_base

from validator.api_models import ValidarResponse
from validator.notificacion import (
    ConfigSMTP,
    enviar_notificacion,
    plantilla_correo,
)

# Variables de entorno SMTP relevantes. Los tests las limpian/establecen de
# forma aislada (defensivo contra la configuración de cada máquina).
VARS_ENTORNO_SMTP = (
    "VISTOBUENO_SMTP_HOST",
    "VISTOBUENO_SMTP_PORT",
    "VISTOBUENO_SMTP_USER",
    "VISTOBUENO_SMTP_PASSWORD",
    "VISTOBUENO_SMTP_STARTTLS",
    "VISTOBUENO_CORREO_REMITENTE",
    "VISTOBUENO_NOTIFICACIONES",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def dto_rojo() -> ValidarResponse:
    """DTO de ejemplo con 2 reglas fallidas (una con contenido adversario)."""
    return ValidarResponse.model_validate(
        {
            "semaforo": "rojo",
            "resumen": {
                "total": 47,
                "total_evaluadas": 46,
                "reglas_no_aplicables": 1,
                "fallidos_error": 2,
                "fallidos_warning": 1,
            },
            "resultados": [
                {
                    "rule_id": "papel_tamano",
                    "paso": False,
                    "severidad": "error",
                    "mensaje": "Tamaño de papel incorrecto <script>alert('xss')</script>",
                    "esperado": "210 x 297 mm",
                    "encontrado": "216 x 279 mm",
                    "ubicacion": 'Sección "Formato general" (párr. 124-125)',
                    "fuente": "MANUAL.docx",
                    "cita": '"Tamaño A4/papel (210x297 cm)"',
                    "aplicable": True,
                },
                {
                    "rule_id": "fuente_cuerpo",
                    "paso": False,
                    "severidad": "warning",
                    "mensaje": "Fuente del cuerpo distinta a Arial",
                    "esperado": "Arial 12",
                    "encontrado": "Times New Roman 12",
                    "ubicacion": None,
                    "fuente": "",
                    "cita": "",
                    "aplicable": True,
                },
                {
                    "rule_id": "margen_superior",
                    "paso": True,
                    "severidad": "error",
                    "mensaje": "Margen superior correcto",
                    "esperado": "",
                    "encontrado": "cumple",
                    "ubicacion": None,
                    "fuente": "",
                    "cita": "",
                    "aplicable": True,
                },
            ],
            "como_preguntar_a_una_ia": [],
            "metadatos": {
                "archivo_nombre": "tesis_prueba.docx",
                "archivo_tamano_bytes": 1024,
                "reglas_evaluadas": 46,
                "reglas_totales": 47,
                "version_esquema": "2026-09-01",
                "tipo_documento_declarado": None,
                "tipo_documento_inferido": None,
                "tipo_documento_estado": "vigente",
            },
        }
    )


def dto_verde() -> ValidarResponse:
    """DTO defensivo: todo pasa (el wiring solo debe enviar en rojo)."""
    return ValidarResponse.model_validate(
        {
            "semaforo": "verde",
            "resumen": {
                "total": 47,
                "total_evaluadas": 46,
                "reglas_no_aplicables": 1,
                "fallidos_error": 0,
                "fallidos_warning": 0,
            },
            "resultados": [],
            "como_preguntar_a_una_ia": [],
            "metadatos": {
                "archivo_nombre": "tesis_ok.docx",
                "archivo_tamano_bytes": 1024,
                "reglas_evaluadas": 46,
                "reglas_totales": 47,
                "version_esquema": "2026-09-01",
                "tipo_documento_declarado": None,
                "tipo_documento_inferido": None,
                "tipo_documento_estado": "vigente",
            },
        }
    )


class SMTPFalso:
    """Doble de smtplib.SMTP que registra llamadas sin red."""

    instancias: list[SMTPFalso] = []

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.llamadas: list = []
        self.mensaje_enviado = None
        SMTPFalso.instancias.append(self)

    def starttls(self) -> None:
        self.llamadas.append("starttls")

    def login(self, usuario: str, clave: str) -> None:
        self.llamadas.append(("login", usuario, clave))

    def send_message(self, msg) -> None:
        self.mensaje_enviado = msg
        self.llamadas.append("send_message")

    def __enter__(self) -> SMTPFalso:
        return self

    def __exit__(self, *exc) -> None:
        return None


@pytest.fixture
def smtp_falso(monkeypatch):
    """Parchea smtplib.SMTP por el doble; expone las instancias creadas."""
    SMTPFalso.instancias = []
    monkeypatch.setattr(smtplib, "SMTP", SMTPFalso)
    return SMTPFalso


# ---------------------------------------------------------------------------
# ConfigSMTP
# ---------------------------------------------------------------------------


class TestConfigSMTP:
    def test_deshabilitado_por_defecto(self, monkeypatch):
        """Sin variables de entorno, el envío queda deshabilitado."""
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        cfg = ConfigSMTP.desde_entorno()
        assert cfg.enabled is False

    def test_habilitado_con_host_y_flag(self, monkeypatch):
        """Flag + host activan; el password no es necesario para 'enabled'."""
        monkeypatch.setenv("VISTOBUENO_SMTP_HOST", "smtp.unitru.edu.pe")
        monkeypatch.setenv("VISTOBUENO_SMTP_PORT", "587")
        monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", "1")
        cfg = ConfigSMTP.desde_entorno()
        assert cfg.enabled is True
        assert cfg.starttls is True

    def test_flag_sin_host_no_habilita(self, monkeypatch):
        monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", "1")
        monkeypatch.delenv("VISTOBUENO_SMTP_HOST", raising=False)
        assert ConfigSMTP.desde_entorno().enabled is False

    def test_puerto_no_numerico_cae_al_default(self, monkeypatch):
        monkeypatch.setenv("VISTOBUENO_SMTP_PORT", "no-numerico")
        assert ConfigSMTP.desde_entorno().port == 587

    def test_starttls_false_para_sink_local(self, monkeypatch):
        monkeypatch.setenv("VISTOBUENO_SMTP_HOST", "127.0.0.1")
        monkeypatch.setenv("VISTOBUENO_SMTP_STARTTLS", "false")
        monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", "1")
        cfg = ConfigSMTP.desde_entorno()
        assert cfg.starttls is False
        assert cfg.enabled is True

    def test_flag_acepta_true_yes_igual_que_starttls(self, monkeypatch):
        """B4: el flag acepta 1/true/yes (antes solo el literal "1").

        Sin esto, VISTOBUENO_NOTIFICACIONES=true dejaba el envío apagado
        sin ningún error visible, siendo STARTTLS más permisivo.
        """
        monkeypatch.setenv("VISTOBUENO_SMTP_HOST", "smtp.unitru.edu.pe")
        for valor in ("1", "true", "yes", "TRUE", " Yes "):
            monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", valor)
            assert ConfigSMTP.desde_entorno().notificaciones is True, valor
        for valor in ("", "0", "no", "off", "cualquier-cosa"):
            monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", valor)
            assert ConfigSMTP.desde_entorno().notificaciones is False, valor


# ---------------------------------------------------------------------------
# plantilla_correo
# ---------------------------------------------------------------------------


class TestPlantillaCorreo:
    def test_registro_formal_y_nombre(self):
        html_body, texto = plantilla_correo(dto_rojo())
        for cuerpo in (html_body, texto):
            assert "Estimado(a) estudiante" in cuerpo
            assert "tesis_prueba.docx" in cuerpo

    def test_contiene_reglas_fallidas_y_excluye_cumplidas(self):
        html_body, texto = plantilla_correo(dto_rojo())
        assert "papel_tamano" in html_body
        assert "fuente_cuerpo" in html_body
        # La regla que PASA no debe aparecer en la tabla de observaciones
        assert "margen_superior" not in html_body

    def test_escapa_html_adversario(self):
        html_body, texto = plantilla_correo(dto_rojo())
        assert "<script>" not in html_body
        # La forma escapada de "<script>" (html.escape) debe estar presente
        assert html.escape("<script>") in html_body
        # En texto plano el contenido adversario se conserva literal (es texto)
        assert "<script>alert('xss')</script>" in texto

    def test_contiene_valores_referencias_y_citas(self):
        html_body, _ = plantilla_correo(dto_rojo())
        assert "210 x 297 mm" in html_body
        assert "216 x 279 mm" in html_body
        assert "Formato general" in html_body
        assert "210x297 cm" in html_body  # cita
        assert "<strong>error</strong>" in html_body
        assert "<strong>warning</strong>" in html_body

    def test_caso_defensivo_verde(self):
        html_body, texto = plantilla_correo(dto_verde())
        assert "No se detectaron observaciones" in html_body
        assert "No se detectaron observaciones" in texto


# ---------------------------------------------------------------------------
# enviar_notificacion
# ---------------------------------------------------------------------------


class TestEnviarNotificacion:
    def test_deshabilitado_no_toca_smtp(self, smtp_falso):
        """Config sin flag: no envía, explica el motivo y jamás abre conexión."""
        cfg = ConfigSMTP(host="127.0.0.1", notificaciones=False)
        resultado = enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg)
        assert resultado.enviado is False
        assert "deshabilitadas" in resultado.detalle
        assert smtp_falso.instancias == []

    def test_envio_exitoso_arma_encabezados(self, smtp_falso):
        cfg = ConfigSMTP(
            host="127.0.0.1",
            port=8025,
            starttls=False,
            remitente="no-responder@unitru.edu.pe",
            notificaciones=True,
        )
        assert enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg).enviado is True
        (smtp,) = smtp_falso.instancias
        assert (smtp.host, smtp.port) == ("127.0.0.1", 8025)
        assert "send_message" in smtp.llamadas
        msg = smtp.mensaje_enviado
        # Encabezados que smtplib NO agrega y los servidores reales exigen
        assert msg["Date"] is not None
        assert msg["Message-ID"] is not None
        assert str(msg["From"]) == "no-responder@unitru.edu.pe"
        assert str(msg["To"]) == "destino@prueba.local"
        assert "tesis_prueba.docx" in str(msg["Subject"])
        assert msg.is_multipart()  # multipart/alternative (texto + HTML)

    def test_starttls_y_login_condicionales(self, smtp_falso):
        cfg = ConfigSMTP(
            host="smtp.unitru.edu.pe",
            port=587,
            user="vistobueno",
            password="clave-de-prueba",
            starttls=True,
            notificaciones=True,
        )
        assert enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg).enviado is True
        (smtp,) = smtp_falso.instancias
        assert "starttls" in smtp.llamadas
        assert ("login", "vistobueno", "clave-de-prueba") in smtp.llamadas

    def test_sin_starttls_no_lo_negocia(self, smtp_falso):
        cfg = ConfigSMTP(host="127.0.0.1", starttls=False, notificaciones=True)
        enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg)
        (smtp,) = smtp_falso.instancias
        assert "starttls" not in smtp.llamadas
        assert not any(llamada.startswith("login") for llamada in smtp.llamadas)

    def test_fallo_smtp_es_best_effort(self, monkeypatch):
        """Conexión rechazada (OSError): retorna False, nunca lanza."""

        class SMTPRoto:
            def __init__(self, *args, **kwargs):
                raise ConnectionRefusedError("conexion rechazada")

        monkeypatch.setattr(smtplib, "SMTP", SMTPRoto)
        cfg = ConfigSMTP(host="127.0.0.1", notificaciones=True)
        resultado = enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg)
        assert resultado.enviado is False
        # El motivo técnico queda expuesto para el personal del repositorio
        assert "ConnectionRefusedError" in resultado.detalle

    def test_error_smtp_en_login_tambien_es_best_effort(self, monkeypatch):
        class SMTPAuthRoto:
            def __init__(self, *args, **kwargs):
                pass

            def starttls(self):
                pass

            def login(self, u, p):
                raise smtplib.SMTPAuthenticationError(code=535, msg="credenciales rechazadas")

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return None

        monkeypatch.setattr(smtplib, "SMTP", SMTPAuthRoto)
        cfg = ConfigSMTP(host="smtp.unitru.edu.pe", user="u", password="p", notificaciones=True)
        resultado = enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg)
        assert resultado.enviado is False
        assert "SMTPAuthenticationError" in resultado.detalle

    def test_nombre_con_saltos_de_linea_no_inyecta_cabeceras(self, smtp_falso):
        """B5: CR/LF en el nombre del archivo (viene del multipart) no puede
        inyectar cabeceras ni romper el envío: se neutraliza en el Subject."""
        dto = dto_rojo()
        dto.metadatos.archivo_nombre = "tesis\r\nBcc: victima@spam.example"
        cfg = ConfigSMTP(host="127.0.0.1", starttls=False, notificaciones=True)

        resultado = enviar_notificacion(dto, "destino@prueba.local", cfg)

        # El envío no se rompió (antes: ValueError escapaba del best-effort)
        assert resultado.enviado is True
        (smtp,) = smtp_falso.instancias
        msg = smtp.mensaje_enviado
        # El texto hostil quedó DENTRO del Subject, sin salto de línea...
        asunto = str(msg["Subject"])
        assert "Bcc:" in asunto
        assert "\r" not in asunto and "\n" not in asunto
        # ...y jamás llegó a ser una cabecera propia del mensaje
        assert msg["Bcc"] is None

    def test_error_del_armado_del_mensaje_es_best_effort(self, monkeypatch):
        """B5: cualquier fallo del armado (no solo SMTP) no debe lanzar.

        La plantilla y las cabeceras se arman dentro del try: un ValueError
        ahí escapaba y rompía la respuesta HTTP de POST /validar.
        """

        def plantilla_rota(respuesta):
            raise ValueError("plantilla rota")

        monkeypatch.setattr("validator.notificacion.plantilla_correo", plantilla_rota)
        cfg = ConfigSMTP(host="127.0.0.1", notificaciones=True)
        resultado = enviar_notificacion(dto_rojo(), "destino@prueba.local", cfg)
        assert resultado.enviado is False
        assert "ValueError" in resultado.detalle


# ---------------------------------------------------------------------------
# Guardia de contrato: la respuesta de /validar expone la notificación
# ---------------------------------------------------------------------------


class TestGuardiaContrato:
    def test_respuesta_expone_estado_de_notificacion(self, monkeypatch):
        """El esquema incluye `notificacion` (estado + detalle)."""
        # Defensivo: si el entorno del desarrollador tiene SMTP configurado,
        # el estado cambiaría. monkeypatch revierte al salir del test.
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        with open(compilar_docx(configuracion_base()), "rb") as f:
            respuesta = CLIENTE.post(
                "/validar",
                files={
                    "archivo": (
                        "tesis.docx",
                        f,
                        MIME_DOCX,
                    )
                },
                data={"correo": "estudiante@unitru.edu.pe"},
            )
        assert respuesta.status_code == 200
        assert set(respuesta.json().keys()) == {
            "semaforo",
            "notificacion",
            "deposito",
            "ficha_deposito",
            "resumen",
            "resultados",
            "como_preguntar_a_una_ia",
            "metadatos",
        }
        # v1.7.0: este documento base da semáforo verde → la ficha
        # materializa; con rojo sería null (invariante).
        assert respuesta.json()["ficha_deposito"] is not None
        # Documento base con rojo + correo válido, pero sin opt-in del
        # operador: el envío es explícito (`notificar`), no automático.
        notificacion = respuesta.json()["notificacion"]
        assert notificacion == {"estado": "no_solicitado", "detalle": None}


# ---------------------------------------------------------------------------
# E2E: POST /validar contra un sink SMTP real (aiosmtpd)
# ---------------------------------------------------------------------------


class _BuzonSink:
    """Handler de aiosmtpd que acumula los mensajes recibidos."""

    def __init__(self):
        self.recibidos: list = []

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        self.recibidos.append(envelope)
        return "250 Message accepted for delivery"


@pytest.fixture
def sink_smtp():
    """Levanta un sink SMTP real (aiosmtpd) en 127.0.0.1 con puerto libre.

    aiosmtpd 1.4.6 no soporta port=0 (no actualiza Controller.port tras el
    bind y su propio trigger de arranque falla), así que el puerto libre se
    reserva manualmente antes de crear el controlador.
    """
    with socket.socket() as reservado:
        reservado.bind(("127.0.0.1", 0))
        puerto = reservado.getsockname()[1]
    buzon = _BuzonSink()
    controlador = Controller(buzon, hostname="127.0.0.1", port=puerto)
    controlador.start()
    try:
        yield buzon, puerto
    finally:
        controlador.stop()


# Regla que se desvía para obtener el semáforo rojo. Se elige una regla
# mecánica y no una de estructura porque las estructuras están condicionadas
# al tipo documental: el documento base es un plan cuantitativo, así que las
# estructuras de los otros dos tipos de TINV ya no le aplican y no pueden
# usarse para ponerlo en rojo. Antes de `aplicar_si` sí lo hacían, y por eso
# este fixture quedó obsoleto al condicionarlas.
REGLA_ROJA = "margen_superior"


def _docx_rojo() -> bytes:
    """Bytes de un documento con semáforo rojo.

    Se parte del documento bueno y se le aplica una sola desviación
    (márgen superior), de modo que el rojo lo produzca un incumplimiento real
    y no una estructura que no le corresponde.
    """
    with open(compilar_docx(aplicar_mutacion(REGLA_ROJA, configuracion_base())), "rb") as f:
        return f.read()


def _post_validar(docx: bytes, correo: str | None = None, notificar: bool = False):
    """POST /validar con el DOCX dado y, opcionalmente, correo y opt-in."""
    data = {}
    if correo is not None:
        data["correo"] = correo
    if notificar:
        data["notificar"] = "true"
    return CLIENTE.post(
        "/validar",
        files={"archivo": ("tesis.docx", docx, MIME_DOCX)},
        data=data,
    )


def _apuntar_al_sink(monkeypatch, puerto: int) -> None:
    """Habilita las notificaciones apuntando al sink local (sin STARTTLS)."""
    monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", "1")
    monkeypatch.setenv("VISTOBUENO_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("VISTOBUENO_SMTP_PORT", str(puerto))
    monkeypatch.setenv("VISTOBUENO_SMTP_STARTTLS", "false")


class TestNotificacionEndToEnd:
    def test_rojo_con_correo_envia_al_estudiante(self, monkeypatch, sink_smtp):
        """Opt-in + rojo + correo + habilitado: envía y responde 'enviado'."""
        buzon, puerto = sink_smtp
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        _apuntar_al_sink(monkeypatch, puerto)

        # El destinatario es el correo normalizado: email-validator
        # minúscula el dominio pero conserva la parte local por diseño.
        respuesta = _post_validar(_docx_rojo(), "Estudiante@Unitru.edu.pe", notificar=True)

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["semaforo"] == "rojo"
        assert cuerpo["notificacion"] == {"estado": "enviado", "detalle": None}

        # El mensaje llegó al sink dirigido al estudiante
        (envelope,) = buzon.recibidos
        assert envelope.rcpt_tos == ["Estudiante@unitru.edu.pe"]
        mensaje = email.message_from_bytes(envelope.content, policy=email.policy.default)
        assert "Observaciones de formato" in str(mensaje["Subject"])
        cuerpo_texto = mensaje.get_body(preferencelist=("plain",)).get_content()
        assert "Estimado(a) estudiante" in cuerpo_texto
        # El HTML incluye el rule_id de cada regla fallida como referencia estable
        cuerpo_html = mensaje.get_body(preferencelist=("html",)).get_content()
        assert REGLA_ROJA in cuerpo_html

    def test_deshabilitado_no_envia_nada(self, monkeypatch, sink_smtp):
        """Opt-in + rojo + correo, pero notificaciones apagadas: 'deshabilitado'."""
        buzon, _puerto = sink_smtp
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)

        respuesta = _post_validar(_docx_rojo(), "estudiante@unitru.edu.pe", notificar=True)

        assert respuesta.status_code == 200
        notificacion = respuesta.json()["notificacion"]
        assert notificacion["estado"] == "deshabilitado"
        # B3: nota de configuración para el personal del repositorio
        assert notificacion["detalle"] is not None
        assert "VISTOBUENO_NOTIFICACIONES" in notificacion["detalle"]
        assert buzon.recibidos == []

    def test_fallo_smtp_no_rompe_la_respuesta(self, monkeypatch):
        """SMTP caído: la respuesta sigue 200 con estado 'fallo' y motivo."""
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        _apuntar_al_sink(monkeypatch, puerto=1)  # nada escucha en el puerto 1

        respuesta = _post_validar(_docx_rojo(), "estudiante@unitru.edu.pe", notificar=True)

        assert respuesta.status_code == 200
        notificacion = respuesta.json()["notificacion"]
        assert notificacion["estado"] == "fallo"
        assert notificacion["detalle"]
        assert "ConnectionRefusedError" in notificacion["detalle"]

    def test_sin_correo_no_intenta_envio(self, monkeypatch, sink_smtp):
        """Sin campo correo: estado 'sin_correo' y el sink no recibe nada."""
        buzon, puerto = sink_smtp
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        _apuntar_al_sink(monkeypatch, puerto)

        respuesta = _post_validar(_docx_rojo())

        assert respuesta.status_code == 200
        notificacion = respuesta.json()["notificacion"]
        assert notificacion == {"estado": "sin_correo", "detalle": None}
        assert buzon.recibidos == []

    def test_notificar_sin_correo_sigue_sin_correo(self, monkeypatch, sink_smtp):
        """Opt-in sin correo: prima la falta de destinatario ('sin_correo')."""
        buzon, puerto = sink_smtp
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        _apuntar_al_sink(monkeypatch, puerto)

        respuesta = _post_validar(_docx_rojo(), notificar=True)

        assert respuesta.status_code == 200
        notificacion = respuesta.json()["notificacion"]
        assert notificacion == {"estado": "sin_correo", "detalle": None}
        assert buzon.recibidos == []

    def test_sin_opt_in_no_envia_nada(self, monkeypatch, sink_smtp):
        """Correo + rojo + habilitado, pero sin opt-in: 'no_solicitado'."""
        buzon, puerto = sink_smtp
        for var in VARS_ENTORNO_SMTP:
            monkeypatch.delenv(var, raising=False)
        _apuntar_al_sink(monkeypatch, puerto)

        respuesta = _post_validar(_docx_rojo(), "estudiante@unitru.edu.pe", notificar=False)

        assert respuesta.status_code == 200
        notificacion = respuesta.json()["notificacion"]
        assert notificacion == {"estado": "no_solicitado", "detalle": None}
        # El envío es opt-in: sin `notificar` jamás se abre la conexión SMTP
        assert buzon.recibidos == []
