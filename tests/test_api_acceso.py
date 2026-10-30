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

import pytest
from conftest import CLIENTE, MIME_DOCX, ruta_docx_prueba
from fastapi.testclient import TestClient

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

    def test_hosts_ampliados_por_entorno(self, monkeypatch):
        """VISTOBUENO_HOSTS suma un dominio propio (reverse proxy local)."""
        monkeypatch.setenv("VISTOBUENO_HOSTS", "api.midominio.local")
        cliente = TestClient(
            app, client=("127.0.0.1", 50000), base_url="http://api.midominio.local"
        )
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
