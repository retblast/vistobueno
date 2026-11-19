"""Tests del exportador de reportes a Markdown y PDF (tarea 16).

Verifica que:
- `reporte_a_markdown` produzca encabezados, resumen y tabla con las reglas;
- el detalle de reglas fallidas aparezca (esperado/encontrado);
- `reporte_a_pdf` devuelva bytes de PDF válido (%PDF) no vacíos;
- `_main` exporte correctamente a .md y .pdf desde un JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import markdown
import pytest

from validator.exportador import _main, reporte_a_markdown, reporte_a_pdf

REPORTE: dict[str, Any] = {
    "semaforo": "rojo",
    "resultados": [
        {
            "rule_id": "papel_tamano",
            "passed": True,
            "severity": "error",
            "message": "El tamaño del papel debe ser A4",
            "expected": "210 x 297 mm",
            "found": "cumple",
            "location": 'Sección "Formato general"',
            "fuente": "MANUAL.docx",
            "cita": '"Tamaño A4"',
        },
        {
            "rule_id": "margen_superior",
            "passed": False,
            "severity": "error",
            "message": "El margen superior debe ser 2,5 cm",
            "expected": "2,5 cm",
            "found": "1,5 cm",
            "location": 'Sección "Formato general"',
            "fuente": "MANUAL.docx",
            "cita": '"Margen superior 2,5 cm"',
        },
    ],
    "resumen": {
        "total": 42,
        "total_evaluadas": 40,
        "reglas_no_aplicables": 2,
        "fallidos_error": 1,
        "fallidos_warning": 0,
    },
    "como_preguntar_a_una_ia": [
        {"rule_id": "margen_superior", "prompt": "¿Cómo corrijo el margen superior?"}
    ],
}


def test_markdown_contiene_semaforo_resumen_y_tabla():
    md = reporte_a_markdown(REPORTE)
    assert "# Reporte de validación" in md
    assert "ROJO" in md
    assert "Reglas evaluadas: **40** de **42**" in md
    assert "No aplicables: **2**" in md
    assert "`papel_tamano`" in md
    assert "`margen_superior`" in md
    assert "✅ cumple" in md
    assert "❌ **falla**" in md


def test_markdown_no_presenta_las_omitidas_como_evaluadas():
    """VA-18: las reglas que no se miraron no cuentan como evaluadas."""
    md = reporte_a_markdown(REPORTE)
    assert "Total de reglas evaluadas: **42**" not in md


def test_markdown_acepta_reportes_antiguos_sin_total_evaluadas():
    """VA-18: los reportes guardados antes del cambio siguen exportándose."""
    reporte = {
        **REPORTE,
        "resumen": {"total": 42, "fallidos_error": 1, "fallidos_warning": 0},
    }
    md = reporte_a_markdown(reporte)
    assert "Reglas evaluadas: **42** de **42**" in md
    assert "No aplicables: **0**" in md
    assert "Total de reglas evaluadas" not in md


def test_markdown_detalla_reglas_fallidas():
    md = reporte_a_markdown(REPORTE)
    assert "## Detalle de reglas fallidas" in md
    assert "**Esperado:** 2,5 cm" in md
    assert "**Encontrado:** 1,5 cm" in md
    assert '**Ubicación:** Sección "Formato general"' in md


def test_markdown_incluye_prompt_ia():
    md = reporte_a_markdown(REPORTE)
    assert "## Cómo preguntar a una IA" in md
    assert "¿Cómo corrijo el margen superior?" in md


def test_markdown_escapa_el_texto_que_viene_del_documento():
    """AUD-15: el texto del DOCX no puede romper la tabla ni injectar HTML."""
    reporte = {
        **REPORTE,
        "resultados": [
            {
                "rule_id": "caratula_autores_mayusculas",
                "passed": False,
                "severity": "error",
                "message": "Los autores <b>deben</b> ir en mayúsculas",
                "expected": "Mayúsculas y minúsculas",
                "found": "@w:val=['<b>ana</b> | maría'] 1 incumplen: #1=<b>ana</b>",
                "location": "Carátula | fila 2",
                "fuente": "MANUAL.docx",
                "cita": '"Autores"',
            }
        ],
    }
    md = reporte_a_markdown(reporte)
    assert "<b>" not in md
    assert "&lt;b&gt;" in md
    assert "&#124;" in md, "el pipe rompe la tabla si no se escapa"
    # La tabla sigue siendo una tabla: el pipe escapado no la parte en dos.
    assert "| Regla | Estado | Severidad | Resultado |" in md
    assert md.count("| `caratula_autores_mayusculas` |") == 1


def test_pdf_devuelve_bytes_validos():
    pdf = reporte_a_pdf(REPORTE)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 500
    assert pdf[:4] == b"%PDF"


REPORTE_CON_RECURSOS = {
    **REPORTE,
    "resultados": [
        {
            **REPORTE["resultados"][1],
            "message": "Carátula con ![logo](file:///etc/passwd) y [sitio](http://ejemplo.test/x)",
            "found": '<img src="file:///etc/shadow"> y `código`',
        }
    ],
}


def test_markdown_neutraliza_imagenes_y_enlaces_del_documento():
    """VA-12: el texto del DOCX no puede crear imágenes ni enlaces activos."""
    md = reporte_a_markdown(REPORTE_CON_RECURSOS)
    assert "![logo](file:///etc/passwd)" not in md
    assert "[sitio](http://ejemplo.test/x)" not in md
    assert "\\!\\[logo\\]" in md
    assert "&lt;img src=" in md
    assert "<img" not in md


def test_markdown_no_escapa_la_virgulilla():
    """Revisión #113: `\\~` se renderizaba con una barra invertida visible.

    La virgulilla no es sintaxis activa sin la extensión de tachado, así que
    escaparla solo ensuciaba el texto («rango \\~2,5 cm»).
    """
    reporte = {
        **REPORTE,
        "resultados": [
            {
                **REPORTE["resultados"][1],
                "message": "El margen ronda ~2,5 cm",
                "found": "rango ~2,5 cm",
            }
        ],
    }
    md = reporte_a_markdown(reporte)
    assert "\\~" not in md
    assert "~2,5 cm" in md
    html = markdown.markdown(md, extensions=["tables", "fenced_code", "toc"])
    assert "\\~" not in html
    assert "~2,5 cm" in html


def test_prompt_con_backticks_no_cierra_el_bloque_de_codigo():
    """VA-12: un prompt no puede escapar de su bloque y volverse Markdown."""
    reporte = {
        **REPORTE,
        "como_preguntar_a_una_ia": [
            {
                "rule_id": "margen_superior",
                "prompt": "antes\n```\nfuga\n```\ndespués",
            }
        ],
    }
    md = reporte_a_markdown(reporte)
    assert "````" in md

    html = markdown.markdown(md, extensions=["tables", "fenced_code"])
    assert html.count("<pre>") == 1
    assert "fuga" in html


def test_fetcher_restringido_rechaza_recursos_externos():
    """VA-12: solo se permite `data:`; ni archivos locales ni red."""
    from validator.exportador import _crear_fetcher_restringido

    fetcher = _crear_fetcher_restringido()
    for url in (
        "file:///etc/passwd",
        "http://ejemplo.test/logo.png",
        "https://ejemplo.test/logo.png",
        "ftp://ejemplo.test/logo.png",
    ):
        with pytest.raises(ValueError):
            fetcher.fetch(url)
    respuesta = fetcher.fetch("data:text/plain,hola")
    assert b"hola" in respuesta.read()


def _fetcher_espia(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
    """Envuelve el fetcher restringido para registrar intentos y rechazos.

    WeasyPrint invoca el fetcher con `__call__` (no con `fetch`), así que el
    espía implementa `__call__` y delega en el fetcher real, que rechaza todo
    lo que no sea `data:`.
    """
    from validator import exportador

    restringido = exportador._crear_fetcher_restringido()
    intentos: list[str] = []
    rechazados: list[str] = []

    class _Espia:
        def __call__(self, url, headers=None):
            intentos.append(str(url))
            try:
                return restringido.fetch(str(url), headers=headers)
            except ValueError:
                rechazados.append(str(url))
                raise

    monkeypatch.setattr(exportador, "_crear_fetcher_restringido", lambda: _Espia())
    return intentos, rechazados


def test_pdf_no_abre_recursos_externos(monkeypatch):
    """VA-12 (ruta normal): el Markdown hostil ya viene escapado.

    El espía va sobre la capa del fetcher (donde WeasyPrint sí llama), de modo
    que el test falla si el escapado deja pasar una imagen o un enlace.
    """
    intentos, rechazados = _fetcher_espia(monkeypatch)
    pdf = reporte_a_pdf(REPORTE_CON_RECURSOS)
    assert pdf[:4] == b"%PDF"
    assert [u for u in intentos if not u.startswith("data:")] == []
    assert rechazados == []


def test_pdf_rechaza_recursos_externos_sin_escapar(monkeypatch):
    """VA-12 (capa del fetcher): aunque el Markdown ya venga hostil, se corta.

    Se salta `_escapar_texto` monkeypatcheando `reporte_a_markdown` para que el
    HTML llegue con `<img>` y enlaces activos; el fetcher restringido debe
    rechazar `file://` y `http://`, y el PDF se genera igual.
    """
    from validator import exportador

    hostil = "# Reporte\n\n![x](file:///etc/passwd)\n\n<img src='http://ejemplo.test/x.png'>\n"
    monkeypatch.setattr(exportador, "reporte_a_markdown", lambda _reporte: hostil)
    intentos, rechazados = _fetcher_espia(monkeypatch)

    pdf = exportador.reporte_a_pdf(REPORTE)
    assert pdf[:4] == b"%PDF"
    externos = [u for u in intentos if not u.startswith("data:")]
    assert externos, "WeasyPrint debió intentar cargar el recurso inyectado"
    assert set(externos) == set(rechazados)
    assert any(u.startswith("file:") for u in externos)
    assert any(u.startswith("http:") for u in externos)


def test_main_exporta_markdown_y_pdf(tmp_path: Path):
    reporte_json = tmp_path / "reporte.json"
    reporte_json.write_text(json.dumps(REPORTE, ensure_ascii=False), encoding="utf-8")
    md_out = tmp_path / "salida.md"
    sys.argv = ["exportador", str(reporte_json), str(md_out)]
    _main()
    assert "ROJO" in md_out.read_text(encoding="utf-8")

    pdf_out = tmp_path / "salida.pdf"
    sys.argv = ["exportador", str(reporte_json), str(pdf_out)]
    _main()
    assert pdf_out.read_bytes()[:4] == b"%PDF"


def test_main_rechaza_extension_desconocida(tmp_path: Path, capsys: pytest.CaptureFixture):
    reporte_json = tmp_path / "reporte.json"
    reporte_json.write_text(json.dumps(REPORTE), encoding="utf-8")
    sys.argv = ["exportador", str(reporte_json), str(tmp_path / "salida.txt")]
    with pytest.raises(SystemExit) as exc:
        _main()
    assert exc.value.code == 2
    assert "no soportada" in capsys.readouterr().out
