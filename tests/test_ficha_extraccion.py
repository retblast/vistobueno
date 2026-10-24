"""Tests de la captura de la ficha de depósito (diseño 17).

Verifican que el motor expone, con página, el texto completo de los 7 campos
que la SPA necesita para pre-llenar el formulario oficial de DSpace (la 8ª
clave, `renati.juror`, es opcional y no se captura: ver diseño 17 §6), y que la
captura es de SOLO LECTURA: no cambia el semáforo ni agrega reglas de
validación.

Contrato: `docs/HANDOVER_MOTOR_FICHA_DEPOSITO.md` §4 y `docs/PLAN_FICHA_DEPOSITO.md` §4.2.
"""

from docx_factory import compilar_docx, configuracion_base

from validator.engine import (
    build_report,
    load_ficha_rules,
    load_rules,
    validate_docx,
)

RULES = load_rules("reglas_unt.yaml")
FICHA = load_ficha_rules()


def _ficha(path: str) -> dict:
    resultados = validate_docx(path, RULES, FICHA)
    return build_report(resultados)["ficha"]


def test_ficha_captura_los_siete_campos_del_doc_bueno():
    path = compilar_docx(configuracion_base())
    try:
        ficha = _ficha(path)
    finally:
        import os

        os.unlink(path)

    # Las 7 claves acordadas (renati.juror es opcional y no se captura hoy).
    assert set(ficha) == {
        "dc.title",
        "dc.contributor.author",
        "dc.contributor.advisor",
        "dc.description.abstract",
        "dc.subject",
        "dc.date.issued",
        "escuela",
    }
    assert all(dato["detectado"] for dato in ficha.values())


def test_ficha_valores_esperados_del_doc_bueno():
    path = compilar_docx(configuracion_base())
    try:
        ficha = _ficha(path)
    finally:
        import os

        os.unlink(path)

    assert "Estrategias lúdicas" in ficha["dc.title"]["valor"]
    assert ficha["dc.contributor.author"]["valor"] == ["Ana María Pérez García"]
    assert ficha["dc.contributor.advisor"]["valor"] == "Mag. Carlos Alberto RODRÍGUEZ MIRANDA"
    assert ficha["escuela"]["valor"] == "ESCUELA PROFESIONAL DE EDUCACIÓN INICIAL"
    assert ficha["dc.date.issued"]["valor"] == "2026"
    assert ficha["dc.subject"]["valor"] == ["clave0", "clave1", "clave2"]
    assert "resumen0" in ficha["dc.description.abstract"]["valor"]


def test_ficha_incluye_pagina_de_origen():
    path = compilar_docx(configuracion_base())
    try:
        ficha = _ficha(path)
    finally:
        import os

        os.unlink(path)

    # La carátula es la página 1.
    assert ficha["dc.title"]["pagina"] == 1
    assert ficha["dc.contributor.author"]["pagina"] == 1
    assert ficha["escuela"]["pagina"] == 1
    assert ficha["dc.date.issued"]["pagina"] == 1
    # Resumen y palabras clave viven en una página posterior a la 1.
    assert ficha["dc.description.abstract"]["pagina"] >= 2
    assert ficha["dc.subject"]["pagina"] >= 2


def test_ficha_es_solo_lectura_no_cambia_semaforo():
    """La captura no altera el veredicto: doc bueno sigue verde con/sin ficha."""
    path = compilar_docx(configuracion_base())
    try:
        sin_ficha = build_report(validate_docx(path, RULES))
        con_ficha = build_report(validate_docx(path, RULES, FICHA))
    finally:
        import os

        os.unlink(path)

    assert sin_ficha["semaforo"] == "verde"
    assert con_ficha["semaforo"] == "verde"
    assert sin_ficha["ficha"] == {}
    assert con_ficha["resumen"] == sin_ficha["resumen"]


def test_load_ficha_rules_sin_archivo_devuelve_vacio(tmp_path):
    """Un despliegue sin ficha (CLI) no falla: ruleset vacío."""
    assert load_ficha_rules(str(tmp_path / "no_existe.yaml")) == {}
