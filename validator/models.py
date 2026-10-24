"""Modelos de datos para resultados de validación."""

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


# Resultados que NO son reglas del YAML sino la traducción de un estado de la
# detección de tipo documental (`compilador._con_sentinel`). No describen un
# defecto corregible en Word, así que quedan fuera de la sección "cómo
# preguntar a una IA" (revisión PR #45, punto 4).
RULES_CENTINELA = frozenset(
    {
        "tipo_documento_no_determinado",
        "tipo_documento_contradictorio",
        "tipo_documento_sin_estructura",
    }
)


@dataclass
class RuleResult:
    rule_id: str
    passed: bool
    severity: Severity
    message: str
    expected: str = ""
    found: str = ""
    # Indica si la regla llegó a evaluarse. Una regla no aplicable
    # (`aplicar_si` que no se cumple para el tipo de documento detectado)
    # no puede bloquear la entrega, por eso se separa de `passed`:
    # `aplicable=False` significa "esta regla no le toca a este documento".
    aplicable: bool = True
    location: str | None = None
    fuente: str = ""
    cita: str = ""
    # Datos capturados para la ficha de depósito (diseño 17). Cada entrada es
    # `{"campo": str, "valor": str | list[str], "pagina": int | None,
    # "detectado": bool}`. Es un canal de LECTURA: no participa del semáforo ni
    # de `passed`. Vacío para la inmensa mayoría de reglas.
    ficha: list[dict] = field(default_factory=list)
    # True si el resultado proviene de una regla de CAPTURA (`reglas_ficha.yaml`,
    # sección `extraccion`) y no de una regla de validación. `build_report` los
    # excluye del semáforo y del `resumen`: no son reglas que se cumplen o
    # fallan, solo datos que se leen.
    captura: bool = False

    def to_dict(self) -> dict:
        # `aplicable` NO se expone aquí: el contrato por regla es estable y
        # las reglas no aplicables se filtran del reporte (ver `build_report`),
        # contando aparte en `resumen`. Es un criterio de filtrado, no un dato
        # de la regla.
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "expected": self.expected,
            "found": self.found,
            "location": self.location,
            "fuente": self.fuente,
            "cita": self.cita,
            "ficha": list(self.ficha),
        }
