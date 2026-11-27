"""RN-04: el diagnóstico de márgenes no puede contradecir al semáforo.

1417 y 1418 twips se convierten ambos en «2.50 cm» al redondear. Antes una
regla en rojo decía «#1=2.50 cm; esperado=2.50 cm». El detalle muestra ahora
los twips crudos solo cuando el texto convertido colisiona; la comparación
sigue siendo exacta y la tolerancia de 1 twip no se aplica (decisión de
biblioteca pendiente).
"""

from __future__ import annotations

from pathlib import Path

from docx_factory import compilar_docx, configuracion_base

from validator.engine import load_rules, validate_docx

RAIZ = Path(__file__).resolve().parent.parent
REGLAS = load_rules(str(RAIZ / "reglas_unt.yaml"))
REGLA = "margen_superior"


def _resultado(top: int):
    cfg = configuracion_base()
    cfg["margenes"]["top"] = top
    ruta = Path(compilar_docx(cfg))
    try:
        return next(r for r in validate_docx(str(ruta), REGLAS) if r.rule_id == REGLA)
    finally:
        ruta.unlink(missing_ok=True)


def test_1418_twips_sigue_pasando():
    resultado = _resultado(1418)
    assert resultado.passed, resultado.found


def test_1417_twips_falla_y_muestra_los_valores_crudos():
    """Mismo cm redondeado, twips distintos: el detalle lo explica."""
    resultado = _resultado(1417)
    assert not resultado.passed
    assert "1417 twips (2.50 cm)" in resultado.found, resultado.found
    assert "esperado=1418 twips (2.50 cm)" in resultado.found, resultado.found
    assert "esperado=2.50 cm" not in resultado.found, resultado.found


def test_567_twips_falla_como_desvio_real_sin_añadir_tolerancia():
    """1.00 cm frente a 2.50 cm no necesita el sufijo de twips crudos."""
    resultado = _resultado(567)
    assert not resultado.passed
    assert "1.00 cm" in resultado.found, resultado.found
    assert "esperado=2.50 cm" in resultado.found, resultado.found
    assert "twips" not in resultado.found, resultado.found
