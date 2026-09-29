"""Motor de reglas: carga el YAML, ejecuta las reglas mecanizadas contra
un DOCX extraído, y arma el reporte agrupado con filtro de severidad.

Soporta dos formatos de reglas:
- LEGACY  (`rules` con `mecanismo_verificable.checks`): el formato original,
  evaluado por `checks.run_check`. Se conserva para compatibilidad.
- DSL     (`reglas` con secciones `atributo_xml`, `automata_secuencia`,
  `gramatica_estructura`, etc.): el formato declarativo compilado por
  `CompilerDSL`, basado en analizadores y autómatas.

Ambos formatos producen el mismo contrato: `List[RuleResult]`.
"""

from collections.abc import Iterable

import yaml

from .checks import run_check
from .compilador import CompilerDSL
from .extractor import extract
from .models import RuleResult, Severity


def load_rules(yaml_path: str) -> dict:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_docx(docx_path: str, rules_data: dict) -> list[RuleResult]:
    """Ejecuta todas las reglas mecanizadas contra un DOCX.

    Si `rules_data` usa el formato DSL (`reglas`), delega en `CompilerDSL`.
    En caso contrario, usa el motor legacy (`rules` con `mecanismo_verificable`).

    Las reglas sin mecanismo verificable (contenido semántico) se omiten
    en ambos formatos — no son verificables por estructura de archivo.
    Ver la sección `no_deterministas` del YAML.
    """
    extracted = extract(docx_path)

    # Formato DSL (nuevo, declarativo con analizadores/autómatas).
    if "reglas" in rules_data:
        return CompilerDSL().ejecutar(rules_data, extracted)

    # Formato legacy.
    return _validate_legacy(rules_data, extracted)


def _validate_legacy(rules_data: dict, extracted) -> list[RuleResult]:
    """Evalúa el YAML legacy (`rules` + `mecanismo_verificable`)."""
    results: list[RuleResult] = []

    for rule in rules_data.get("rules", []):
        mecanismo = rule.get("mecanismo_verificable")
        if not mecanismo:
            continue

        fallos = []
        for check in mecanismo["checks"]:
            try:
                ok, detalle = run_check(check, extracted, rule)
            except Exception as e:
                # Un check mal formado o un XML inesperado no debe tumbar
                # el resto del reporte — se registra como fallo con detalle.
                ok, detalle = False, f"error ejecutando check: {type(e).__name__}: {e}"
            if not ok:
                fallos.append(detalle)

        results.append(
            RuleResult(
                rule_id=rule["id"],
                passed=not fallos,
                severity=Severity(rule.get("severidad", "error")),
                message=rule.get("descripcion", rule["id"]),
                expected=str(rule.get("valor_esperado", "")),
                found="; ".join(fallos) if fallos else "cumple",
                location=rule.get("ubicacion"),
                fuente=rule.get("fuente", ""),
                cita=rule.get("cita", ""),
            )
        )

    return results


def filter_by_severity(
    results: Iterable[RuleResult], severities: list[str] | None = None
) -> list[RuleResult]:
    """Filtra resultados por severidad. Si severities es None, no filtra."""
    if severities is None:
        return list(results)
    wanted = {Severity(s) for s in severities}
    return [r for r in results if r.severity in wanted]


def build_report(results: list[RuleResult], severities: list[str] | None = None) -> dict:
    """Arma el reporte final.

    El semáforo SIEMPRE se calcula sobre TODOS los resultados con
    severidad "error" (independiente del filtro de severidad del reporte
    detallado) — un filtro de visualización nunca debe poder ocultar un
    bloqueo real de la entrega.

    Las reglas **no aplicables** no entran en `resultados`: no se miraron, y
    listarlas haría creer que se cumplieron. Se cuentan aparte en el resumen,
    junto a cuántas sí se evaluaron. Sin eso, un total fijo haría creer al
    estudiante que 4 reglas se cumplieron cuando en realidad no se miraron
    (decisión 5 del diseño, docs/diseno/15_tipo_documento_grupos.md).
    """
    hay_error_bloqueante = any((not r.passed) and r.severity == Severity.ERROR for r in results)
    evaluadas = [r for r in results if r.aplicable]
    omitidas = len(results) - len(evaluadas)
    reporte_resultados = filter_by_severity(evaluadas, severities)

    return {
        "semaforo": "rojo" if hay_error_bloqueante else "verde",
        "resultados": [r.to_dict() for r in reporte_resultados],
        "resumen": {
            "total": len(results),
            "total_evaluadas": len(evaluadas),
            "reglas_no_aplicables": omitidas,
            "fallidos_error": sum(
                1 for r in results if not r.passed and r.severity == Severity.ERROR
            ),
            "fallidos_warning": sum(
                1 for r in results if not r.passed and r.severity == Severity.WARNING
            ),
        },
    }
