"""Buzón de una ranura para la comunicación con el userscript de depósito.

Mecanismo de intercambio entre la SPA (que publica la ficha completada
por el operador) y el userscript que corre en el navegador del operador
sobre las páginas de DSpace (que lee la ficha y reporta el depósito
realizado).

Diseño (ver docs/PLAN_FICHA_DEPOSITO.md §6):

- **Una sola ranura** por dirección (ficha y depósito): "última gana".
  Supuesto documentado: un operador, una tesis en vuelo a la vez (así
  trabaja hoy el registro: filas secuenciales).
- **TTL de 1 hora**: una ficha olvidada no puede auto-rellenar un
  formulario horas después. La lectura de una ranura expirada la limpia.
- **Estado en memoria del proceso**: sin base de datos, sin sesiones. Un
  reinicio vacía el buzón; el operador simplemente re-valida y re-prepara.
- **Thread-safe**: los endpoints síncronos de FastAPI corren en el
  threadpool, por lo que el acceso concurrente es posible.

Seguridad (docs/PLAN_FICHA_DEPOSITO.md §6): la API no agrega cabeceras
CORS, así que una página web cualquiera en el navegador del operador no
puede LEER el contenido del buzón (contiene datos personales del
estudiante). El userscript lo lee por GM_xmlhttpRequest, que corre en el
contexto de la extensión y no está sujeto a CORS.
"""

import threading
import time

TTL_SEGUNDOS_POR_DEFECTO = 3600.0  # 1 hora


class Buzon:
    """Buzón de una ranura por dirección, con TTL y "última gana".

    Atributos:
        ttl_segundos: Vigencia de cada contenido publicado, en segundos.
    """

    def __init__(self, ttl_segundos: float = TTL_SEGUNDOS_POR_DEFECTO) -> None:
        self._ttl = ttl_segundos
        self._lock = threading.Lock()
        self._ficha: dict | None = None
        self._ficha_publicada_en: float = 0.0
        self._deposito: dict | None = None
        self._deposito_publicado_en: float = 0.0

    # --- Ranura de la ficha (SPA → userscript) ---

    def publicar_ficha(self, ficha: dict) -> None:
        """Publica la ficha completada; reemplaza la anterior (última gana)."""
        with self._lock:
            self._ficha = dict(ficha)
            self._ficha_publicada_en = time.monotonic()

    def leer_ficha(self) -> dict | None:
        """Devuelve la ficha vigente; None si está vacía o expirada.

        Una ranura expirada se limpia en esta misma lectura.
        Devuelve una copia: el llamador no puede mutar el contenido.
        """
        with self._lock:
            if self._ficha is None:
                return None
            if time.monotonic() - self._ficha_publicada_en > self._ttl:
                self._ficha = None
                return None
            return dict(self._ficha)

    # --- Ranura del depósito (userscript → SPA) ---

    def reportar_deposito(self, datos: dict) -> None:
        """Reporta el depósito realizado; reemplaza el anterior."""
        with self._lock:
            self._deposito = dict(datos)
            self._deposito_publicado_en = time.monotonic()

    def leer_deposito(self) -> dict | None:
        """Devuelve el depósito reportado; None si está vacío o expirado."""
        with self._lock:
            if self._deposito is None:
                return None
            if time.monotonic() - self._deposito_publicado_en > self._ttl:
                self._deposito = None
                return None
            return dict(self._deposito)

    # --- Higiene ---

    def limpiar(self) -> None:
        """Vacía ambas ranuras (uso en tests y para reiniciar el flujo)."""
        with self._lock:
            self._ficha = None
            self._deposito = None
