"""Utilidades compartidas para la suite de tests de VistoBueno.

Proporciona el cliente de prueba, constantes de validación de contrato,
la ruta a la plantilla de prueba y un helper para subirla a la API.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from validator.api import app

# ---------------------------------------------------------------------------
# Cliente de prueba global
# ---------------------------------------------------------------------------

CLIENTE = TestClient(app)

# ---------------------------------------------------------------------------
# Rutas a recursos de prueba
# ---------------------------------------------------------------------------

RECURSOS_DIR = Path(__file__).resolve().parent.parent / "recursos"
PLANTILLA = RECURSOS_DIR / "EDUCACION INICIAL-PLANTILLA INVESTIGACIÓN CUANTITATIVA.docx"

# MIME type oficial de los DOCX (paquetes OOXML)
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ---------------------------------------------------------------------------
# Constantes de validación de contrato (campos esperados en la respuesta API)
# ---------------------------------------------------------------------------

# Campos que debe tener cada elemento en 'resultados'
CAMPOS_RESULTADO = {
    "rule_id",
    "paso",
    "severidad",
    "mensaje",
    "esperado",
    "encontrado",
    "ubicacion",
    "fuente",
    "cita",
}

# Campos del objeto 'resumen'
CAMPOS_RESUMEN = {"total", "fallidos_error", "fallidos_warning"}

# Campos del objeto 'metadatos'
CAMPOS_METADATOS = {
    "archivo_nombre",
    "archivo_tamano_bytes",
    "reglas_evaluadas",
    "version_esquema",
}


# ---------------------------------------------------------------------------
# Helper para subir la plantilla
# ---------------------------------------------------------------------------


def subir_plantilla(
    ruta: str = "/validar",
    nombre: str = "tesis.docx",
    mime: str = MIME_DOCX,
    data: dict | None = None,
):
    """Envía la plantilla oficial a POST /validar y devuelve la respuesta.

    Args:
        ruta: URL del endpoint (permite query params, ej. "?incluir_prompts_ia=false").
        nombre: nombre de archivo declarado en el multipart.
        mime: Content-Type declarado del archivo.
        data: campos form adicionales (ej. {"correo": ...}).

    Returns:
        La respuesta del TestClient. Salta el test si la plantilla no
        existe en recursos/.
    """
    if not PLANTILLA.exists():
        pytest.skip("Plantilla de prueba no disponible")
    with open(PLANTILLA, "rb") as f:
        kwargs = {"files": {"archivo": (nombre, f, mime)}}
        if data is not None:
            kwargs["data"] = data
        return CLIENTE.post(ruta, **kwargs)
