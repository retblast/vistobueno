"""Tests del buzón de una ranura (comunicación app ↔ userscript, v1.7.0).

Cubre dos niveles:

- Unitario: la clase Buzon (TTL, última-gana, ranuras independientes,
  copia defensiva).
- Contrato: los endpoints HTTP del buzón sobre la app real (flujo POST →
  GET, 404 en vacío/expirado, 422 con payload inválido) y la invariante
  de seguridad: el buzón NUNCA emite cabeceras CORS (una página web
  cualquiera del navegador del operador no puede leer la ficha, que
  contiene datos personales del estudiante).

Uso:
    pytest tests/test_api_buzon.py -v
"""

import time

import pytest
from conftest import CLIENTE

import validator.api
from validator.buzon import Buzon

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

DEPOSITO = {
    "handle": "https://hdl.handle.net/20.500.14414/99999",
    "titulo": "Tesis de prueba",
    "timestamp": "2026-10-19T18:10:00",
}


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
    """La ranura única con TTL: comportamiento puro del almacén."""

    def test_ranura_vacia_devuelve_none(self):
        """Sin publicar nada, la lectura devuelve None."""
        buzon = Buzon()
        assert buzon.leer_ficha() is None
        assert buzon.leer_deposito() is None

    def test_publicar_y_leer(self):
        """Lo publicado se lee intacto."""
        buzon = Buzon()
        buzon.publicar_ficha({"extraidos": [1], "manuales": []})
        assert buzon.leer_ficha() == {"extraidos": [1], "manuales": []}

    def test_ultima_gana(self):
        """Publicar de nuevo reemplaza el contenido de la única ranura."""
        buzon = Buzon()
        buzon.publicar_ficha({"a": 1})
        buzon.publicar_ficha({"b": 2})
        assert buzon.leer_ficha() == {"b": 2}

    def test_ttl_expira(self):
        """Con el TTL vencido, la lectura devuelve None y limpia la ranura."""
        buzon = Buzon(ttl_segundos=0.01)
        buzon.publicar_ficha({"a": 1})
        time.sleep(0.05)
        assert buzon.leer_ficha() is None
        # La limpieza fue efectiva: una nueva lectura sigue en None.
        assert buzon.leer_ficha() is None

    def test_ttl_vigente_devuelve_contenido(self):
        """Dentro del TTL, el contenido sigue disponible en lecturas repetidas."""
        buzon = Buzon(ttl_segundos=60)
        buzon.publicar_ficha({"a": 1})
        assert buzon.leer_ficha() == {"a": 1}
        assert buzon.leer_ficha() == {"a": 1}

    def test_ranuras_independientes(self):
        """La ficha y el depósito no se pisan entre sí."""
        buzon = Buzon()
        buzon.publicar_ficha({"ficha": True})
        buzon.reportar_deposito({"handle": "x"})
        assert buzon.leer_ficha() == {"ficha": True}
        assert buzon.leer_deposito() == {"handle": "x"}

    def test_lectura_devuelve_copia(self):
        """Mutuar lo leído no corrompe el contenido almacenado."""
        buzon = Buzon()
        buzon.publicar_ficha({"a": 1})
        leido = buzon.leer_ficha()
        leido["a"] = 999
        assert buzon.leer_ficha() == {"a": 1}

    def test_limpiar_vacia_todo(self):
        """limpiar() vacía ambas ranuras."""
        buzon = Buzon()
        buzon.publicar_ficha({"a": 1})
        buzon.reportar_deposito({"handle": "x"})
        buzon.limpiar()
        assert buzon.leer_ficha() is None
        assert buzon.leer_deposito() is None


# ---------------------------------------------------------------------------
# Contrato: endpoints HTTP del buzón
# ---------------------------------------------------------------------------


class TestBuzonEndpoints:
    """Flujo POST → GET sobre la app FastAPI real."""

    def test_publicar_y_leer_ficha(self):
        """POST /ficha-pendiente → 204; GET devuelve la ficha intacta."""
        respuesta = CLIENTE.post("/ficha-pendiente", json=FICHA)
        assert respuesta.status_code == 204

        leida = CLIENTE.get("/ficha-pendiente")
        assert leida.status_code == 200
        assert leida.json() == FICHA

    def test_ficha_vacia_da_404(self):
        """GET sin publicar antes → 404 con detalle en español."""
        respuesta = CLIENTE.get("/ficha-pendiente")
        assert respuesta.status_code == 404
        assert "ficha" in respuesta.json()["detail"]

    def test_ficha_ultima_gana_por_http(self):
        """Publicar dos veces: GET devuelve la segunda."""
        CLIENTE.post("/ficha-pendiente", json=FICHA)
        CLIENTE.post("/ficha-pendiente", json=FICHA_REEMPLAZO)
        leida = CLIENTE.get("/ficha-pendiente")
        assert leida.status_code == 200
        assert leida.json() == FICHA_REEMPLAZO

    def test_ficha_payload_invalido_da_422(self):
        """POST sin extraidos/manuales → 422 de validación."""
        respuesta = CLIENTE.post("/ficha-pendiente", json={"cualquier": "cosa"})
        assert respuesta.status_code == 422

    def test_publicar_y_leer_deposito(self):
        """POST /deposito → 204; GET devuelve el reporte intacto."""
        respuesta = CLIENTE.post("/deposito", json=DEPOSITO)
        assert respuesta.status_code == 204

        leido = CLIENTE.get("/deposito")
        assert leido.status_code == 200
        assert leido.json() == DEPOSITO

    def test_deposito_vacio_da_404(self):
        """GET /deposito sin reporte previo → 404."""
        respuesta = CLIENTE.get("/deposito")
        assert respuesta.status_code == 404

    def test_deposito_payload_invalido_da_422(self):
        """POST /deposito sin handle/timestamp → 422."""
        respuesta = CLIENTE.post("/deposito", json={"handle": ""})
        assert respuesta.status_code == 422


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
        respuesta = CLIENTE.post("/ficha-pendiente", json=FICHA)
        assert "access-control-allow-origin" not in respuesta.headers

    def test_endpoints_deposito_sin_cors(self):
        respuesta = CLIENTE.get("/deposito")
        assert "access-control-allow-origin" not in respuesta.headers
        respuesta = CLIENTE.post("/deposito", json=DEPOSITO)
        assert "access-control-allow-origin" not in respuesta.headers
