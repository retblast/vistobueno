#!/usr/bin/env python3
"""Corre el motor de reglas contra todos los .docx de un directorio.

Reemplaza al prototipo eval_checks2.py: misma idea (evaluar reglas
mecanizadas contra un lote de plantillas), pero reusando el motor de
producción en validator/ en vez de lógica standalone, y sin rutas
hardcodeadas.

Uso:
    python scripts/eval_contra_plantillas.py unt_format_rules_schema.yaml ruta/a/plantillas/
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validator.engine import load_rules, validate_docx  # noqa: E402


def _reglas_de(datos: dict) -> list[dict]:
    """Lista de reglas de un YAML cargado, en cualquiera de los dos formatos.

    `load_rules` devuelve `{"reglas": [...]}` para el DSL actual y
    `{"rules": [...]}` para los YAML legacy. El script debe servir con
    ambos (F-6 del plan de la semana 11); antes solo leía `rules` y
    reventaba con `KeyError` al apuntarlo a `reglas_ficha.yaml`.
    """
    for clave in ("reglas", "rules"):
        reglas = datos.get(clave)
        if isinstance(reglas, list):
            return reglas
    raise ValueError("El YAML no trae una lista de reglas ('reglas' ni 'rules')")


def _total_mecanizadas(datos: dict) -> int:
    """Cuántas reglas del ruleset tienen mecanismo verificable.

    En el DSL toda regla es verificable; en el formato legacy solo las que
    declaran `mecanismo_verificable`.
    """
    reglas = _reglas_de(datos)
    if "reglas" in datos:
        return len(reglas)
    return sum(1 for r in reglas if "mecanismo_verificable" in r)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rules", help="Ruta al YAML de reglas")
    parser.add_argument("carpeta", help="Carpeta con archivos .docx a evaluar")
    args = parser.parse_args()

    rules_data = load_rules(args.rules)
    total_mecanizadas = _total_mecanizadas(rules_data)

    docs = sorted(Path(args.carpeta).glob("*.docx"))
    if not docs:
        print(f"No se encontraron .docx en {args.carpeta}")
        return

    for docx_path in docs:
        resultados = validate_docx(str(docx_path), rules_data)
        fallidos = [r for r in resultados if not r.passed]
        print(
            f"== {docx_path.name[:60]}  "
            f"({len(resultados) - len(fallidos)}/{len(resultados)} PASS "
            f"de {total_mecanizadas} mecanizadas)"
        )
        for r in fallidos:
            print(f"   FAIL[{r.severity.value}] {r.rule_id}: {r.found[:118]}")


if __name__ == "__main__":
    main()
