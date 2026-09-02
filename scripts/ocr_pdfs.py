#!/usr/bin/env python3
"""Extracción de texto de los PDF de reglamentos de la UNT (RCU).

Diseño:
  - Primero intenta extraer TEXTO NATIVO de cada página con PyMuPDF.
    Los RCU tienen capa de texto real, por lo que la mayoría de páginas
    no requieren OCR.
  - Si una página tiene muy poco o nulo texto nativo (algo < umbral),
    se rasteriza a 300 DPI y se aplica Tesseract (spa+eng) vía pytesseract.
    Si tesseract no está disponible, la página se marca como "pendiente OCR".
  - Escribe un .txt por PDF en la carpeta de salida, con separador de página
    "=== PÁGINA N ===" para poder mapear fragmentos a secciones del reglamento.

Uso:
    python scripts/ocr_pdfs.py [PDF...] [-o carpeta] [--umbral N]
"""
import argparse
import shutil
from pathlib import Path

import pymupdf

DEFAULT_UMBRAL = 50  # chars de texto nativo por debajo del cual se hace OCR


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_page(page, dpi: int = 300) -> str:
    pix = page.get_pixmap(dpi=dpi)
    png = pix.tobytes("png")
    import pytesseract
    text = pytesseract.image_to_string(png, lang="spa+eng")
    return text.strip()


def extraer_pdf(pdf_path: Path, out_path: Path, umbral: int) -> dict:
    """Devuelve {paginas: N, ocr_aplicado: [.], pendientes: [.]}"""
    doc = pymupdf.open(str(pdf_path))
    uso_ocr = _tesseract_available()
    ocr_aplicado = []
    pendientes = []

    buckets = []
    for i, page in enumerate(doc):
        header = f"=== PÁGINA {i + 1} ==="
        native = (page.get_text() or "").strip()
        if len(native) < umbral:
            if uso_ocr:
                ocr_text = _ocr_page(page)
                ocr_aplicado.append(i + 1)
                bucket = f"{header}\n[OCR aplicado]\n{ocr_text}"
            else:
                pendientes.append(i + 1)
                bucket = f"{header}\n[TEXTO NO NATIVO — pendiente OCR (tesseract no disponible)]\n{native}"
        else:
            bucket = f"{header}\n{native}"
        buckets.append(bucket)

    doc.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n".join(buckets) + "\n", encoding="utf-8")

    return {
        "paginas": len(buckets),
        "ocr_aplicado": ocr_aplicado,
        "pendientes": pendientes,
    }


def main():
    parser = argparse.ArgumentParser(description="Extrae/OCR texto de PDFs RCU")
    parser.add_argument("pdfs", nargs="*", help="Rutas a PDFs (default: los dos RCU del repo)")
    parser.add_argument("-o", "--out", default="recursos/ocr", help="Carpeta de salida")
    parser.add_argument("--umbral", type=int, default=DEFAULT_UMBRAL, help="chars mínimos de texto nativo")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    pdfs = args.pdfs or [
        "RCU-N-274-2022-UNT.pdf",
        "RCU-N-220-2022-UNT-LINEAS DE INVESTIGACION.pdf",
    ]
    pdf_paths = [(Path(p) if Path(p).suffix else repo / p) for p in pdfs]
    out_dir = Path(args.out)

    tesseract = _tesseract_available()
    print(f"Tesseract disponible: {tesseract}")

    for p in pdf_paths:
        if not p.exists():
            print(f"NO ENCONTRADO: {p}")
            continue
        out = out_dir / (p.stem + ".txt")
        res = extraer_pdf(p, out, args.umbral)
        estado = []
        if res["ocr_aplicado"]:
            estado.append(f"OCR en págs {res['ocr_aplicado']}")
        if res["pendientes"]:
            estado.append(f"PENDIENTES (sin tesseract): pág {res['pendientes']}")
        print(f"OK {p.name}: {res['paginas']} págs -> {out}" + (f" | {', '.join(estado)}" if estado else " (texto nativo)"))


if __name__ == "__main__":
    main()
