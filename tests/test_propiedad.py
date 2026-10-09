"""Tests de propiedad (Fase F6): el motor DSL preserva la correlación
regla ↔ resultado.

El factory `docx_factory` genera un documento "bueno" que cumple TODAS las
reglas mecánicas salvo los esquemas alternativos de estructura
(cualitativo y revisión de literatura), que son mutuamente excluyentes con
el plan cuantitativo. Sobre ese documento se verifican dos propiedades:

1. `test_doc_bueno_pasa_46` — el documento bueno pasa exactamente 46/48
   reglas, y las únicas no pasadas son las documentadas en
   `NO_APLICABLES_BASE`.

2. `test_mutacion_afecta_solo_esa_regla` — para cada una de las 48 reglas,
   aplicar su mutación (desvío MÍNIMO) cambia el resultado SOLO de esa
   regla (comparación punto a punto `(passed, found)` contra el documento
   bueno). Las reglas acopladas por mecanismo IDÉNTICO se declaran en
   `REGLAS_ACOPLADAS` y se validan con su conjunto esperado.

Nota técnica: los autómatas de estructura reportan en `found` un contador
interno `headings=N` que cambia ante cualquier inserción/renombrado de
cabeceras (aunque la semántica no cambie). Por eso, para las reglas
`estructura_tinv_*`, el observable comparado es `passed`; para el resto,
`(passed, found)`.

Uso:
    pytest tests/test_propiedad.py -v
"""

from pathlib import Path

import pytest
from docx_factory import (
    NO_APLICABLES_BASE,
    REGLAS,
    REGLAS_ACOPLADAS,
    aplicar_mutacion,
    compilar_docx,
    configuracion_base,
)

from validator.engine import load_rules, validate_docx

RULES = load_rules("reglas_unt.yaml")

ESTRUCTURA = {
    "estructura_tinv_cuantitativo",
    "estructura_tinv_cualitativo",
    "estructura_tinv_revision_literatura",
}


def _por_regla(resultados):
    return {r.rule_id: r for r in resultados}


def _estado(docx_path: str) -> dict:
    """`(rule_id -> (passed, found))`; para estructura `(passed, aplicable)`.

    Las reglas de estructura no se comparan por `found` porque los autómatas
    reportan un contador interno `headings=N` que cambia ante cualquier
    inserción o renombrado, aunque la semántica no cambie. Se comparan por
    `aplicable` en su lugar: desde el paso 4 la aplicabilidad depende del tipo
    detectado, así que es la señal que distingue "esta tesis es de otro tipo"
    de "esta tesis está mal estructurada", y sin ella una mutación que hace
    aplicable una estructura alternativa no se observaría (no aplicable y
    aplicable dan las dos `passed=True`).
    """
    return {
        r.rule_id: (
            (r.passed, None if r.rule_id in ESTRUCTURA else r.found)
            if r.rule_id not in ESTRUCTURA
            else (r.passed, r.aplicable)
        )
        for r in validate_docx(docx_path, RULES)
    }


def _sin_archivo(path: str):
    Path(path).unlink(missing_ok=True)


# El paso 6 agrega un error centinela (`tipo_documento_no_determinado` /
# `tipo_documento_contradictorio`) cuando la detección no puede clasificar el
# documento, y el issue #5 del handover trae el warning
# `tipo_documento_sin_estructura` cuando el tipo detectado (proyecto, informe,
# TSP) todavía no tiene esquema en `reglas_unt.yaml`. Ninguno es una de las 48
# reglas: los deriva la detección, así que no tienen mutación propia ni cuenta
# para `REGLAS`. En un documento mutado pueden aparecer (y en el base no), por
# lo que se excluyen de la comparación punto a punto para no contarlos como
# "movidas".
CENTINELAS = {
    "tipo_documento_no_determinado",
    "tipo_documento_contradictorio",
    "tipo_documento_sin_estructura",
}


def _compare(path_a: str, path_b: str, esperado: set, rule_id: str):
    """Verifica que la única diferencia entre dos documentos es `esperado`."""
    a = {rid: v for rid, v in _estado(path_a).items() if rid not in CENTINELAS}
    b = {rid: v for rid, v in _estado(path_b).items() if rid not in CENTINELAS}
    assert set(a) == set(b) == set(REGLAS)
    diffs = {rid for rid in a if a[rid] != b[rid]}
    assert diffs == esperado, (
        f"regla {rule_id}: la mutación cambió {sorted(diffs)}, esperado {sorted(esperado)}"
    )


def test_doc_bueno_pasa_sin_fallos():
    """El documento base no falla NINGUNA regla. Este es el arreglo.

    Antes fallaban las dos estructuras de otros tipos de tesis
    (`estructura_tinv_cualitativo` y `estructura_tinv_revision_literatura`),
    errores imposibles de corregir para una tesis cuantitativa que ponían el
    semáforo en rojo. Con la detección de tipo, esas dos ya no aplican y
    el documento sale limpio.
    """
    cfg = configuracion_base()
    path = compilar_docx(cfg)
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)

    assert len(res) == 48
    fallos = {rid for rid, r in res.items() if not r.passed}
    assert fallos == set(), f"fallos={sorted(fallos)}"


def test_doc_bueno_solo_omite_las_reglas_de_otros_tipos():
    """Las no aplicables son exactamente las reglas de otros tipos de
    documento: los 2 esquemas de estructura alternativos y, desde el issue
    #5 del handover, sus mínimos de referencias/anexos y el texto de
    carátula del Proyecto."""
    cfg = configuracion_base()
    path = compilar_docx(cfg)
    try:
        res = _por_regla(validate_docx(path, RULES))
    finally:
        _sin_archivo(path)

    no_aplicables = {rid for rid, r in res.items() if not r.aplicable}
    assert no_aplicables == NO_APLICABLES_BASE


@pytest.mark.parametrize("rule_id", REGLAS)
def test_mutacion_afecta_solo_esa_regla(rule_id):
    """Cada desvío mínimo invalida únicamente su regla (o su par acoplado)."""
    base_cfg = configuracion_base()
    path_base = compilar_docx(base_cfg)
    try:
        path_mut = compilar_docx(aplicar_mutacion(rule_id, base_cfg))
        try:
            esperado = REGLAS_ACOPLADAS.get(rule_id, set()) | {rule_id}
            _compare(path_base, path_mut, esperado, rule_id)
        finally:
            _sin_archivo(path_mut)
    finally:
        _sin_archivo(path_base)


def test_mutaciones_cubren_las_48_reglas():
    """Cadena de seguridad: toda regla de reglas_unt.yaml tiene mutación."""
    ids_yaml = {r["id"] for r in RULES["reglas"]}
    assert ids_yaml == set(REGLAS)
    assert len(REGLAS) == 48
