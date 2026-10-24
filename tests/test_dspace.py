"""Tests del módulo de depósito en DSpace (validator/dspace.py).

Cobertura:
- ConfigDSpace: defaults (deshabilitado), activación por entorno
  (1/true/yes, mismo criterio que la notificación), variables requeridas
  y `faltantes` para la nota de configuración.
- metadatos_desde_formulario / operaciones_metadatos: mapeo form → JSON
  Patch, separadores múltiples, campos vacíos.
- depositar_documento: flujo completo contra un stub del contrato HAL
  (httpx.MockTransport): happy path con y sin metadatos, 401 de login,
  422 del formulario, error de conexión, cookie de CSRF ausente y
  deshabilitado sin tocar la red.
- Guardia de contrato: POST /validar expone `deposito` (estado + detalle)
  con los cinco estados del flujo de depósito.
"""

import json as json_mod
import urllib.parse

import httpx
from conftest import CLIENTE, MIME_DOCX
from docx_factory import aplicar_mutacion, compilar_docx, configuracion_base

from validator.dspace import (
    ConfigDSpace,
    ResultadoDeposito,
    depositar_documento,
    metadatos_desde_formulario,
    operaciones_metadatos,
)

# Variables de entorno del módulo. Los tests las limpian/establecen de forma
# aislada (defensivo contra la configuración de cada máquina).
VARS_ENTORNO_DSPACE = (
    "VISTOBUENO_DSPACE",
    "VISTOBUENO_DSPACE_URL",
    "VISTOBUENO_DSPACE_USER",
    "VISTOBUENO_DSPACE_PASSWORD",
    "VISTOBUENO_DSPACE_COLECCION",
    "VISTOBUENO_DSPACE_SECCION",
    "VISTOBUENO_DSPACE_TIMEOUT",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _limpiar_entorno(monkeypatch) -> None:
    for var in VARS_ENTORNO_DSPACE:
        monkeypatch.delenv(var, raising=False)


def _configurar_entorno_stub(monkeypatch, transport: httpx.BaseTransport | None = None) -> None:
    """Entorno completo apuntando a una URL cualquiera (el transporte se inyecta)."""
    monkeypatch.setenv("VISTOBUENO_DSPACE", "1")
    monkeypatch.setenv("VISTOBUENO_DSPACE_URL", "https://stub.local/server/api")
    monkeypatch.setenv("VISTOBUENO_DSPACE_USER", "servicio")
    monkeypatch.setenv("VISTOBUENO_DSPACE_PASSWORD", "secreto")
    monkeypatch.setenv("VISTOBUENO_DSPACE_COLECCION", "uuid-coleccion")


# ---------------------------------------------------------------------------
# Stub del contrato REST de DSpace 7/8 (HAL + JWT + CSRF)
# ---------------------------------------------------------------------------

XSRF_STUB = "xsrf-123"
JWT_STUB = "Bearer jwt-stub"
ID_WORKSPACEITEM = 17


class StubDSpace:
    """Stub con estado mínimo del contrato HAL de DSpace.

    Implementa el flujo de depósito con las reglas reales del contrato:
    status entrega la cookie XSRF; login exige el header X-XSRF-TOKEN y
    las credenciales válidas, y responde el Bearer; el workspaceitem exige
    autorización, colección y archivo; el PATCH aplica las operaciones
    (o responde 422 si el modo exige dc.title); la licencia y el workflow
    completan el flujo. Registra las llamadas para las aserciones.
    """

    def __init__(
        self,
        password_valida: str = "secreto",
        exigir_titulo: bool = False,
        login_sin_authorization: bool = False,
    ) -> None:
        self.password_valida = password_valida
        self.exigir_titulo = exigir_titulo
        self.login_sin_authorization = login_sin_authorization
        self.llamadas: list[tuple[str, str]] = []
        self.metadatos: dict[str, list[dict]] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.llamadas.append((request.method, request.url.path))
        cuerpo = request.read()
        ruta = request.url.path

        if ruta.endswith("/authn/status"):
            return httpx.Response(
                200,
                json={"okay": True, "authenticated": False},
                headers={"set-cookie": f"DSPACE-XSRF-COOKIE={XSRF_STUB}"},
            )

        if ruta.endswith("/authn/login"):
            if request.headers.get("X-XSRF-TOKEN") != XSRF_STUB:
                return httpx.Response(403, json={"message": "CSRF token missing"})
            form = urllib.parse.parse_qs(cuerpo.decode())
            if form.get("password", [""])[0] != self.password_valida:
                return httpx.Response(401, json={"message": "Login failed"})
            headers = {} if self.login_sin_authorization else {"Authorization": JWT_STUB}
            return httpx.Response(200, json={"okay": True}, headers=headers)

        if ruta.endswith("/submission/workspaceitems") and request.method == "POST":
            if request.headers.get("Authorization") != JWT_STUB:
                return httpx.Response(401, json={"message": "Authentication required"})
            if request.url.params.get("owningCollection") != "uuid-coleccion":
                return httpx.Response(422, json={"message": "owningCollection requerido"})
            if b"filename=" not in cuerpo:
                return httpx.Response(422, json={"message": "falta el archivo"})
            return httpx.Response(
                200,
                json={"id": ID_WORKSPACEITEM, "type": "workspaceitem", "sections": {}},
            )

        if ruta.endswith(f"/submission/workspaceitems/{ID_WORKSPACEITEM}/license"):
            if request.headers.get("Authorization") != JWT_STUB:
                return httpx.Response(401, json={"message": "Authentication required"})
            return httpx.Response(200, json={"granted": True})

        if ruta.endswith("/workflow/workflowitems"):
            if request.headers.get("Authorization") != JWT_STUB:
                return httpx.Response(401, json={"message": "Authentication required"})
            if json_mod.loads(cuerpo).get("workspaceItemId") != ID_WORKSPACEITEM:
                return httpx.Response(422, json={"message": "workspaceItemId inválido"})
            return httpx.Response(201, json={"id": 99, "type": "workflowitem", "workflowSteps": []})

        if (
            ruta.endswith(f"/submission/workspaceitems/{ID_WORKSPACEITEM}")
            and request.method == "PATCH"
        ):
            if request.headers.get("Authorization") != JWT_STUB:
                return httpx.Response(401, json={"message": "Authentication required"})
            operaciones = json_mod.loads(cuerpo)
            paths = [op.get("path", "") for op in operaciones]
            if self.exigir_titulo and not any(p.endswith("/dc.title") for p in paths):
                return httpx.Response(
                    422,
                    json={
                        "jsonSchemaErrors": [{"paths": ["/sections/traditionalpageone/dc.title"]}]
                    },
                )
            for op in operaciones:
                self.metadatos[op["path"]] = op["value"]
            return httpx.Response(200, json={"sections": {}})

        return httpx.Response(404, json={"message": f"ruta no implementada en el stub: {ruta}"})


def _config_con_stub(stub: StubDSpace, **overrides) -> ConfigDSpace:
    valores = dict(
        habilitado=True,
        base_url="https://stub.local/server/api",
        usuario="servicio",
        password="secreto",
        coleccion="uuid-coleccion",
        transport=httpx.MockTransport(stub.handler),
    )
    valores.update(overrides)
    return ConfigDSpace(**valores)


def _docx_prueba() -> str:
    """Ruta de un DOCX válido cualquiera: el stub no lee su contenido."""
    return compilar_docx(configuracion_base())


# ---------------------------------------------------------------------------
# ConfigDSpace
# ---------------------------------------------------------------------------


class TestConfigDSpace:
    def test_deshabilitado_por_defecto(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        config = ConfigDSpace.desde_entorno()
        assert config.enabled is False
        assert config.habilitado is False

    def test_habilitado_con_configuracion_completa(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        monkeypatch.setenv("VISTOBUENO_DSPACE", "1")
        monkeypatch.setenv("VISTOBUENO_DSPACE_URL", "https://repositorio.unitru.edu.pe/server/api")
        monkeypatch.setenv("VISTOBUENO_DSPACE_USER", "servicio")
        monkeypatch.setenv("VISTOBUENO_DSPACE_PASSWORD", "secreto")
        monkeypatch.setenv("VISTOBUENO_DSPACE_COLECCION", "uuid")
        config = ConfigDSpace.desde_entorno()
        assert config.enabled is True
        assert config.faltantes == []

    def test_flag_sin_configuracion_no_habilita(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        monkeypatch.setenv("VISTOBUENO_DSPACE", "1")
        config = ConfigDSpace.desde_entorno()
        assert config.enabled is False
        assert set(config.faltantes) == {
            "VISTOBUENO_DSPACE_URL",
            "VISTOBUENO_DSPACE_USER",
            "VISTOBUENO_DSPACE_PASSWORD",
            "VISTOBUENO_DSPACE_COLECCION",
        }

    def test_configuracion_sin_flag_no_habilita(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        monkeypatch.setenv("VISTOBUENO_DSPACE_URL", "https://x/server/api")
        config = ConfigDSpace.desde_entorno()
        assert config.enabled is False

    def test_flag_acepta_true_yes(self, monkeypatch):
        for valor in ("1", "true", "yes", "TRUE", "Yes"):
            monkeypatch.setenv("VISTOBUENO_DSPACE", valor)
            assert ConfigDSpace.desde_entorno().habilitado is True, valor
        for valor in ("", "0", "no", "false"):
            monkeypatch.setenv("VISTOBUENO_DSPACE", valor)
            assert ConfigDSpace.desde_entorno().habilitado is False, valor

    def test_timeout_no_numerico_cae_al_default(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        monkeypatch.setenv("VISTOBUENO_DSPACE_TIMEOUT", "veinte")
        assert ConfigDSpace.desde_entorno().timeout == 30


# ---------------------------------------------------------------------------
# Metadatos del formulario → JSON Patch
# ---------------------------------------------------------------------------


class TestMetadatos:
    def test_campos_vacios_no_producen_metadatos(self):
        assert metadatos_desde_formulario() == {}
        assert metadatos_desde_formulario(titulo="", autores="  ") == {}

    def test_titulo_y_resumen_como_valores_unicos(self):
        m = metadatos_desde_formulario(titulo="Taller de títeres", resumen="El resumen.")
        assert m["dc.title"] == ["Taller de títeres"]
        assert m["dc.description.abstract"] == ["El resumen."]

    def test_autores_se_separan_por_punto_y_coma_o_salto(self):
        m = metadatos_desde_formulario(autores="Linares A, Angie; Morales, Víctor\nBr. Otro")
        assert m["dc.contributor.author"] == ["Linares A, Angie", "Morales, Víctor", "Br. Otro"]

    def test_palabras_clave_se_separan_por_punto_y_coma_o_coma(self):
        m = metadatos_desde_formulario(palabras_clave="títeres; dramatización, preescolar")
        assert m["dc.subject"] == ["títeres", "dramatización", "preescolar"]

    def test_operaciones_son_add_sobre_la_seccion(self):
        ops = operaciones_metadatos({"dc.title": ["T"]}, "traditionalpageone")
        assert ops == [
            {
                "op": "add",
                "path": "/sections/traditionalpageone/dc.title",
                "value": [{"value": "T"}],
            }
        ]

    def test_operaciones_respetan_la_seccion_configurada(self):
        ops = operaciones_metadatos({"dc.subject": ["a", "b"]}, "seccion-instancia")
        assert ops[0]["path"] == "/sections/seccion-instancia/dc.subject"
        assert ops[0]["value"] == [{"value": "a"}, {"value": "b"}]


# ---------------------------------------------------------------------------
# depositar_documento contra el stub del contrato HAL
# ---------------------------------------------------------------------------


class TestDepositarDocumento:
    def test_flujo_completo_con_metadatos(self, monkeypatch):
        stub = StubDSpace()
        resultado = depositar_documento(
            _docx_prueba(),
            {"dc.title": ["Tesis de prueba"]},
            config=_config_con_stub(stub),
        )
        assert resultado.enviado is True
        assert "cola de aprobación" in (resultado.detalle or "")
        # Orden del flujo: CSRF, login, workspaceitem, PATCH, licencia, workflow
        assert [p for _, p in stub.llamadas] == [
            "/server/api/authn/status",
            "/server/api/authn/login",
            "/server/api/submission/workspaceitems",
            f"/server/api/submission/workspaceitems/{ID_WORKSPACEITEM}",
            f"/server/api/submission/workspaceitems/{ID_WORKSPACEITEM}/license",
            "/server/api/workflow/workflowitems",
        ]
        assert stub.metadatos == {
            "/sections/traditionalpageone/dc.title": [{"value": "Tesis de prueba"}]
        }

    def test_flujo_sin_metadatos_salta_el_patch(self, monkeypatch):
        stub = StubDSpace()
        resultado = depositar_documento(_docx_prueba(), config=_config_con_stub(stub))
        assert resultado.enviado is True
        paths = [p for _, p in stub.llamadas]
        assert f"/server/api/submission/workspaceitems/{ID_WORKSPACEITEM}" not in paths

    def test_login_rechazado_es_fallo_best_effort(self, monkeypatch):
        stub = StubDSpace(password_valida="otra-clave")
        resultado = depositar_documento(_docx_prueba(), config=_config_con_stub(stub))
        assert resultado.enviado is False
        assert "401" in (resultado.detalle or "")
        # El flujo murió en el login: no se creó ningún workspaceitem
        paths = [p for _, p in stub.llamadas]
        assert "/server/api/submission/workspaceitems" not in paths

    def test_formulario_rechaza_metadatos_incompletos(self, monkeypatch):
        stub = StubDSpace(exigir_titulo=True)
        resultado = depositar_documento(
            _docx_prueba(),
            {"dc.subject": ["sin título"]},
            config=_config_con_stub(stub),
        )
        assert resultado.enviado is False
        assert "422" in (resultado.detalle or "")
        assert "dc.title" in (resultado.detalle or "")

    def test_login_sin_authorization_es_fallo(self, monkeypatch):
        stub = StubDSpace(login_sin_authorization=True)
        resultado = depositar_documento(_docx_prueba(), config=_config_con_stub(stub))
        assert resultado.enviado is False
        assert "Authorization" in (resultado.detalle or "")

    def test_error_de_conexion_es_best_effort(self, monkeypatch):
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("sin conexión al repositorio")

        config = ConfigDSpace(
            habilitado=True,
            base_url="https://caido.local/server/api",
            usuario="s",
            password="s",
            coleccion="uuid",
            transport=httpx.MockTransport(handler),
        )
        resultado = depositar_documento(_docx_prueba(), config=config)
        assert resultado.enviado is False
        assert "ConnectError" in (resultado.detalle or "")

    def test_deshabilitado_no_toca_la_red(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        stub = StubDSpace()
        config = _config_con_stub(stub, habilitado=False)
        resultado = depositar_documento(_docx_prueba(), config=config)
        assert resultado.enviado is False
        assert "deshabilitado" in (resultado.detalle or "")
        assert stub.llamadas == []

    def test_deshabilitado_por_entorno_reporta_faltantes(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        resultado = depositar_documento(_docx_prueba())
        assert resultado.enviado is False
        detalle = resultado.detalle or ""
        assert "VISTOBUENO_DSPACE_URL" in detalle
        assert "VISTOBUENO_DSPACE_PASSWORD" in detalle


# ---------------------------------------------------------------------------
# Guardia de contrato: POST /validar expone `deposito`
# ---------------------------------------------------------------------------


def _docx_verde() -> bytes:
    """Bytes del documento bueno del factory (semáforo verde)."""
    with open(compilar_docx(configuracion_base()), "rb") as f:
        return f.read()


def _docx_rojo() -> bytes:
    """Bytes de un documento con semáforo rojo (margen superior incumplido)."""
    with open(compilar_docx(aplicar_mutacion("margen_superior", configuracion_base())), "rb") as f:
        return f.read()


def _post_validar(docx: bytes, data: dict | None = None):
    return CLIENTE.post(
        "/validar",
        files={"archivo": ("tesis.docx", docx, MIME_DOCX)},
        data=data or {},
    )


class TestGuardiaContratoDeposito:
    def test_deposito_sin_solicitud_por_defecto(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        respuesta = _post_validar(_docx_verde())
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert set(cuerpo.keys()) == {
            "semaforo",
            "notificacion",
            "deposito",
            "ficha_deposito",
            "resumen",
            "resultados",
            "como_preguntar_a_una_ia",
            "metadatos",
        }
        assert cuerpo["deposito"] == {"estado": "sin_solicitud", "detalle": None}
        # v1.7.0: con semáforo verde la ficha siempre materializa.
        assert cuerpo["ficha_deposito"] is not None

    def test_rojo_con_depositar_es_no_apto_y_no_toca_el_modulo(self, monkeypatch):
        _limpiar_entorno(monkeypatch)

        def _bomba(*_args, **_kwargs):
            raise AssertionError("el depósito no debe intentarse con semáforo rojo")

        monkeypatch.setattr("validator.api.depositar_documento", _bomba)
        respuesta = _post_validar(_docx_rojo(), data={"depositar": "true"})
        assert respuesta.status_code == 200
        deposito = respuesta.json()["deposito"]
        assert deposito["estado"] == "no_apto"
        assert "verde" in (deposito["detalle"] or "")

    def test_verde_sin_configuracion_es_deshabilitado_con_nota(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        respuesta = _post_validar(_docx_verde(), data={"depositar": "true"})
        assert respuesta.status_code == 200
        deposito = respuesta.json()["deposito"]
        assert deposito["estado"] == "deshabilitado"
        detalle = deposito["detalle"] or ""
        assert "VISTOBUENO_DSPACE" in detalle
        assert "VISTOBUENO_DSPACE_URL" in detalle

    def test_verde_habilitado_deposita_y_expone_enviado(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        _configurar_entorno_stub(monkeypatch)
        recibido: dict = {}

        def _fake(ruta, metadatos, config=None):
            recibido["ruta"] = ruta
            recibido["metadatos"] = metadatos
            return ResultadoDeposito(True, "el ítem quedó en la cola de aprobación de la sede")

        monkeypatch.setattr("validator.api.depositar_documento", _fake)
        respuesta = _post_validar(
            _docx_verde(),
            data={
                "depositar": "true",
                "titulo": "Taller de títeres",
                "autores": "Autor A; Autor B",
                "asesor": "Asesora C",
                "resumen": "El resumen.",
                "palabras_clave": "títeres, preescolar",
            },
        )
        assert respuesta.status_code == 200
        deposito = respuesta.json()["deposito"]
        assert deposito["estado"] == "enviado"
        assert "cola de aprobación" in (deposito["detalle"] or "")
        # El módulo recibió la ruta del temporal y los metadatos del form
        assert str(recibido["ruta"]).endswith(".docx")
        assert recibido["metadatos"]["dc.title"] == ["Taller de títeres"]
        assert recibido["metadatos"]["dc.contributor.author"] == ["Autor A", "Autor B"]
        assert recibido["metadatos"]["dc.contributor.advisor"] == ["Asesora C"]
        assert recibido["metadatos"]["dc.subject"] == ["títeres", "preescolar"]

    def test_fallo_del_modulo_propaga_el_detalle(self, monkeypatch):
        _limpiar_entorno(monkeypatch)
        _configurar_entorno_stub(monkeypatch)

        def _fake(_ruta, _metadatos, config=None):
            return ResultadoDeposito(False, "ErrorDeposito: login: HTTP 401 — rechazado")

        monkeypatch.setattr("validator.api.depositar_documento", _fake)
        respuesta = _post_validar(_docx_verde(), data={"depositar": "true"})
        assert respuesta.status_code == 200
        deposito = respuesta.json()["deposito"]
        assert deposito["estado"] == "fallo"
        assert "HTTP 401" in (deposito["detalle"] or "")
