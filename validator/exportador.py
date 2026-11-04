"""Exportación del reporte de validación a Markdown y PDF.

Convierte el dict del reporte (producido por `engine.build_report`) a una
versión legible para la bitácora/entrega:
- `reporte_a_markdown`: texto Markdown con semáforo, resumen y tabla de
  resultados (incluye la sección "cómo preguntar a una IA" si el reporte
  la trae).
- `reporte_a_pdf`: Markdown -> HTML -> PDF vía WeasyPrint. Se eligió
  WeasyPrint por calidad de render (estilos CSS reales, tablas y acentos
  correctos) frente a alternativas como reportlab o pymupdf.Story.

Uso:
    python -m validator.exportador reporte.json salida.md
    python -m validator.exportador reporte.json salida.pdf
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import markdown

# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

_EMOJIS = {"rojo": "🔴", "verde": "🟢"}


def reporte_a_markdown(reporte: dict) -> str:
    """Convierte el dict del reporte a texto Markdown."""
    semaforo = reporte["semaforo"]
    resumen = reporte["resumen"]
    lineas: list[str] = [
        "# Reporte de validación de formato — UNT FECyC",
        "",
        f"**Semáforo:** {_EMOJIS.get(semaforo, '')} **{semaforo.upper()}**",
        "",
        "## Resumen",
        "",
        f"- Total de reglas evaluadas: **{resumen['total']}**",
        f"- Fallidas (error): **{resumen['fallidos_error']}**",
        f"- Fallidas (warning): **{resumen['fallidos_warning']}**",
        "",
        "## Resultados",
        "",
        "| Regla | Estado | Severidad | Resultado |",
        "|-------|--------|-----------|-----------|",
    ]

    for r in reporte["resultados"]:
        estado = "✅ cumple" if r["passed"] else "❌ **falla**"
        linea = f"| `{r['rule_id']}` | {estado} | `{r['severity']}` | {html.escape(r['message'])} |"
        lineas.append(linea)

    lineas += ["", "### Detalle de reglas fallidas", ""]
    for r in reporte["resultados"]:
        if r["passed"]:
            continue
        lineas += [
            f"#### `{r['rule_id']}` — {html.escape(r['message'])}",
            "",
            f"- **Esperado:** {html.escape(r['expected'])}",
            f"- **Encontrado:** {html.escape(r['found'])}",
        ]
        if r.get("location"):
            lineas.append(f"- **Ubicación:** {r['location']}")
        if r.get("fuente"):
            lineas.append(f"- **Fuente:** {r['fuente']}")
        if r.get("cita"):
            lineas.append(f"- **Cita:** {r['cita']}")
        lineas.append("")

    if reporte.get("como_preguntar_a_una_ia"):
        lineas += ["## Cómo preguntar a una IA", ""]
        for p in reporte["como_preguntar_a_una_ia"]:
            lineas += [
                f"### `{p['rule_id']}`",
                "",
                "```",
                html.escape(p["prompt"]),
                "```",
                "",
            ]

    return "\n".join(lineas).strip() + "\n"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: sans-serif; font-size: 10pt; line-height: 1.4; }
h1 { color: #1a3c6e; border-bottom: 2px solid #1a3c6e; }
h2 { color: #1a3c6e; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #ccc; padding: 4px 6px; text-align: left; }
th { background-color: #eef2f7; }
code { background-color: #f4f4f4; padding: 0 2px; }
pre, blockquote { background-color: #f8f8f8; padding: 8px; }
"""


def reporte_a_pdf(reporte: dict) -> bytes:
    """Convierte el dict del reporte a PDF (como bytes).

    WeasyPrint se importa aquí (lazy) para que los flujos Markdown/JSON no
    arrastren la dependencia pesada (ver revisión técnica PR #28).
    """
    from weasyprint import HTML

    markdown_txt = reporte_a_markdown(reporte)
    html_txt = markdown.markdown(markdown_txt, extensions=["tables", "fenced_code", "toc"])
    styled = f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>{html_txt}</body></html>"
    return HTML(string=styled).write_pdf()


def _main() -> None:
    """CLI utilitaria: python -m validator.exportador reporte.json salida.md|pdf"""
    if len(sys.argv) != 3:
        print("Uso: python -m validator.exportador reporte.json salida{.md|.pdf}")
        sys.exit(2)
    reporte_path, out_path = sys.argv[1], sys.argv[2]
    reporte = json.loads(Path(reporte_path).read_text(encoding="utf-8"))
    ext = Path(out_path).suffix.lower()
    if ext == ".md":
        Path(out_path).write_text(reporte_a_markdown(reporte), encoding="utf-8")
    elif ext == ".pdf":
        Path(out_path).write_bytes(reporte_a_pdf(reporte))
    else:
        print(f"Extensión no soportada: {ext} (use .md o .pdf)")
        sys.exit(2)
    print(f"Reporte exportado a {out_path}")


if __name__ == "__main__":
    _main()
