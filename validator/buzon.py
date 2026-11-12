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
from datetime import UTC, datetime, timedelta
from uuid import uuid4

TTL_SEGUNDOS_POR_DEFECTO = 3600.0  # 1 hora


class SinFichaVigente(Exception):
    """No hay una ficha publicada y vigente para aceptar el reporte."""


class TramiteNoCoincide(Exception):
    """El reporte o el papeleo pertenece a un trámite anterior."""


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
        self._ficha_tramite_id: str | None = None
        self._ficha_vence_en: datetime | None = None
        self._deposito: dict | None = None
        self._deposito_publicado_en: float = 0.0

    def _limpiar_ranuras(self) -> None:
        """Vacía el estado; el llamador ya tiene el lock."""
        self._ficha = None
        self._ficha_publicada_en = 0.0
        self._ficha_tramite_id = None
        self._ficha_vence_en = None
        self._deposito = None
        self._deposito_publicado_en = 0.0

    def _ficha_vigente(self) -> tuple[dict, str, datetime] | None:
        """Devuelve la ficha vigente o limpia las ranuras; requiere lock."""
        if self._ficha is None or self._ficha_tramite_id is None or self._ficha_vence_en is None:
            return None
        if time.monotonic() - self._ficha_publicada_en > self._ttl:
            self._limpiar_ranuras()
            return None
        return dict(self._ficha), self._ficha_tramite_id, self._ficha_vence_en

    # --- Ranura de la ficha (SPA → userscript) ---

    def publicar_ficha(self, ficha: dict) -> tuple[str, datetime]:
        """Publica la ficha y devuelve su trámite y vencimiento.

        Cada publicación crea un trámite nuevo y descarta el depósito
        anterior: un título igual no significa que sea la misma tesis.
        """
        with self._lock:
            ahora = time.monotonic()
            self._ficha = dict(ficha)
            self._ficha_publicada_en = ahora
            self._ficha_tramite_id = uuid4().hex
            self._ficha_vence_en = datetime.now(UTC) + timedelta(seconds=self._ttl)
            self._deposito = None
            self._deposito_publicado_en = 0.0
            return self._ficha_tramite_id, self._ficha_vence_en

    def leer_ficha(self) -> tuple[dict, str, datetime] | None:
        """Devuelve ficha, trámite y vencimiento; None si vacía o expirada.

        Una ranura expirada se limpia en esta misma lectura.
        Devuelve una copia: el llamador no puede mutar el contenido.
        """
        with self._lock:
            return self._ficha_vigente()

    # --- Ranura del depósito (userscript → SPA) ---

    def reportar_deposito(self, datos: dict) -> None:
        """Reporta el depósito de la ficha vigente; reemplaza el anterior.

        Rechaza el reporte si no hay ficha vigente o si el trámite no
        coincide. Así un ítem de una ficha anterior no puede cerrar la
        ficha actual.
        """
        with self._lock:
            vigente = self._ficha_vigente()
            if vigente is None:
                raise SinFichaVigente(
                    "No hay una ficha vigente: expiró o no se preparó el depósito."
                )
            _, tramite_id, _ = vigente
            if datos.get("tramite_id") != tramite_id:
                raise TramiteNoCoincide(
                    "El depósito pertenece a un trámite anterior; vuelve a preparar la ficha."
                )
            self._deposito = dict(datos)
            self._deposito_publicado_en = time.monotonic()

    def leer_deposito(self) -> dict | None:
        """Devuelve el depósito vigente; None si vacío, expirado o ajeno."""
        with self._lock:
            if self._deposito is None:
                return None
            vigente = self._ficha_vigente()
            if vigente is None:
                return None
            _, tramite_id, _ = vigente
            if self._deposito.get("tramite_id") != tramite_id:
                self._deposito = None
                return None
            if time.monotonic() - self._deposito_publicado_en > self._ttl:
                self._deposito = None
                return None
            return dict(self._deposito)

    # --- Higiene ---

    def limpiar(self) -> None:
        """Vacía ambas ranuras (uso en tests y para reiniciar el flujo)."""
        with self._lock:
            self._limpiar_ranuras()
