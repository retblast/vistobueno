"""Tests del buzón de una ranura (comunicación app ↔ userscript, v1.13.0).

Cubre dos niveles:

- Unitario: la clase Buzon (TTL, última-gana, trámite, ranuras
  independientes, copia defensiva, invalidación del depósito anterior).
- Contrato: los endpoints HTTP del buzón sobre la app real (POST → GET,
  201 con `tramite_id`, envelopes, 404/409, 422 con payload inválido) y
  la invariante de seguridad: el buzón NUNCA emite cabeceras CORS.

Uso:
    pytest tests/test_api_buzon.py -v
"""

import time

import pytest
from conftest import CLIENTE
from fastapi.testclient import TestClient

import validator.api
from validator.api import app
from validator.buzon import Buzon, SinFichaVigente, TramiteNoCoincide

# Cliente con un peer que NO es loopback: simula una petición que llega
# desde otro equipo de la red (auditoría 2026-10-26, AUD-09). El Host es
# el loopback para aislar el control del peer (AUD-28).
CLIENTE_FUERA = TestClient(app, client=("10.0.0.5", 40000), base_url="http://127.0.0.1")

FICHA = {
    "extraidos": [
        {"campo": "dc.title", "valor": "Tesis de prueba", "pagina": 1, "detectado": True},
        {"campo": "escuela", "valor": None, "pagina": None, "detectado": False},
    ],
    "manuales": [
        {"campo": "matricula", "valor": "10584011-18"},
        {"campo": "renati.author.dni", "valor": None},
    ],
}

FICHA_REEMPLAZO = {
    "extraidos": [
        {"campo": "dc.title", "valor": "Otra tesis", "pagina": 1, "detectado": True},
    ],
    "manuales": [],
}

HANDLE = "https://hdl.handle.net/20.500.14414/99999"
TIMESTAMP = "2026-10-19T18:10:00"
TITULO_OBSERVADO = "Tesis de prueba"


def _cuerpo_deposito(tramite_id: str) -> dict:
    return {
        "tramite_id": tramite_id,
        "handle": HANDLE,
        "titulo_observado": TITULO_OBSERVADO,
        "timestamp": TIMESTAMP,
    }


def _publicar_ficha(cliente: TestClient = CLIENTE, ficha: dict = FICHA):
    return cliente.post("/ficha-pendiente", json=ficha)


def _publicar_deposito(tramite_id: str, cliente: TestClient = CLIENTE):
    return cliente.post("/deposito", json=_cuerpo_deposito(tramite_id))


@pytest.fixture(autouse=True)
def _buzon_limpio():
    """Aísla los tests: el buzón es un singleton del proceso."""
    validator.api._BUZON.limpiar()
    yield
    validator.api._BUZON.limpiar()


# ---------------------------------------------------------------------------
# Unitario: la clase Buzon
# ---------------------------------------------------------------------------


