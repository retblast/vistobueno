"""Contrato de captura de la ficha de depósito (auditoría 2026-10-26).

La ficha pre-llena el formulario oficial de DSpace y alimenta las
constancias y el registro: si la captura parte un autor en dos o se
queda vacía, el papeleo sale mal (y el operador no ve el error).

Este archivo fija el **criterio de aceptación** de los hallazgos del
motor (AUD-24, AUD-25, AUD-26, AUD-27) sobre un DOCX con la
**estructura real** de la carátula (ver `tests/_caratula_real.py`): la
etiqueta `AUTORES:` en su propio párrafo, un autor por párrafo, líneas
de ORCID intercaladas, la etiqueta `ASESORA:` en su propio párrafo y el
año en la última línea de la portada.

Los tests marcados `xfail(strict=True)` fallan hoy: son la especificación
del arreglo de Int3. Cuando el motor los cumpla, el `XPASS` estricto
pone el CI en rojo hasta que Int1 quite la marca (ver
`docs/HANDOVER_AUDITORIA_2026-10-26.md` §6).

Uso:
    pytest tests/test_captura_ficha.py -v
"""

from pathlib import Path

import pytest
from _caratula_real import capturar_ficha, crear_docx_caratula, valor

from validator.api import _ficha_desde_reporte


@pytest.fixture(scope="module")
def ficha() -> dict:
    """Las capturas que publica el motor para el DOCX de carátula real."""
    ruta = crear_docx_caratula()
    try:
        return capturar_ficha(ruta)
    finally:
        Path(ruta).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AUD-24 — los autores se parten por la coma de "Apellidos, Nombres"
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "AUD-24: la captura parte cada autor por la coma de 'Apellidos, "
        "Nombres' y se queda con un solo párrafo. Ver "
        "docs/HANDOVER_AUDITORIA_2026-10-26.md §4 (AUD-24)."
    ),
)
def test_autores_un_por_parrafo(ficha):
    """Dos párrafos de autor → DOS autores, sin partir por la coma."""
    assert valor(ficha, "dc.contributor.author") == [
        "Br. Apellido, Nombre",
        "Br. Apellido2, Nombre2",
    ]


# ---------------------------------------------------------------------------
# AUD-25 — el asesor llega vacío marcado como detectado
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "AUD-25: la etiqueta 'ASESORA:' va en su propio párrafo; el nombre "
        "está en el siguiente. La captura toma la etiqueta y devuelve ''. "
        "Ver docs/HANDOVER_AUDITORIA_2026-10-26.md §4 (AUD-25)."
    ),
)
def test_asesor_toma_el_parrafo_siguiente(ficha):
    """El asesor es el párrafo que sigue a la etiqueta."""
    assert valor(ficha, "dc.contributor.advisor") == "Dra. Apellido, Nombre"


# ---------------------------------------------------------------------------
# AUD-26 — el año se lee del final del título
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "AUD-26: el ancla 'trujillo' casa el párrafo del título (que "
        "termina en ', Trujillo 2024') en vez de la línea de portada. "
        "Ver docs/HANDOVER_AUDITORIA_2026-10-26.md §4 (AUD-26)."
    ),
)
def test_anio_toma_el_anio_de_portada(ficha):
    """El año es el de la portada (2026), no el que aparece en el título."""
    assert valor(ficha, "dc.date.issued") == "2026"


# ---------------------------------------------------------------------------
# AUD-27 — la última palabra clave conserva el punto final
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "AUD-27: la última palabra clave conserva el punto final de la "
        "línea APA. Ver docs/HANDOVER_AUDITORIA_2026-10-26.md §4 (AUD-27)."
    ),
)
def test_palabras_clave_sin_puntuacion_final(ficha):
    """Las palabras clave van limpias de puntuación final."""
    assert valor(ficha, "dc.subject") == ["Educación", "Cultura", "Identidad cultural"]


# ---------------------------------------------------------------------------
# Lo que Int1 SÍ garantiza hoy: la API no publica un valor inservible
# ---------------------------------------------------------------------------


def test_el_motor_marca_el_asesor_vacio_como_detectado(ficha):
    """Evidencia del defecto: el motor publica detectado=True con valor ''.

    Este test **pasa hoy**: documenta el comportamiento del motor que
    rompe el contrato. Cuando Int3 lo corrija, este test falla y hay que
    borrarlo (junto con la marca `xfail` de los tests de arriba).
    """
    asesor = ficha.get("dc.contributor.advisor") or {}
    assert asesor.get("detectado") is True
    assert asesor.get("valor") == ""


def test_la_api_degrada_el_valor_inservible_a_no_detectado():
    """El contrato de la API: detectado=true implica valor utilizable."""
    ficha_api = _ficha_desde_reporte(
        {
            "ficha": {
                "dc.contributor.advisor": {"valor": "", "pagina": 1, "detectado": True},
                "dc.date.issued": {"valor": "Trujillo - Perú", "pagina": 1, "detectado": True},
            }
        }
    )
    por_campo = {campo.campo: campo for campo in ficha_api.extraidos}

    asesor = por_campo["dc.contributor.advisor"]
    assert asesor.detectado is False
    assert asesor.valor is None
    assert asesor.pagina is None

    anio = por_campo["dc.date.issued"]
    assert anio.detectado is False
    assert anio.valor is None
    assert anio.pagina is None
