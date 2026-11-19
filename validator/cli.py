"""CLI de referencia para correr el validador localmente contra un DOCX.

Uso:
    python -m validator.cli tesis.docx unt_format_rules_schema.yaml
    python -m validator.cli tesis.docx unt_format_rules_schema.yaml --severity error
    python -m validator.cli tesis.docx unt_format_rules_schema.yaml --json
    python -m validator.cli tesis.docx reglas_unt.yaml --formato markdown --salida reporte.md
    python -m validator.cli tesis.docx reglas_unt.yaml --formato pdf --salida reporte.pdf
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine import build_report, load_rules, validate_docx
from .exportador import reporte_a_markdown, reporte_a_pdf
from .prompts import build_ai_help_section


def main():
    parser = argparse.ArgumentParser(description="Validador de formato de tesis (UNT)")
    parser.add_argument("docx", help="Ruta al archivo .docx a validar")
    parser.add_argument("rules", help="Ruta al YAML de reglas")
    parser.add_argument(
        "--severity",
        choices=["error", "warning"],
        action="append",
        help="Filtra el reporte detallado por severidad (repetible). Por defecto muestra todas.",
    )
    parser.add_argument("--json", action="store_true", help="Imprime el reporte en JSON")
    parser.add_argument(
        "--formato",
        choices=["json", "markdown", "pdf"],
        help="Formato de exportación del reporte. Si no se indica, usa el modo texto de terminal.",
    )
    parser.add_argument(
        "--salida",
        help="Ruta del archivo de salida para --formato (default: stdout para json/markdown).",
    )
    args = parser.parse_args()

    rules_data = load_rules(args.rules)
    results = validate_docx(args.docx, rules_data)
    reporte = build_report(results, severities=args.severity)

    # --json es un atajo de --formato json (compatibilidad).
    if args.json and args.formato is None:
        args.formato = "json"

    if args.formato == "json":
        reporte["como_preguntar_a_una_ia"] = build_ai_help_section(
            [r for r in results if not r.passed]
        )
        texto = json.dumps(reporte, ensure_ascii=False, indent=2)
        _escribir(texto, args.salida)
        return

    if args.formato == "markdown":
        reporte["como_preguntar_a_una_ia"] = build_ai_help_section(
            [r for r in results if not r.passed]
        )
        _escribir(reporte_a_markdown(reporte), args.salida)
        return

    if args.formato == "pdf":
        reporte["como_preguntar_a_una_ia"] = build_ai_help_section(
            [r for r in results if not r.passed]
        )
        _escribir_bytes(reporte_a_pdf(reporte), args.salida)
        return

    resumen = reporte["resumen"]
    print(f"Semáforo: {reporte['semaforo'].upper()}")
    print(f"Reglas evaluadas: {resumen['total_evaluadas']} de {resumen['total']}")
    print(f"No aplicables: {resumen['reglas_no_aplicables']}")
    print(f"Errores fallidos: {resumen['fallidos_error']}")
    print(f"Warnings fallidos: {resumen['fallidos_warning']}")
    print()
    for r in reporte["resultados"]:
        estado = "OK  " if r["passed"] else f"FAIL[{r['severity']}]"
        print(f"{estado} {r['rule_id']}: {r['message']}")
        if not r["passed"]:
            print(f"      esperado:   {r['expected']}")
            print(f"      encontrado: {r['found']}")

    if reporte["semaforo"] == "rojo":
        sys.exit(1)


def _escribir(texto: str, salida: str | None) -> None:
    if salida:
        with open(salida, "w", encoding="utf-8") as f:
            f.write(texto)
    else:
        print(texto)


def _escribir_bytes(data: bytes, salida: str | None) -> None:
    if not salida:
        print("--formato pdf requiere --salida (ruta del archivo).")
        sys.exit(2)
    with open(salida, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
