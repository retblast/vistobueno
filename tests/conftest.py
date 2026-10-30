"""Utilidades compartidas para la suite de tests de VistoBueno.

Proporciona el cliente de prueba, constantes de validación de contrato,
la ruta al DOCX de prueba (plantilla oficial o factory) y un helper para
subirlo a la API.
"""

from functools import cache
from pathlib import Path

import pytest
from docx_factory import compilar_docx, configuracion_base
from fastapi.testclient import TestClient

from validator import api as api_module
from validator.api import app

# ---------------------------------------------------------------------------
# Cliente de prueba global
# ---------------------------------------------------------------------------

# El peer se fija en el loopback: la API solo se sirve desde la máquina
# donde corre la app (auditoría 2026-10-26, AUD-09) y el `TestClient` por
# defecto usa el host "testserver", que no es loopback. El `base_url`
# también es loopback para pasar el chequeo del header Host (AUD-28).
CLIENTE = TestClient(app, client=("127.0.0.1", 50000), base_url="http://127.0.0.1")


@pytest.fixture(autouse=True)
def _reiniciar_limitador():
    """Los limitadores son estado del proceso: cada test arranca limpio.

    Sin esto, el cupón por IP se llenaría a lo largo de la suite y las
    pruebas de `POST /validar` empezarían a recibir 429. Se limpian los
    tres cupos: la ventana fija (legacy) y los dos adaptativos por CPU.
    """
    api_module._LIMITADOR_PETICIONES.limpiar()
    api_module._LIMITADOR_CPU_VALIDACION.limpiar()
    api_module._LIMITADOR_CPU_PAPELES.limpiar()
    yield
    api_module._LIMITADOR_PETICIONES.limpiar()
    api_module._LIMITADOR_CPU_VALIDACION.limpiar()
    api_module._LIMITADOR_CPU_PAPELES.limpiar()


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
    "aplicable",
}

# Campos del objeto 'resumen'
CAMPOS_RESUMEN = {
    "total",
    "total_evaluadas",
    "reglas_no_aplicables",
    "fallidos_error",
    "fallidos_warning",
}

# Campos del objeto 'metadatos'
CAMPOS_METADATOS = {
    "archivo_nombre",
    "archivo_tamano_bytes",
    "reglas_evaluadas",
    "reglas_totales",
    "version_esquema",
    "tipo_documento_declarado",
    "tipo_documento_inferido",
    "tipo_documento_estado",
}


# ---------------------------------------------------------------------------
# Ruta al DOCX de prueba
# ---------------------------------------------------------------------------


@cache
def ruta_docx_prueba() -> Path:
    """Ruta del DOCX de prueba para los tests de contrato (hallazgo B1).

    Prefiere la plantilla oficial de recursos/ (salida real de Word).
    Si no existe — recursos/ está en .gitignore, así que es el caso de la
    CI — genera el documento bueno del factory: determinista y sin
    dependencias externas. Sin este fallback, 21 tests de contrato se
    saltaban SIEMPRE en CI y el POST /validar con un DOCX real quedaba
    sin probar con el pipeline en verde.
    """
    if PLANTILLA.exists():
        return PLANTILLA
    return Path(compilar_docx(configuracion_base()))


# ---------------------------------------------------------------------------
# Helper para subir el DOCX de prueba
# ---------------------------------------------------------------------------


def subir_plantilla(
    ruta: str = "/validar",
    nombre: str = "tesis.docx",
    mime: str = MIME_DOCX,
    data: dict | None = None,
):
    """Envía el DOCX de prueba (plantilla o factory) a POST /validar.

    Args:
        ruta: URL del endpoint (permite query params, ej. "?incluir_prompts_ia=false").
        nombre: nombre de archivo declarado en el multipart.
        mime: Content-Type declarado del archivo.
        data: campos form adicionales (ej. {"correo": ...}).

    Returns:
        La respuesta del TestClient.
    """
    with open(ruta_docx_prueba(), "rb") as f:
        kwargs = {"files": {"archivo": (nombre, f, mime)}}
        if data is not None:
            kwargs["data"] = data
        return CLIENTE.post(ruta, **kwargs)
