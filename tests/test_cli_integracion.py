"""Tests de integración de la CLI (--formato / --salida / --severity).

Cubre el aviso de la revisión técnica PR #28: los modos `--formato` del CLI
no tenían tests de integración. Genera un DOCX real con el factory y evalúa
contra `reglas_unt.yaml`.

Uso:
    pytest tests/test_cli_integracion.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from docx_factory import compilar_docx, configuracion_base

from validator import cli

RAIZ = Path(__file__).resolve().parent.parent
YAML = RAIZ / "reglas_unt.yaml"


@pytest.fixture(scope="module")
def docx() -> str:
    return compilar_docx(configuracion_base())


def _correr(argv: list, monkeypatch, capsys):
    """Ejecuta cli.main() con argv simulado; devuelve (exit_code, captured)."""
    monkeypatch.setattr(sys, "argv", ["validator.cli"] + argv)
    try:
        cli.main()
    except SystemExit as exc:
        return exc.code, capsys.readouterr()
    return None, capsys.readouterr()


def _json_reporte(captured) -> dict:
    return json.loads(captured.out)


def test_cli_json_stdout(docx, monkeypatch, capsys):
    code, captured = _correr([docx, str(YAML), "--formato", "json"], monkeypatch, capsys)
    assert code is None
    reporte = _json_reporte(captured)
    assert reporte["semaforo"] in {"verde", "rojo"}
    assert {"total", "fallidos_error", "fallidos_warning"} <= set(reporte["resumen"])
    assert "como_preguntar_a_una_ia" in reporte


def test_cli_json_atajo(docx, monkeypatch, capsys):
    # --json es un atajo de --formato json (compatibilidad).
    code, captured = _correr([docx, str(YAML), "--json"], monkeypatch, capsys)
    assert code is None
    assert _json_reporte(captured)["semaforo"] in {"verde", "rojo"}


def test_cli_markdown_salida(docx, monkeypatch, capsys, tmp_path: Path):
    salida = tmp_path / "reporte.md"
    code, _ = _correr(
        [docx, str(YAML), "--formato", "markdown", "--salida", str(salida)],
        monkeypatch,
        capsys,
    )
    assert code is None
    texto = salida.read_text(encoding="utf-8")
    assert texto.startswith("# Reporte de validación")


def test_cli_pdf_salida(docx, monkeypatch, capsys, tmp_path: Path):
    salida = tmp_path / "reporte.pdf"
    code, _ = _correr(
        [docx, str(YAML), "--formato", "pdf", "--salida", str(salida)],
        monkeypatch,
        capsys,
    )
    assert code is None
    data = salida.read_bytes()
    assert len(data) > 500
    assert data[:4] == b"%PDF"


def test_cli_pdf_requiere_salida(docx, monkeypatch, capsys):
    code, captured = _correr([docx, str(YAML), "--formato", "pdf"], monkeypatch, capsys)
    assert code == 2
    assert "requiere --salida" in captured.out


def test_cli_severity_filtra_resultados(docx, monkeypatch, capsys):
    code, captured = _correr(
        [docx, str(YAML), "--severity", "error", "--formato", "json"],
        monkeypatch,
        capsys,
    )
    assert code is None
    reporte = _json_reporte(captured)
    assert all(r["severity"] == "error" for r in reporte["resultados"])


def test_cli_texto_distingue_evaluadas_de_no_aplicables(docx, monkeypatch, capsys):
    """VA-18: el modo texto no presenta las 50 reglas como evaluadas."""
    code, captured = _correr([docx, str(YAML)], monkeypatch, capsys)
    assert code is None
    assert "Reglas evaluadas: 44 de 50" in captured.out
    assert "No aplicables: 6" in captured.out
    assert "Total reglas evaluadas: 50" not in captured.out
