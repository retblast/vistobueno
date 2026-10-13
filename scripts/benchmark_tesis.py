#!/usr/bin/env python3
"""Benchmark del motor de reglas sobre una carpeta de tesis reales (.docx).

Corre el motor de producción (`validator/`) sobre documentos reales y reporta:

- por documento: semáforo y conteo de fallos (`error`/`warning`);
- agregado por regla: en cuántos documentos pasa y en cuántos falla
  ("reglas que pasan en la práctica").

No calcula precisión automática: sin etiquetas humanas no hay verdaderos
positivos/negativos. Para acercarse a eso, lista los fallos por documento
para su revisión manual.

Uso:
    python scripts/benchmark_tesis.py recursos/tesis/
    python scripts/benchmark_tesis.py recursos/tesis/ --json medicion.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validator.engine import build_report, load_rules, validate_docx  # noqa: E402
from validator.models import RULES_CENTINELA  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def evaluar(carpeta: Path, reglas: Path) -> dict:
    """Corre el motor sobre los `.docx` de la carpeta y devuelve la medición."""
    rules_data = load_rules(str(reglas))
    docs = sorted(carpeta.glob("*.docx"))

    por_doc = []
    por_regla: dict[str, dict[str, int]] = defaultdict(
        lambda: {"pasa": 0, "falla": 0, "error": 0, "warning": 0}
    )

    for docx in docs:
        resultados = validate_docx(str(docx), rules_data)
        reporte = build_report(resultados)
        por_doc.append(
            {
                "documento": docx.name,
                "semaforo": reporte["semaforo"],
                "fallidos_error": reporte["resumen"]["fallidos_error"],
                "fallidos_warning": reporte["resumen"]["fallidos_warning"],
                "evaluadas": reporte["resumen"]["total_evaluadas"],
            }
        )
        for r in resultados:
            if r.rule_id in RULES_CENTINELA or not r.aplicable:
                continue
            if r.passed:
                por_regla[r.rule_id]["pasa"] += 1
            else:
                por_regla[r.rule_id]["falla"] += 1
                por_regla[r.rule_id][r.severity.value] += 1

    return {
        "reglas": str(reglas),
        "carpeta": str(carpeta),
        "total_documentos": len(docs),
        "documentos": por_doc,
        "por_regla": dict(sorted(por_regla.items())),
    }


def imprimir(medicion: dict) -> None:
    print(f"Corpus: {medicion['carpeta']}  ({medicion['total_documentos']} documento(s))")

    print("\n== Por documento ==")
    for d in medicion["documentos"]:
        print(
            f"  [{d['semaforo']:5}] {d['documento'][:56]:56}  "
            f"error={d['fallidos_error']} warning={d['fallidos_warning']} "
            f"evaluadas={d['evaluadas']}"
        )

    print("\n== Por regla (pasa / total) ==")
    for regla, c in medicion["por_regla"].items():
        total = c["pasa"] + c["falla"]
        marca = "OK" if c["falla"] == 0 else "  "
        print(f"  {marca} {regla:48} {c['pasa']}/{total}  (err={c['error']} warn={c['warning']})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("carpeta", help="Carpeta con tesis .docx")
    parser.add_argument("--reglas", default=str(RAIZ / "reglas_unt.yaml"), help="YAML de reglas")
    parser.add_argument("--json", metavar="RUTA", help="Volcar la medición en JSON")
    args = parser.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        print(f"No existe la carpeta: {carpeta}", file=sys.stderr)
        return 1

    medicion = evaluar(carpeta, Path(args.reglas))
    if medicion["total_documentos"] == 0:
        print(f"No se encontraron .docx en {carpeta}", file=sys.stderr)
        return 1

    imprimir(medicion)
    if args.json:
        Path(args.json).write_text(
            json.dumps(medicion, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nMedición guardada en {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
