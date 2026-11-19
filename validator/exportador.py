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

import json
import re
import sys
from pathlib import Path

import markdown

# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

_EMOJIS = {"rojo": "🔴", "verde": "🟢"}

_ESCAPES_MD = {"&": "&amp;", "<": "&lt;", ">": "&gt;", "|": "&#124;"}

# Además del HTML y el pipe, el texto del documento puede contener sintaxis
# Markdown activa (imágenes, enlaces, énfasis, código). Si se cuela en el
# Markdown, el PDF la interpreta y puede intentar cargar un recurso — VA-12.
# La virgulilla (`~`) no se escapa: sin la extensión de tachado, Python-Markdown
# la deja literal, y escaparla imprimía una barra invertida visible («rango
# \~2,5 cm») — revisión #113.
_ESCAPES_TEXTO = {
    **_ESCAPES_MD,
    "\\": "\\\\",
    "`": "\\`",
    "*": "\\*",
    "_": "\\_",
    "[": "\\[",
    "]": "\\]",
    "(": "\\(",
    ")": "\\)",
    "!": "\\!",
    "#": "\\#",
}


def _escapar(texto: object) -> str:
    """Escapa identificadores que van dentro de un `code span`.

    Solo neutraliza HTML y el pipe: un backslash no escapa dentro de un
    `code span`, así que los identificadores (con `_`) se dejan intactos.
    """
    return "".join(_ESCAPES_MD.get(c, c) for c in str(texto))


def _escapar_texto(texto: object) -> str:
    """Escapa el texto que viene del documento antes de meterlo en Markdown.

    El detalle de las reglas incluye texto del DOCX del estudiante (por
    ejemplo, el nombre de la carátula que incumplió un patrón) y ese texto
    no puede romper la tabla, inyectar HTML crudo ni crear imágenes o
    enlaces activos en el Markdown (ni en el PDF, que se genera a partir de
    este Markdown) — AUD-15 y VA-12.
    """
    return "".join(_ESCAPES_TEXTO.get(c, c) for c in str(texto))


def _bloque_codigo(texto: str) -> list[str]:
    """Devuelve un bloque de código cuya cerca no pueda cerrar el texto.

    La cerca es más larga que cualquier racha de backticks del contenido, así
    que un prompt no puede terminar el bloque y convertirse en Markdown — VA-12.
    """
    mayor = max((len(m) for m in re.findall(r"`+", texto)), default=0)
    cerca = "`" * max(3, mayor + 1)
    return [cerca, texto, cerca]


def reporte_a_markdown(reporte: dict) -> str:
    """Convierte el dict del reporte a texto Markdown."""
    semaforo = reporte["semaforo"]
    resumen = reporte["resumen"]
    evaluadas = resumen.get("total_evaluadas", resumen["total"])
    no_aplicables = resumen.get("reglas_no_aplicables", 0)
    lineas: list[str] = [
        "# Reporte de validación de formato — UNT FECyC",
        "",
        f"**Semáforo:** {_EMOJIS.get(semaforo, '')} **{semaforo.upper()}**",
        "",
        "## Resumen",
        "",
        f"- Reglas evaluadas: **{evaluadas}** de **{resumen['total']}**",
        f"- No aplicables: **{no_aplicables}**",
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
        linea = (
            f"| `{_escapar(r['rule_id'])}` | {estado} | "
            f"`{_escapar(r['severity'])}` | {_escapar_texto(r['message'])} |"
        )
        lineas.append(linea)

    lineas += ["", "### Detalle de reglas fallidas", ""]
    for r in reporte["resultados"]:
        if r["passed"]:
            continue
        lineas += [
            f"#### `{_escapar(r['rule_id'])}` — {_escapar_texto(r['message'])}",
            "",
            f"- **Esperado:** {_escapar_texto(r['expected'])}",
            f"- **Encontrado:** {_escapar_texto(r['found'])}",
        ]
        if r.get("location"):
            lineas.append(f"- **Ubicación:** {_escapar_texto(r['location'])}")
        if r.get("fuente"):
            lineas.append(f"- **Fuente:** {_escapar_texto(r['fuente'])}")
        if r.get("cita"):
            lineas.append(f"- **Cita:** {_escapar_texto(r['cita'])}")
        lineas.append("")

    if reporte.get("como_preguntar_a_una_ia"):
        lineas += ["## Cómo preguntar a una IA", ""]
        for p in reporte["como_preguntar_a_una_ia"]:
            lineas += [
                f"### `{_escapar(p['rule_id'])}`",
                "",
                *_bloque_codigo(p["prompt"]),
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


def _crear_fetcher_restringido():
    """Devuelve un fetcher de WeasyPrint que solo acepta `data:`.

    El reporte no trae recursos externos: el CSS va en línea. Cualquier
    `file://`, `http(s)://` u otro esquema que aparezca en el HTML es una
    inyección y se rechaza. WeasyPrint convierte el rechazo en un aviso y
    omite el recurso, así que el PDF se genera igual — VA-12.
    """
    from weasyprint.urls import URLFetcher

    class _FetcherRestringido(URLFetcher):
        def fetch(self, url, headers=None):
            esquema = str(url).split(":", 1)[0].lower()
            if esquema != "data":
                raise ValueError(f"recurso no permitido en el PDF: {url}")
            return super().fetch(url, headers=headers)

    return _FetcherRestringido()


def reporte_a_pdf(reporte: dict) -> bytes:
    """Convierte el dict del reporte a PDF (como bytes).

    WeasyPrint se importa aquí (lazy) para que los flujos Markdown/JSON no
    arrastren la dependencia pesada (ver revisión técnica PR #28).
    """
    from weasyprint import HTML

    markdown_txt = reporte_a_markdown(reporte)
    html_txt = markdown.markdown(markdown_txt, extensions=["tables", "fenced_code", "toc"])
    styled = f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>{html_txt}</body></html>"
    return HTML(string=styled, url_fetcher=_crear_fetcher_restringido()).write_pdf()


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
