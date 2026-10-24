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
from pathlib import Path

import yaml

from .checks import run_check
from .compilador import CompilerDSL
from .extractor import extract
from .models import RuleResult, Severity


def load_rules(yaml_path: str) -> dict:
    """Carga el YAML de reglas con manejo de errores controlado.

    Lanza `ValueError` con un mensaje claro si el archivo no existe, no es un
    YAML válido o su contenido no es un diccionario (en lugar de una excepción
    cruda de PyYAML o TypeError).
    """
    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ValueError(f"No se encontró el archivo de reglas: {yaml_path}") from e
    except yaml.YAMLError as e:
        raise ValueError(
            f"El archivo de reglas {yaml_path} tiene sintaxis YAML inválida: {e}"
        ) from e
    if not isinstance(data, dict):
        raise ValueError(
            f"El archivo de reglas {yaml_path} no devolvió un diccionario "
            f"(contenido: {type(data).__name__})"
        )
    return data


# Reglas de captura de la ficha de depósito (diseño 17). Viven en un archivo
# aparte de `reglas_unt.yaml` a propósito: son LECTURA (nunca fallan, no
# entran en el semáforo ni en el conteo de reglas verificables), así que no
# comparten el invariante de mutaciones de `tests/_mutations.py`.
REGLAS_FICHA_PATH = str(Path(__file__).resolve().parent.parent / "reglas_ficha.yaml")


def load_ficha_rules(yaml_path: str = REGLAS_FICHA_PATH) -> dict:
    """Carga el ruleset de captura de la ficha de depósito.

    Devuelve `{}` si el archivo no existe: un despliegue sin ficha (p. ej.
    la CLI de referencia) sigue funcionando y `validate_docx` no captura nada.
    """
    if not Path(yaml_path).exists():
        return {}
    return load_rules(yaml_path)


def validate_docx(
    docx_path: str,
    rules_data: dict,
    ficha_data: dict | None = None,
) -> list[RuleResult]:
    """Ejecuta todas las reglas mecanizadas contra un DOCX.

    Si `rules_data` usa el formato DSL (`reglas`), delega en `CompilerDSL`.
    En caso contrario, usa el motor legacy (`rules` con `mecanismo_verificable`).

    Las reglas sin mecanismo verificable (contenido semántico) se omiten
    en ambos formatos — no son verificables por estructura de archivo.
    Ver la sección `no_deterministas` del YAML.

    `ficha_data` es el ruleset de captura de la ficha de depósito
    (`reglas_ficha.yaml`, diseño 17). Si se pasa, se evalúa sobre el MISMO
    DOCX ya extraído y sus resultados (siempre `passed=True`, read-only) se
    anexan al final: `build_report` recoge sus capturas en el campo `ficha`.
    Es `None` en la validación pura (CLI, tests de reglas), de modo que ese
    camino queda idéntico al de siempre.
    """
    extracted = extract(docx_path)

    # Formato DSL (nuevo, declarativo con analizadores/autómatas).
    if "reglas" in rules_data:
        resultados = CompilerDSL().ejecutar(rules_data, extracted)
    else:
        # Formato legacy.
        resultados = _validate_legacy(rules_data, extracted)

    # Captura de la ficha de depósito: segunda pasada sobre el mismo árbol
    # extraído. No valida ni altera el semáforo (sus resultados son passed).
    if ficha_data is not None:
        resultados = resultados + CompilerDSL().ejecutar(ficha_data, extracted)

    return resultados


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


def _agregar_ficha(results: list[RuleResult]) -> dict:
    """Reúne las capturas de ficha (`RuleResult.ficha`) en un dict por campo.

    Cada regla puede haber capturado uno o más datos para la ficha de
    depósito (diseño 17). El contrato de la API (handover §4) espera un
    `dict[campo] = {"valor", "pagina", "detectado"}`; aquí se colapsan los
    items de todas las reglas. Si un campo aparece más de una vez gana el
    primero (las reglas de carátula y las de cuerpo no capturan la misma
    clave). Siempre es un dict, vacío si no hubo capturas.
    """
    ficha: dict[str, dict] = {}
    for r in results:
        for item in r.ficha:
            campo = item.get("campo")
            if not campo or campo in ficha:
                continue
            ficha[campo] = {
                "valor": item.get("valor"),
                "pagina": item.get("pagina"),
                "detectado": bool(item.get("detectado")),
            }
    return ficha


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

    Los resultados de **captura** (ficha de depósito, diseño 17) se excluyen
    del semáforo y del resumen: no son reglas que se cumplen o fallan, solo
    datos que se leen. Sus capturas sí viajan en el campo `ficha`.
    """
    ficha = _agregar_ficha(results)
    results = [r for r in results if not r.captura]
    hay_error_bloqueante = any((not r.passed) and r.severity == Severity.ERROR for r in results)
    evaluadas = [r for r in results if r.aplicable]
    omitidas = len(results) - len(evaluadas)
    reporte_resultados = filter_by_severity(evaluadas, severities)

    return {
        "semaforo": "rojo" if hay_error_bloqueante else "verde",
        "resultados": [r.to_dict() for r in reporte_resultados],
        "ficha": ficha,
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
