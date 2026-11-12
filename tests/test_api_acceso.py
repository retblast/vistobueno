"""Tests del control de acceso y del chequeo de Host (auditoría B0).

Cubre dos controles independientes:

- **Header Host** (AUD-28): rechaza el DNS rebinding con 400 antes de
  llegar a cualquier endpoint. El atacante conserva su dominio en el
  Host aunque su DNS resuelva a 127.0.0.1.
- **Peer loopback o token** (AUD-09, ampliado a toda la API): un equipo
  remoto no puede validar, leer la ficha ni generar papeleo. La app se
  despliega en la PC del operador; el loopback es la frontera.

Uso:
    pytest tests/test_api_acceso.py -v
"""

import asyncio

import pytest
from conftest import CLIENTE, MIME_DOCX, ruta_docx_prueba
from fastapi.testclient import TestClient

import validator.api
from validator.api import CABECERA_TOKEN_BUZON, _host_sin_puerto, app

# Peer remoto con Host de loopback: aísla el control del peer (el Host
# lo cubre TestHostConfiable).
CLIENTE_FUERA = TestClient(app, client=("10.0.0.5", 40000), base_url="http://127.0.0.1")

TOKEN = "token-de-prueba"

SOLICITUD_PAPEL = {
    "ficha": {
        "extraidos": [
            {"campo": "dc.title", "valor": "Tesis de prueba", "pagina": 1, "detectado": True},
        ],
        "manuales": [],
    },
    "tramite_id": "tramite-de-prueba",
    "handle": "https://hdl.handle.net/20.500.14414/1",
    "timestamp": "2026-10-19T18:10:00",
}


def _subir(cliente: TestClient, *, token: str | None = None):
    """Envía el DOCX de prueba con el peer/Host del cliente dado."""
    headers = {CABECERA_TOKEN_BUZON: token} if token is not None else None
    with open(ruta_docx_prueba(), "rb") as f:
        return cliente.post(
            "/validar",
            files={"archivo": ("tesis.docx", f.read(), MIME_DOCX)},
            headers=headers,
        )


# ---------------------------------------------------------------------------
# Header Host: DNS rebinding
# ---------------------------------------------------------------------------


class TestHostConfiable:
    """El Host debe ser de la máquina local (o de VISTOBUENO_HOSTS)."""

    def test_host_ajeno_devuelve_400(self):
        """Un dominio de atacante no llega a ningún endpoint (DNS rebinding)."""
        atacante = TestClient(app, client=("127.0.0.1", 50000), base_url="http://atacante.example")
        respuesta = atacante.get("/docs")
        assert respuesta.status_code == 400
        assert "Host" in respuesta.text

    def test_loopback_con_puerto_pasa(self):
        """El puerto del Host se ignora: 127.0.0.1:8000 es loopback."""
        cliente = TestClient(app, client=("127.0.0.1", 50000), base_url="http://127.0.0.1:8000")
        assert cliente.get("/docs").status_code == 200

    def test_ipv6_literal_pasa(self):
        """El literal IPv6 entre corchetes se reconoce (con y sin puerto).

        Se prueba el parser directo: el `TestClient` de Starlette no
        sabe armar un `base_url` IPv6 (parte el netloc por el primer
        `:`), así que el caso no se puede montar por HTTP en tests.
        """
        assert _host_sin_puerto("[::1]:8000") == "::1"
        assert _host_sin_puerto("[::1]") == "::1"
        assert _host_sin_puerto("127.0.0.1:8000") == "127.0.0.1"

    def test_el_ipv6_literal_sin_corchetes_no_se_vacia(self):
        """`::1` es un host, no un host con puerto.

        Al partirlo por el primer `:` quedaba la cadena vacía, y esa
        cadena vacía entraba en la lista de admitidos: una petición sin
        header `Host` pasaba el control (revisión PR #71, N1).
        """
        assert _host_sin_puerto("::1") == "::1"
        assert _host_sin_puerto("fe80::1") == "fe80::1"
        assert "" not in validator.api._hosts_confiables()

    def test_una_peticion_sin_host_devuelve_400(self):
        """HTTP/1.0 permite omitir el header `Host`: debe recibir 400.

        El control del `Host` es la frontera contra el DNS rebinding: si
        la petición no dice de dónde viene, no se sirve.
        """
        alcance = {
            "type": "http",
            "method": "GET",
            "path": "/docs",
            "headers": [],
            "client": ("127.0.0.1", 50000),
        }
        mensajes: list[dict] = []

        async def _app(scope, receive, send):  # pragma: no cover - no debe llegar
            raise AssertionError("la petición sin Host llegó al endpoint")

        async def _send(mensaje):
            mensajes.append(mensaje)

        async def _receive():
            return {"type": "http.request"}

        asyncio.run(validator.api.MiddlewareHostConfiable(_app)(alcance, _receive, _send))
        inicio = next(m for m in mensajes if m["type"] == "http.response.start")
        assert inicio["status"] == 400

    def test_hosts_ampliados_por_entorno(self, monkeypatch):
        """VISTOBUENO_HOSTS suma un dominio propio (reverse proxy local)."""
        monkeypatch.setenv("VISTOBUENO_HOSTS", "api.midominio.local")
        cliente = TestClient(
            app, client=("127.0.0.1", 50000), base_url="http://api.midominio.local"
        )
        assert cliente.get("/docs").status_code == 200

    def test_el_host_del_entorno_ignora_el_puerto(self, monkeypatch):
        """`VISTOBUENO_HOSTS=10.0.0.5:8000` sirve para el Host `10.0.0.5:8000`.

        Sin normalizar, el puerto de la lista no coincidía con el Host
        real de la petición y el peer remoto recibía 400 (revisión PR #71, B3).
        """
        monkeypatch.setenv("VISTOBUENO_HOSTS", "10.0.0.5:8000")
        assert "10.0.0.5" in validator.api._hosts_confiables()
        assert "10.0.0.5:8000" not in validator.api._hosts_confiables()
        cliente = TestClient(app, client=("10.0.0.5", 40000), base_url="http://10.0.0.5:8000")
        assert cliente.get("/docs").status_code == 200

    def test_wildcard_desactiva_el_chequeo(self, monkeypatch):
        """`*` es la salida de emergencia documentada (no recomendada)."""
        monkeypatch.setenv("VISTOBUENO_HOSTS", "*")
        cliente = TestClient(app, client=("127.0.0.1", 50000), base_url="http://atacante.example")
        assert cliente.get("/docs").status_code == 200


