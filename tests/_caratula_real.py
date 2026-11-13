"""Carátula de tesis con la **estructura real** (auditoría 2026-10-26).

Este módulo construye el DOCX mínimo que reproduce la estructura real de
la carátula de una tesis de la UNT:

- la etiqueta `AUTORES:` va en su **propio párrafo** y cada autor en un
  párrafo aparte, con la línea de ORCID intercalada;
- la etiqueta `ASESORA:` va en su propio párrafo y el nombre en el
  siguiente;
- el título termina en ", Trujillo <año>" y la portada cierra con la
  línea de ciudad y el año en párrafos separados;
- las palabras clave están en el RESUMEN, no en la carátula.

Los nombres son **placeholders**: ningún dato real de una tesis entra al
repositorio.

Uso:
    from _caratula_real import capturar_ficha, crear_docx_caratula
"""

import tempfile
from pathlib import Path

from docx import Document

from validator.engine import build_report, load_ficha_rules, load_rules, validate_docx

RAIZ = Path(__file__).resolve().parent.parent
REGLAS_YAML = RAIZ / "reglas_unt.yaml"
REGLAS_FICHA_YAML = RAIZ / "reglas_ficha.yaml"

# --- Contenido de la carátula (placeholders, estructura real) -------------

PORTADA = [
    "UNIVERSIDAD NACIONAL DE TRUJILLO",
    "FACULTAD DE EDUCACIÓN Y CIENCIAS DE LA COMUNICACIÓN",
    "ESCUELA PROFESIONAL DE EDUCACIÓN PRIMARIA",
    "Título del trabajo de investigación: Estrategias lúdicas para mejorar "
    "la identidad cultural en estudiantes de primaria de una institución "
    "educativa, Trujillo 2024",
    "TESIS",
    "Para Optar el Título Profesional de Licenciado en Educación Primaria",
    "AUTORES:",
    "Br. Apellido, Nombre",
    "https://orcid.org/0000-0000-0000-0000",
    "Br. Apellido2, Nombre2",
    "https://orcid.org/0000-0000-0000-0001",
    "ASESORA:",
    "Dra. Apellido, Nombre",
    "https://orcid.org/0000-0000-0000-0002",
    "Línea de Investigación:",
    "Educación y Ciencias de la Comunicación y Desarrollo Sostenible",
    "Trujillo – Perú",
    "2026",
]

# --- Resumen: las palabras clave viven aquí, no en la carátula ------------

RESUMEN_TEXTO = (
    "El presente estudio analiza la relación entre las estrategias lúdicas "
    "y la identidad cultural en estudiantes de primaria."
)

PALABRAS_CLAVE = "Palabras Clave: Educación, Cultura, Identidad cultural."


def crear_docx_caratula(
    portada: list[str] | None = None,
    con_resumen: bool = True,
    referencias: list[str] | None = None,
) -> str:
    """Escribe el DOCX de la carátula real y devuelve su ruta.

    `RESUMEN` se emite como Título1 (`add_heading`) porque en los DOCX
    reales —y en `docs/ejemplos/doc_bueno.docx`— es un párrafo con estilo de
    encabezado, no un párrafo normal. Sin eso, `seccion()` no encuentra la
    sección y la captura del abstract y de las palabras clave queda vacía
    (handover `HANDOVER_PENDIENTES_2026-11-11.md` §3.3).

    Los parámetros permiten reproducir los casos límite de la revisión del
    PR #75 sin duplicar el documento: una portada alternativa, un cuerpo sin
    resumen y referencias después de un encabezado.
    """
    documento = Document()
    for linea in PORTADA if portada is None else portada:
        documento.add_paragraph(linea)
    if con_resumen:
        documento.add_heading("RESUMEN", level=1)
        documento.add_paragraph(RESUMEN_TEXTO)
        documento.add_paragraph(PALABRAS_CLAVE)
    if referencias is not None:
        documento.add_heading("REFERENCIAS", level=1)
        for linea in referencias:
            documento.add_paragraph(linea)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        ruta = tmp.name
    documento.save(ruta)
    return ruta


def capturar_ficha(ruta: str) -> dict:
    """Corre el motor y devuelve `reporte["ficha"]` de ese DOCX."""
    resultados = validate_docx(
        ruta,
        load_rules(str(REGLAS_YAML)),
        load_ficha_rules(str(REGLAS_FICHA_YAML)),
    )
    return build_report(resultados).get("ficha", {})


def valor(ficha: dict, campo: str):
    """El valor capturado de un campo de la ficha."""
    return (ficha.get(campo) or {}).get("valor")
