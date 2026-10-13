"""Tests del benchmark de tesis reales (`scripts/benchmark_tesis.py`).

Usan el DOCX "bueno" del factory (determinista, sin depender de tesis
reales). El motor de producción se consulta igual que en el script.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from docx_factory import compilar_docx, configuracion_base

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "benchmark_tesis.py"
REGLAS = RAIZ / "reglas_unt.yaml"


def _cargar_benchmark():
    spec = importlib.util.spec_from_file_location("benchmark_tesis", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _escribir_docx_bueno(destino: Path) -> Path:
    fuente = Path(compilar_docx(configuracion_base()))
    destino.write_bytes(fuente.read_bytes())
    return destino


def test_evaluar_corpus_agrega_por_regla(tmp_path):
    benchmark = _cargar_benchmark()

    docx = _escribir_docx_bueno(tmp_path / "tesis.docx")
    medicion = benchmark.evaluar(tmp_path, REGLAS)

    assert medicion["total_documentos"] == 1
    assert medicion["documentos"] == [
        {
            "documento": docx.name,
            "semaforo": "verde",
            "fallidos_error": 0,
            "fallidos_warning": 0,
            "evaluadas": 43,
        }
    ]
    assert medicion["por_regla"], "debe haber reglas evaluadas"
    assert all(c["falla"] == 0 for c in medicion["por_regla"].values())


def test_script_cli_con_json(tmp_path):
    _escribir_docx_bueno(tmp_path / "tesis.docx")
    salida = tmp_path / "medicion.json"

    resultado = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "--json", str(salida)],
        capture_output=True,
        text=True,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert "Por documento" in resultado.stdout
    medicion = json.loads(salida.read_text(encoding="utf-8"))
    assert medicion["total_documentos"] == 1
    assert medicion["documentos"][0]["semaforo"] == "verde"
