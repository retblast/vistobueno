"""Tokenizer del DSL: convierte el documento en un flujo tipado de tokens.

Es el "análisis léxico" del motor (fase F2 del plan): recorre <w:body> en
orden de documento y emite tokens con tipo, texto y nivel:

    TITULO(nivel, texto)     párrafo con estilo de encabezado
                             (estilos Heading/Título; ver extractor.es_heading)
    PARRAFO(texto)           párrafo normal (sin estilo de encabezado)
    TABLA                    bloque w:tbl (incluye las celdas como PARRAFOs)
    IMAGEN                   un blip embebido (w:drawing//a:blip)
    SALTO_SECCION            w:sectPr (directo en body o anidado en pPr)

Centraliza la extracción que hoy está duplicada en AutomataSecuencia._headings
y GramaticaEstructuraAnalizador: los autómatas/gramáticas consumen el flujo
tokenizado (o su proyección de texto) en lugar de recorrer el XML directo.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .extractor import NS, ExtractedDocx, W, es_heading, text_of

# Tipos de token emitidos por el tokenizer.
TITULO = "TITULO"
PARRAFO = "PARRAFO"
TABLA = "TABLA"
IMAGEN = "IMAGEN"
SALTO_SECCION = "SALTO_SECCION"

TIPOS_CONOCIDOS = (TITULO, PARRAFO, TABLA, IMAGEN, SALTO_SECCION)


@dataclass(frozen=True)
class Token:
    """Un token del documento: tipo, texto y nivel (solo TITULO)."""

    tipo: str
    texto: str = ""
    nivel: int = 0

    def __str__(self) -> str:
        return self.texto


def _nivel_heading(estilo: str) -> int:
    """Nivel del encabezado a partir del valor del pStyle (Heading1, Ttulo2…)."""
    m = re.search(r"(\d+)\s*$", estilo)
    return int(m.group(1)) if m else 1


def _blips_para(p) -> int:
    """Cantidad de imágenes (a:blip) embebidas en un párrafo."""
    return len(p.xpath(".//a:blip", namespaces=NS))


def tokenizar(extracted: ExtractedDocx) -> list[Token]:
    """Convierte el documento extraído en el flujo de tokens en orden.

    Recorre párrafos, tablas y saltos de sección en orden de documento
    (incluye los párrafos anidados dentro de tablas, igual que el XPath
    `//w:body//w:p` del motor legacy).
    """
    doc = extracted.document
    body = doc.find(f"{W}body")
    if body is None:
        return []

    tokens: list[Token] = []
    for el in body.iter(W + "p", W + "tbl", W + "sectPr"):
        if el.tag == W + "sectPr":
            tokens.append(Token(SALTO_SECCION))
            continue
        if el.tag == W + "tbl":
            tokens.append(Token(TABLA))
            continue

        # Es un párrafo (w:p).
        pPr = el.find(W + "pPr")
        st = pPr.find(W + "pStyle") if pPr is not None else None
        val = st.get(W + "val") if st is not None else None
        texto = text_of(el).strip()
        estilo = str(val) if val is not None else ""

        if es_heading(estilo):
            tokens.append(Token(TITULO, texto, _nivel_heading(estilo)))
        else:
            tokens.append(Token(PARRAFO, texto))

        for _ in range(_blips_para(el)):
            tokens.append(Token(IMAGEN))

        # sectPr anidado en pPr: el corte de sección va DESPUÉS del párrafo.
        if pPr is not None and pPr.find(W + "sectPr") is not None:
            tokens.append(Token(SALTO_SECCION))

    return tokens


def solo(tokens: Sequence[Token], tipos) -> list[Token]:
    """Filtra el flujo conservando solo los tipos indicados."""
    permitidos = set(tipos)
    return [t for t in tokens if t.tipo in permitidos]


def seccion(
    tokens: Sequence[Token],
    inicio: str,
    fin: str | None = None,
    hasta_final: bool = False,
) -> list[Token]:
    """Slice de una sección delimitada por títulos (F3).

    Parámetros
    ----------
    tokens:
        Flujo tipado emitido por `tokenizar` (o cualquier secuencia de
        Token con títulos).
    inicio:
        Regex que debe matchear el texto del primer TITULO que abre la
        sección. Ese título NO se incluye en el resultado; sí el resto del
        flujo hasta el corte.
    fin:
        Regex de corte (opcional). Solo un TITULO posterior cuyo texto la
        matchee cierra la sección; si se omite, corta ante el primer
        TITULO posterior (o al final del flujo si no hay más títulos).
    hasta_final:
        Si es True y no hay fin que matchee, la sección va hasta el final
        del documento (AUD-02). Por defecto False para mantener el
        comportamiento histórico.

    Semántica y advertencias
    ------------------------
    - Los límites se evalúan SOLO sobre tokens de tipo TITULO.
    - Las regex se aplican con ``re.search`` e IGNORECASE: es un match de
      subcadena, no exige el texto completo. Por eso conviene anclarlas
      (``^...$``); un fin ``"anexos"`` también cortaría ante un título
      "ANEXOS Y RECURSOS".
    - Sin ningún TITULO que matchee `inicio`: devuelve ``[]``.
    - Si `inicio` matchea y `fin` es ``None`` (o nunca matchea): devuelve
      el resto del flujo, a menos que `hasta_final` sea True en cuyo caso
      va hasta el final.
    - `inicio`/`fin` vacíos o en blanco: levanta ``ValueError``.

    Ejemplos
    --------
    >>> seccion(flujo, r"^resumen$")            # resumen → siguiente título
    >>> seccion(flujo, r"^referencias$", fin=r"^anexos$")   # hasta ANEXOS
    >>> seccion(flujo, r"^anexos$", hasta_final=True)        # hasta fin del doc
    """
    if not inicio or not inicio.strip():
        raise ValueError("'inicio' no puede ser una regex vacía o en blanco")
    if fin is not None and (not fin or not fin.strip()):
        raise ValueError("'fin' no puede ser una regex vacía o en blanco")
    rx0 = re.compile(inicio, re.IGNORECASE)
    rx1 = re.compile(fin, re.IGNORECASE) if fin else None
    begin = -1
    for i, t in enumerate(tokens):
        if t.tipo != TITULO:
            continue
        if begin == -1:
            if rx0.search(t.texto):
                begin = i
            continue
        if rx1 is None:
            if hasta_final:
                continue
            return list(tokens[begin + 1 : i])
        if rx1.search(t.texto):
            return list(tokens[begin + 1 : i])
    if begin == -1:
        return []
    if rx1 is None and hasta_final:
        return list(tokens[begin + 1 :])
    if rx1 is None:
        return list(tokens[begin + 1 :])
    return list(tokens[begin + 1 :])


def textos(tokens: Sequence[Token]) -> list[str]:
    """Proyección de texto del flujo (lo que consumen DFA/PDA/gramática)."""
    return [t.texto for t in tokens]
