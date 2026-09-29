"""Modelos de datos para resultados de validación."""

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


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
        }
