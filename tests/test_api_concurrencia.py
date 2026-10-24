"""Tests de concurrencia del endpoint POST /validar (Semana 7, hallazgo B2).

El endpoint es `async def`. Si el motor de reglas o el envío SMTP corren en
el hilo del event loop, la API completa deja de responder mientras dura cada
validación, y hasta TIMEOUT_SEGUNDOS extra por request si el servidor SMTP
está caído.

Contrato fijado aquí: el trabajo bloqueante se despacha al threadpool
(`fastapi.concurrency.run_in_threadpool`) y NUNCA corre en el hilo del
event loop. La verificación es estructural, no de timing: desde un hilo de
trabajo `asyncio.get_running_loop()` lanza RuntimeError; desde el hilo del
loop en ejecución devuelve el loop.
"""

import asyncio

from conftest import CLIENTE, MIME_DOCX
from docx_factory import compilar_docx, configuracion_base

import validator.api
from validator.models import RuleResult, Severity
from validator.notificacion import ResultadoEnvio


def _docx_bytes() -> bytes:
    """Bytes del documento bueno del factory (sin depender de recursos/)."""
    with open(compilar_docx(configuracion_base()), "rb") as f:
        return f.read()


def _corrio_en_event_loop() -> bool:
    """True si el hilo actual es el del event loop (donde NO debe correr)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _resultado_rojo() -> list[RuleResult]:
    """Un solo resultado de error: fuerza semáforo rojo en la respuesta."""
    return [
        RuleResult(
            rule_id="margen_superior",
            passed=False,
            severity=Severity.ERROR,
            message="Margen superior incorrecto",
            expected="3 cm",
            found="2.5 cm",
        )
    ]


class TestTrabajoBloqueanteFueraDelEventLoop:
    def test_el_motor_no_corre_en_el_event_loop(self, monkeypatch):
        """validate_docx debe correr en un hilo de trabajo, no en el loop."""
        en_loop: dict = {}

        def validate_docx_sonda(docx_path, rules_data, ficha_data=None):
            en_loop["motor"] = _corrio_en_event_loop()
            return []

        monkeypatch.setattr(validator.api, "validate_docx", validate_docx_sonda)
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("tesis.docx", _docx_bytes(), MIME_DOCX)},
        )

        assert respuesta.status_code == 200
        assert en_loop.get("motor") is False, (
            "validate_docx corrió en el hilo del event loop: bloquea toda la API mientras valida"
        )

    def test_el_envio_smtp_no_corre_en_el_event_loop(self, monkeypatch):
        """enviar_notificacion (smtplib bloqueante) debe ir al threadpool."""
        en_loop: dict = {}

        def validate_docx_sonda(docx_path, rules_data, ficha_data=None):
            en_loop["motor"] = _corrio_en_event_loop()
            return _resultado_rojo()

        def enviar_sonda(respuesta, destino, config=None):
            en_loop["smtp"] = _corrio_en_event_loop()
            return ResultadoEnvio(enviado=True, detalle=None)

        monkeypatch.setattr(validator.api, "validate_docx", validate_docx_sonda)
        monkeypatch.setattr(validator.api, "enviar_notificacion", enviar_sonda)
        monkeypatch.setenv("VISTOBUENO_NOTIFICACIONES", "1")
        monkeypatch.setenv("VISTOBUENO_SMTP_HOST", "127.0.0.1")
        monkeypatch.setenv("VISTOBUENO_SMTP_STARTTLS", "false")

        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("tesis.docx", _docx_bytes(), MIME_DOCX)},
            data={"correo": "estudiante@unitru.edu.pe", "notificar": "true"},
        )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        # El rojo y el opt-in garantizan que la sonda SMTP se haya invocado
        assert cuerpo["semaforo"] == "rojo"
        assert cuerpo["notificacion"]["estado"] == "enviado"
        assert en_loop.get("smtp") is False, (
            "enviar_notificacion corrió en el hilo del event loop: "
            "un SMTP caído congelaría la API hasta por 10 s por request"
        )
