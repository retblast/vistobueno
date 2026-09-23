"""Generador de DOCXs sintéticos de tamaño controlado para tests.

Proporciona build_large_docx() para crear archivos DOCX válidos de
tamaño aproximado, útil para probar límites de validación de entrada.

Uso:
    from _docx_generator import build_large_docx

    contenido = build_large_docx(target_bytes=10 * 1024 * 1024)
"""

import io
import random
import zipfile

from docx import Document


def build_large_docx(target_bytes, seed=42):
    """Genera un DOCX válido de tamaño aproximado a target_bytes.

    Crea un DOCX mínimo con python-docx y lo rellena con bytes aleatorios
    (no comprimibles) usando un archivo dummy dentro del ZIP.

    Args:
        target_bytes: Tamaño objetivo en bytes.
        seed: Semilla para el generador de números aleatorios.

    Returns:
        bytes: Contenido del DOCX generado.
    """
    doc = Document()
    doc.add_paragraph("Documento de prueba para validación de tamaño")
    buf_base = io.BytesIO()
    doc.save(buf_base)

    contenido_base = buf_base.getvalue()
    # Reservar ~4 KB para overhead de headers del ZIP
    padding_necesario = target_bytes - len(contenido_base) - 4096

    if padding_necesario <= 0:
        buf_base.seek(0)
        return buf_base.read()

    # Instancia local: no tocar el RNG global para no afectar otros tests
    # que compartan intérprete. randbytes() es CPython-nativo (~17x más
    # rápido que un loop de getrandbits(8) para MBs de padding).
    rng = random.Random(seed)
    padding = rng.randbytes(padding_necesario)

    resultado = io.BytesIO()
    buf_base.seek(0)
    with zipfile.ZipFile(buf_base, "r") as zin:
        with zipfile.ZipFile(resultado, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            zout.writestr("dummy/padding.bin", padding)

    resultado.seek(0)
    return resultado.read()