# ---------------------------------------------------------------------------
# Peer loopback o token: toda la API
# ---------------------------------------------------------------------------


class TestAccesoRemoto:
    """Sin token, un peer remoto recibe 403 en todos los endpoints."""

    def test_remoto_sin_token_no_valida(self):
        assert _subir(CLIENTE_FUERA).status_code == 403

    def test_remoto_con_token_valida(self, monkeypatch):
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", TOKEN)
        assert _subir(CLIENTE_FUERA, token=TOKEN).status_code == 200

    def test_token_incorrecto_da_403(self, monkeypatch):
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", TOKEN)
        assert _subir(CLIENTE_FUERA, token="otro-token").status_code == 403

    def test_loopback_no_necesita_token(self, monkeypatch):
        """El flujo local (SPA + userscript) nunca envía el header."""
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", TOKEN)
        assert _subir(CLIENTE).status_code == 200

    def test_x_forwarded_for_no_falsifica_el_peer(self):
        """La app no lee X-Forwarded-For: el control usa el peer real.

        La cabecera solo puede reescribir el peer si uvicorn arranca con
        proxy headers habilitados; el arranque documentado los desactiva
        (`--no-proxy-headers`).
        """
        respuesta = CLIENTE_FUERA.get("/ficha-pendiente", headers={"X-Forwarded-For": "127.0.0.1"})
        assert respuesta.status_code == 403

    @pytest.mark.parametrize("metodo", ["GET", "POST"])
    def test_remoto_no_toca_el_buzon(self, metodo):
        if metodo == "GET":
            respuesta = CLIENTE_FUERA.get("/ficha-pendiente")
        else:
            respuesta = CLIENTE_FUERA.post(
                "/ficha-pendiente", json={"extraidos": [], "manuales": []}
            )
        assert respuesta.status_code == 403

    @pytest.mark.parametrize("ruta", ["/constancia", "/fila-registro"])
    def test_remoto_no_genera_papeleo(self, ruta):
        respuesta = CLIENTE_FUERA.post(ruta, json=SOLICITUD_PAPEL)
        assert respuesta.status_code == 403


# ---------------------------------------------------------------------------
# Peer remoto: Host permitido + token compartido (revisión PR #71, B2)
# ---------------------------------------------------------------------------


class TestPeerRemotoConHostYToken:
    """El peer remoto necesita las DOS cosas: Host permitido y token.

    El chequeo del `Host` corre antes que el del token. Con un token
    válido pero un Host no listado, la respuesta es 400 (no 200): los dos
    controles son independientes y el primero que falla corta la
    petición.
    """

    @staticmethod
    def _cliente() -> TestClient:
        return TestClient(app, client=("10.0.0.5", 40000), base_url="http://10.0.0.5:8000")

    def test_sin_host_listado_el_token_no_alcanza(self, monkeypatch):
        """Host ajeno + token válido → 400 (el Host se comprueba primero)."""
        monkeypatch.delenv("VISTOBUENO_HOSTS", raising=False)
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", TOKEN)
        assert self._cliente().get("/docs").status_code == 400

    def test_host_listado_sin_token_da_403(self, monkeypatch):
        """Host permitido pero sin token → 403 (el peer sigue siendo remoto)."""
        monkeypatch.setenv("VISTOBUENO_HOSTS", "10.0.0.5")
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", TOKEN)
        respuesta = self._cliente().get("/ficha-pendiente")
        assert respuesta.status_code == 403

    def test_host_listado_con_token_pasa(self, monkeypatch):
        """Host permitido + token válido → la API responde."""
        monkeypatch.setenv("VISTOBUENO_HOSTS", "10.0.0.5")
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", TOKEN)
        cliente = self._cliente()
        assert cliente.get("/docs").status_code == 200
        assert _subir(cliente, token=TOKEN).status_code == 200