class TestBuzonUnitario:
    """La ranura única con TTL, trámite y depósito atado a la ficha."""

    def test_ranura_vacia_devuelve_none(self):
        """Sin publicar nada, la lectura devuelve None."""
        buzon = Buzon()
        assert buzon.leer_ficha() is None
        assert buzon.leer_deposito() is None

    def test_publicar_y_leer_ficha(self):
        """Lo publicado se lee intacto, junto con su trámite."""
        buzon = Buzon()
        tramite_id, vence_en = buzon.publicar_ficha({"extraidos": [1], "manuales": []})
        leida = buzon.leer_ficha()
        assert leida is not None
        ficha, tramite_leido, vence_leido = leida
        assert ficha == {"extraidos": [1], "manuales": []}
        assert tramite_leido == tramite_id
        assert vence_leido == vence_en

    def test_ultima_gana_con_tramite_nuevo(self):
        """Publicar de nuevo reemplaza ficha y trámite."""
        buzon = Buzon()
        primero, _ = buzon.publicar_ficha({"a": 1})
        segundo, _ = buzon.publicar_ficha({"b": 2})
        assert primero != segundo
        leida = buzon.leer_ficha()
        assert leida is not None
        assert leida[0] == {"b": 2}
        assert leida[1] == segundo

    def test_ttl_expira_ficha_y_deposito(self):
        """Con el TTL vencido, ambas ranuras se limpian."""
        buzon = Buzon(ttl_segundos=0.01)
        tramite_id, _ = buzon.publicar_ficha({"a": 1})
        buzon.reportar_deposito(_cuerpo_deposito(tramite_id))
        time.sleep(0.05)
        assert buzon.leer_ficha() is None
        assert buzon.leer_deposito() is None

    def test_ttl_vigente_devuelve_contenido(self):
        """Dentro del TTL, la ficha sigue disponible."""
        buzon = Buzon(ttl_segundos=60)
        buzon.publicar_ficha({"a": 1})
        assert buzon.leer_ficha() is not None
        assert buzon.leer_ficha() is not None

    def test_ranuras_independientes(self):
        """La ficha y su depósito conviven sin pisarse."""
        buzon = Buzon()
        tramite_id, _ = buzon.publicar_ficha({"ficha": True})
        buzon.reportar_deposito(_cuerpo_deposito(tramite_id))
        leida = buzon.leer_ficha()
        assert leida is not None
        assert leida[0] == {"ficha": True}
        assert buzon.leer_deposito() is not None

    def test_lectura_devuelve_copia(self):
        """Mutar lo leído no corrompe el contenido almacenado."""
        buzon = Buzon()
        buzon.publicar_ficha({"a": 1})
        leido = buzon.leer_ficha()
        assert leido is not None
        leido[0]["a"] = 999
        otra = buzon.leer_ficha()
        assert otra is not None
        assert otra[0] == {"a": 1}

    def test_limpiar_vacia_todo(self):
        """limpiar() vacía ficha, trámite y depósito."""
        buzon = Buzon()
        tramite_id, _ = buzon.publicar_ficha({"a": 1})
        buzon.reportar_deposito(_cuerpo_deposito(tramite_id))
        buzon.limpiar()
        assert buzon.leer_ficha() is None
        assert buzon.leer_deposito() is None

    def test_nueva_ficha_borra_deposito_anterior(self):
        """El depósito viejo no sobrevive a una ficha nueva."""
        buzon = Buzon()
        primero, _ = buzon.publicar_ficha({"titulo": "Tesis de prueba"})
        buzon.reportar_deposito(_cuerpo_deposito(primero))
        assert buzon.leer_deposito() is not None
        segundo, _ = buzon.publicar_ficha({"titulo": "Tesis de prueba"})
        assert primero != segundo
        assert buzon.leer_deposito() is None

    def test_reporte_sin_ficha_falla(self):
        """No se acepta un depósito si no hay ficha vigente."""
        buzon = Buzon()
        with pytest.raises(SinFichaVigente):
            buzon.reportar_deposito(_cuerpo_deposito("cualquiera"))

    def test_reporte_con_tramite_ajeno_falla(self):
        """El depósito debe traer el trámite de la ficha vigente."""
        buzon = Buzon()
        buzon.publicar_ficha({"a": 1})
        with pytest.raises(TramiteNoCoincide):
            buzon.reportar_deposito(_cuerpo_deposito("tramite-anterior"))


# ---------------------------------------------------------------------------
# Contrato: endpoints HTTP del buzón
# ---------------------------------------------------------------------------


