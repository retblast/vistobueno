"""Factory determinista de DOCX sintéticos (Fase F6 — tests de propiedad).

Fachada pública de los módulos privados `tests/_*`:

- `_xml_constants`: namespaces y plantillas XML fijas del paquete OPC.
- `_docx_builder`: definición y compilación del DOCX (configuración base).
- `_mutations`: desvíos mínimos por regla + sincronización con el YAML.

Centraliza la construcción de documentos OPC (zip) de forma declarativa a
partir de un diccionario de configuración, de modo que los tests de
propiedad puedan pedir:

- `configuracion_base()`: el documento "bueno", que cumple TODAS las reglas
  mecánicas. Las dos estructuras de otros tipos de TINV no le aplican (el
  documento es un plan cuantitativo). Resultado esperado: 48 evaluadas, 0 fallos.
- `aplicar_mutacion(rule_id, config)`: aplica un desvío MÍNIMO (una sola
  propiedad) contra el documento bueno, de forma que solo la regla
  `rule_id` cambie su resultado.

Mantiene la firma pública usada por los tests (import top-level, sin
paquete), delegando en los módulos internos.

Uso desde tests:
    from docx_factory import configuracion_base, aplicar_mutacion, compilar_docx
"""

from _docx_builder import (
    ANEXOS_BASE,
    compilar_docx,
    configuracion_base,
)
from _mutations import (
    DESVIOS_BASE,
    NO_APLICABLES_BASE,
    NO_APLICABLES_TOTAL,
    REGLAS,
    REGLAS_ACOPLADAS,
    REGLAS_OK_BASE,
    TOTAL_REGLAS,
    aplicar_mutacion,
)

__all__ = [
    "ANEXOS_BASE",
    "DESVIOS_BASE",
    "NO_APLICABLES_BASE",
    "NO_APLICABLES_TOTAL",
    "REGLAS",
    "REGLAS_ACOPLADAS",
    "REGLAS_OK_BASE",
    "TOTAL_REGLAS",
    "aplicar_mutacion",
    "compilar_docx",
    "configuracion_base",
]


def resultado_por_regla(resultados):
    return {r.rule_id: r for r in resultados}
