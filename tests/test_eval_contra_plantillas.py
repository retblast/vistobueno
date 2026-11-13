"""Tests de `scripts/eval_contra_plantillas.py` (F-6, semana 11).

El script evalúa un ruleset contra una carpeta de plantillas. Debe aceptar
los dos formatos del proyecto: el DSL actual (`reglas:`) y el legacy
(`rules:`). Antes solo leía `rules` y fallaba con `KeyError` al apuntarlo
a `reglas_ficha.yaml`.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "eval_contra_plantillas.py"


def _cargar_modulo():
    spec = importlib.util.spec_from_file_location("eval_contra_plantillas", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def script():
    return _cargar_modulo()


def test_acepta_la_clave_reglas(script):
    """El DSL actual usa `reglas`."""
    datos = {"reglas": [{"id": "ficha_titulo"}, {"id": "ficha_autores"}]}
    assert script._reglas_de(datos) == datos["reglas"]
    assert script._total_mecanizadas(datos) == 2


def test_acepta_la_clave_rules(script):
    """El formato legacy usa `rules` y solo cuenta las mecanizadas."""
    datos = {
        "rules": [
            {"id": "con_mecanismo", "mecanismo_verificable": {"checks": []}},
            {"id": "sin_mecanismo"},
        ]
    }
    assert script._reglas_de(datos) == datos["rules"]
    assert script._total_mecanizadas(datos) == 1


def test_rechaza_un_yaml_sin_reglas(script):
    """Un YAML sin ninguna de las dos claves es un error explícito."""
    with pytest.raises(ValueError, match="reglas"):
        script._reglas_de({"otra_cosa": []})


@pytest.mark.parametrize(
    "contenido",
    [
        "reglas:\n  - id: ficha_titulo\n",
        "rules:\n  - id: caratula_titulo\n",
    ],
)
def test_main_no_falla_con_ninguno_de_los_dos_formatos(
    script, tmp_path, monkeypatch, capsys, contenido
):
    """Reproduce el bug F-6: `main()` no debe lanzar `KeyError`."""
    reglas = tmp_path / "reglas.yaml"
    reglas.write_text(contenido, encoding="utf-8")
    carpeta = tmp_path / "plantillas"
    carpeta.mkdir()

    monkeypatch.setattr(sys, "argv", ["eval_contra_plantillas.py", str(reglas), str(carpeta)])
    script.main()

    assert "No se encontraron .docx" in capsys.readouterr().out
