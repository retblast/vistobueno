"""Genera la especificación OpenAPI 3.x de VistoBueno a partir de la app FastAPI.

Extrae el esquema OpenAPI generado por FastAPI y lo escribe en
docs/openapi_spec.json.

Uso:
    python scripts/generate_openapi.py
    python scripts/generate_openapi.py --output docs/openapi_spec.json
    python scripts/generate_openapi.py --check   # CI: falla si hay drift
"""

import argparse
import json
import sys
from pathlib import Path

# Agregar la raíz del proyecto al path para que el import de validator funcione
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from validator.api import app  # noqa: E402 (orquestado tras el sys.path insert)

# Ruta de salida por defecto, anclada a la raíz del proyecto (independiente
# del directorio desde el que se invoque el script).
_DEFAULT_OUTPUT = _PROJECT_ROOT / "docs" / "openapi_spec.json"


def _resolver_ruta(valor: str) -> Path:
    """Resuelve la ruta de salida: relativa a la raíz del proyecto."""
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else _PROJECT_ROOT / ruta


def main():
    parser = argparse.ArgumentParser(description="Generar especificación OpenAPI de VistoBueno")
    parser.add_argument(
        "--output",
        default=str(_DEFAULT_OUTPUT),
        help=("Ruta de salida (default: docs/openapi_spec.json, relativa a la raíz del proyecto)"),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="No escribe: falla (exit 1) si el archivo en disco difiere del generado",
    )
    args = parser.parse_args()

    salida = _resolver_ruta(args.output)
    schema = app.openapi()
    contenido = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        if not salida.exists():
            print(f"ERROR: {salida} no existe. Ejecuta: python3 scripts/generate_openapi.py")
            sys.exit(1)
        if salida.read_text(encoding="utf-8") != contenido:
            print(
                f"ERROR: {salida} está desactualizada respecto a la app. "
                "Ejecuta: python3 scripts/generate_openapi.py"
            )
            sys.exit(1)
        print(f"OK: {salida} está en sync con la app")
        return

    with open(salida, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"OpenAPI spec generada: {salida}")
    print(f"  Versión: {schema['info']['version']}")
    print(f"  Endpoints: {len(schema['paths'])}")


if __name__ == "__main__":
    main()