class TestBuzonEndpoints:
    """Flujo POST → GET sobre la app FastAPI real."""

    def test_publicar_y_leer_ficha(self):
        """POST /ficha-pendiente → 201 con trámite; GET devuelve el sobre."""
        respuesta = _publicar_ficha()
        assert respuesta.status_code == 201
        publicada = respuesta.json()
        assert publicada["tramite_id"]
        assert publicada["vence_en"]

        leida = CLIENTE.get("/ficha-pendiente")
        assert leida.status_code == 200
        sobre = leida.json()
        assert sobre["ficha"] == FICHA
        assert sobre["tramite_id"] == publicada["tramite_id"]
        assert sobre["vence_en"] == publicada["vence_en"]

    def test_ficha_vacia_da_404(self):
        """GET sin publicar antes → 404 con detalle en español."""
        respuesta = CLIENTE.get("/ficha-pendiente")
        assert respuesta.status_code == 404
        assert "ficha" in respuesta.json()["detail"]

    def test_ficha_ultima_gana_por_http(self):
        """Publicar dos veces: GET devuelve la segunda y un trámite nuevo."""
        primera = _publicar_ficha().json()
        segunda = _publicar_ficha(ficha=FICHA_REEMPLAZO).json()
        assert primera["tramite_id"] != segunda["tramite_id"]
        leida = CLIENTE.get("/ficha-pendiente")
        assert leida.status_code == 200
        assert leida.json()["ficha"] == FICHA_REEMPLAZO
        assert leida.json()["tramite_id"] == segunda["tramite_id"]

    def test_ficha_payload_invalido_da_422(self):
        """POST sin extraidos/manuales → 422 de validación."""
        respuesta = CLIENTE.post("/ficha-pendiente", json={"cualquier": "cosa"})
        assert respuesta.status_code == 422

    def test_publicar_y_leer_deposito(self):
        """POST /deposito → 204; GET devuelve el reporte y el alias."""
        tramite_id = _publicar_ficha().json()["tramite_id"]
        respuesta = _publicar_deposito(tramite_id)
        assert respuesta.status_code == 204

        leido = CLIENTE.get("/deposito")
        assert leido.status_code == 200
        deposito = leido.json()
        assert deposito["tramite_id"] == tramite_id
        assert deposito["handle"] == HANDLE
        assert deposito["titulo_observado"] == TITULO_OBSERVADO
        assert deposito["titulo"] == TITULO_OBSERVADO
        assert deposito["timestamp"] == TIMESTAMP

    def test_deposito_vacio_da_404(self):
        """GET /deposito sin reporte previo → 404."""
        respuesta = CLIENTE.get("/deposito")
        assert respuesta.status_code == 404

    def test_deposito_sin_ficha_da_404(self):
        """POST /deposito sin ficha vigente → 404."""
        respuesta = _publicar_deposito("tramite-sin-ficha")
        assert respuesta.status_code == 404
        assert "ficha" in respuesta.json()["detail"]

    def test_deposito_con_tramite_ajeno_da_409(self):
        """Un trámite que no es el vigente → 409."""
        _publicar_ficha()
        respuesta = _publicar_deposito("tramite-anterior")
        assert respuesta.status_code == 409
        assert "trámite" in respuesta.json()["detail"]

    def test_deposito_payload_invalido_da_422(self):
        """POST /deposito sin handle/título/timestamp → 422."""
        respuesta = CLIENTE.post("/deposito", json={"handle": ""})
        assert respuesta.status_code == 422

    def test_payload_viejo_con_titulo_da_422(self):
        """El payload v1.12.0 no entra: falta `tramite_id` y sobra `titulo`."""
        tramite_id = _publicar_ficha().json()["tramite_id"]
        respuesta = CLIENTE.post(
            "/deposito",
            json={
                "tramite_id": tramite_id,
                "handle": HANDLE,
                "titulo": TITULO_OBSERVADO,
                "timestamp": TIMESTAMP,
            },
        )
        assert respuesta.status_code == 422

    def test_nueva_ficha_invalida_deposito_y_reporte_viejo(self):
        """Una ficha nueva descarta el depósito y rechaza el trámite viejo."""
        primero = _publicar_ficha().json()["tramite_id"]
        assert _publicar_deposito(primero).status_code == 204

        segundo = _publicar_ficha().json()["tramite_id"]
        assert primero != segundo
        assert CLIENTE.get("/deposito").status_code == 404
        assert _publicar_deposito(primero).status_code == 409

    def test_reintento_del_mismo_tramite_se_acepta(self):
        """El userscript puede reintentar el mismo trámite tras un fallo."""
        tramite_id = _publicar_ficha().json()["tramite_id"]
        assert _publicar_deposito(tramite_id).status_code == 204

        segundo = CLIENTE.post(
            "/deposito",
            json={
                **_cuerpo_deposito(tramite_id),
                "handle": "https://hdl.handle.net/20.500.14414/88888",
                "timestamp": "2026-10-19T18:11:00",
            },
        )
        assert segundo.status_code == 204
        leido = CLIENTE.get("/deposito").json()
        assert leido["tramite_id"] == tramite_id
        assert leido["handle"] == "https://hdl.handle.net/20.500.14414/88888"
        assert leido["timestamp"] == "2026-10-19T18:11:00"


class TestAccesoBuzon:
    """El buzón solo se sirve desde la máquina donde corre la app (AUD-09).

    La ficha viaja con datos personales del estudiante (DNI, ORCID,
    resumen) y su ranura es de "última gana": sin este control, cualquiera
    de la red podría leerlos o pisar la ficha en vuelo.
    """

    def test_peticion_desde_otro_equipo_da_403(self):
        """Un peer que no es loopback no puede leer la ficha."""
        _publicar_ficha()
        respuesta = CLIENTE_FUERA.get("/ficha-pendiente")
        assert respuesta.status_code == 403
        assert "loopback" in respuesta.json()["detail"]

    def test_peticion_desde_otro_equipo_no_pisa_la_ficha(self):
        """Un tercero tampoco puede sobrescribir la ficha en vuelo."""
        _publicar_ficha()
        respuesta = _publicar_ficha(cliente=CLIENTE_FUERA, ficha=FICHA_REEMPLAZO)
        assert respuesta.status_code == 403
        # La ficha original sigue intacta.
        assert CLIENTE.get("/ficha-pendiente").json()["ficha"] == FICHA

    def test_peticion_desde_otro_equipo_no_reporta_depositos(self):
        """Tampoco puede inyectar un handle en la ranura de depósito."""
        respuesta = _publicar_deposito("cualquier-tramite", cliente=CLIENTE_FUERA)
        assert respuesta.status_code == 403
        assert CLIENTE.get("/deposito").status_code == 404

    def test_loopback_sigue_funcionando(self):
        """El caso normal (SPA y userscript en la misma máquina) no cambia."""
        assert _publicar_ficha().status_code == 201
        assert CLIENTE.get("/ficha-pendiente").status_code == 200

    def test_loopback_no_necesita_token(self, monkeypatch):
        """Con token configurado, el loopback sigue sin necesitarlo.

        La SPA y el userscript hablan con `127.0.0.1` y no envían el
        header: si el loopback exigiera el token, el flujo local se
        rompería en cuanto alguien defina `VISTOBUENO_API_TOKEN`.
        """
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", "secreto-de-prueba")
        assert _publicar_ficha().status_code == 201
        assert CLIENTE.get("/ficha-pendiente").status_code == 200

    def test_token_ausente_da_403(self, monkeypatch):
        """Con token configurado, la petición remota sin header va a 403."""
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", "secreto-de-prueba")
        respuesta = CLIENTE_FUERA.get("/ficha-pendiente")
        assert respuesta.status_code == 403
        assert "token" in respuesta.json()["detail"].lower()

    def test_token_incorrecto_da_403(self, monkeypatch):
        """Con token configurado, un token equivocado va a 403."""
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", "secreto-de-prueba")
        respuesta = CLIENTE_FUERA.get(
            "/ficha-pendiente",
            headers={"X-VistoBueno-Token": "otro-token"},
        )
        assert respuesta.status_code == 403

    def test_token_correcto_permite_el_buzon(self, monkeypatch):
        """Con token configurado y correcto, el flujo normal sigue igual."""
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", "secreto-de-prueba")
        cabeceras = {"X-VistoBueno-Token": "secreto-de-prueba"}
        respuesta = CLIENTE.post("/ficha-pendiente", json=FICHA, headers=cabeceras)
        assert respuesta.status_code == 201
        leida = CLIENTE.get("/ficha-pendiente", headers=cabeceras)
        assert leida.status_code == 200
        assert leida.json()["ficha"] == FICHA

    def test_token_correcto_habilita_a_otro_equipo(self, monkeypatch):
        """El caso documentado: API expuesta + token → el remoto entra.

        Este es el motivo del token compartido. Con el orden anterior
        (loopback primero) ningún peer remoto podía pasar nunca, y la
        variable `VISTOBUENO_API_TOKEN` no habilitaba nada.
        """
        monkeypatch.setenv("VISTOBUENO_API_TOKEN", "secreto-de-prueba")
        cabeceras = {"X-VistoBueno-Token": "secreto-de-prueba"}
        respuesta = CLIENTE_FUERA.post("/ficha-pendiente", json=FICHA, headers=cabeceras)
        assert respuesta.status_code == 201
        leida = CLIENTE_FUERA.get("/ficha-pendiente", headers=cabeceras)
        assert leida.status_code == 200
        assert leida.json()["ficha"] == FICHA

    def test_sin_token_configurado_el_remoto_sigue_cerrado(self):
        """Sin token configurado, el loopback es la única puerta."""
        respuesta = CLIENTE_FUERA.get("/ficha-pendiente")
        assert respuesta.status_code == 403
        assert "loopback" in respuesta.json()["detail"]


class TestBuzonInvarianteSinCors:
    """El buzón jamás emite cabeceras CORS.

    Invariante de seguridad del plan (PLAN_FICHA §6): la ficha contiene
    datos personales del estudiante; sin CORS, una página web maliciosa
    en el navegador del operador no puede leer las respuestas (el
    navegador bloquea la lectura cruzada). El userscript no se ve
    afectado: GM_xmlhttpRequest corre en el contexto de la extensión.
    Si alguien agrega CORSMiddleware sin querer, este test lo detecta.
    """

    def test_get_ficha_sin_cors(self):
        respuesta = CLIENTE.get("/ficha-pendiente")
        assert "access-control-allow-origin" not in respuesta.headers
        assert "access-control-allow-methods" not in respuesta.headers

    def test_post_ficha_sin_cors(self):
        respuesta = _publicar_ficha()
        assert "access-control-allow-origin" not in respuesta.headers

    def test_endpoints_deposito_sin_cors(self):
        respuesta = CLIENTE.get("/deposito")
        assert "access-control-allow-origin" not in respuesta.headers
        respuesta = CLIENTE.post("/deposito", json=_cuerpo_deposito("cualquiera"))
        assert "access-control-allow-origin" not in respuesta.headers
