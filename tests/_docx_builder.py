"""Construcción del DOCX sintético a partir de la config (soporte de F6).

Contiene la definición del documento "bueno" (`configuracion_base`), los
helpers XML de WordprocessingML y la compilación del paquete OPC
(`compilar_docx`). No conoce reglas individuales: es un generador de
DOCX puro, sin lógica de mutaciones (ver `_mutations`).
"""

import tempfile
import zipfile

from _xml_constants import ANS, CONTENT_TYPES, PNS, RELS, RNS, WNS, WPN

ANEXOS_BASE = [
    "Matriz de consistencia",
    "Instrumento(s) de recolección de datos",
    "Ficha técnica del instrumento",
    "Consentimiento informado",
    "Base de datos cuantitativa",
    "Reporte de similitud",
    "Carta de autorización institucional",
    "Declaración jurada",
    "Carta de autorización de publicación",
    "Juicio de expertos",
    "Base de datos cualitativa",
]

_HEADINGS_CUANT = [
    "DEDICATORIA",
    "JURADO EVALUADOR",
    "AGRADECIMIENTO",
    "ÍNDICE",
    "INDICE DE CONTENIDOS",
    "INDICE DE TABLAS",
    "INDICE DE FIGURAS",
    "PRESENTACIÓN",
    "RESUMEN",
    "ABSTRACT",
    "INTRODUCCIÓN",
    "1.3. EL PROBLEMA",
    "SITUACIÓN PROBLEMÁTICA",
    "ENUNCIADO DEL PROBLEMA",
    "JUSTIFICACIÓN O IMPORTANCIA",
    "OBJETIVOS",
    "1.5 VARIABLE(S) Y OPERACIONALIZACIÓN",
    "MARCO TEÓRICO",
    "ANTECEDENTES (ESTADO DEL ARTE)",
    "BASES TEÓRICAS",
    "METODOLOGÍA",
    "POBLACIÓN Y MUESTRA",
    "DISEÑO DE INVESTIGACIÓN",
    "INSTRUMENTO(S) USADO(S) EN LA RECOLECCIÓN DE DATOS",
    "MÉTODOS, TÉCNICAS Y PROCEDIMIENTOS USADOS EN EL ANÁLISIS E INTERPRETACIÓN DE DATOS",
    "RESULTADOS",
    "CONCLUSIONES",
    "REFERENCIAS",
    "ANEXOS",
]

# Cabeceras específicas del esquema cualitativo que, INSERTADAS entre las del
# plan cuantitativo, permiten reconocer AMBOS esquemas a la vez (el autómata
# salta las cabeceras que no matchean su transición actual).
_ANADIDAS_CUALITATIVO = [
    "CATEGORÍAS, MATRIZ DE CATEGORIZACIÓN Y UNIDAD DE ANÁLISIS",  # tras OBJETIVOS
    "PARTICIPANTES",  # tras METODOLOGÍA
    "INSTRUMENTOS USADOS EN LA RECOLECCIÓN DE INFORMACIÓN",  # tras DISEÑO DE INVESTIGACIÓN
    "MÉTODOS, TÉCNICAS, PROCEDIMIENTOS Y ESTRATEGIAS USADAS EN EL ANÁLISIS E INTERPRETACIÓN DE DATOS",  # tras MÉTODOS... DATOS
    "ANÁLISIS Y DISCUSIÓN DE RESULTADOS",  # tras lo anterior
]

_ANADIDAS_REVISION = [
    ("INTRODUCCIÓN", "METODOLOGÍA DE REVISIÓN"),
    ("BASES TEÓRICAS", "DESARROLLO O ANÁLISIS CRÍTICO DE LA LITERATURA"),
    ("RESULTADOS", "CONCLUSIONES Y RECOMENDACIONES"),
]

# Entradas del índice de contenidos (rito bajo "INDICE DE CONTENIDOS").
# Formato `(nivel, texto)` con `nivel` para el estilo `TDC{nivel}` (no es un
# encabezado: el analizador de TOC la reconoce como entrada). El texto copia
# el estilo de las plantillas UNT: número + título + número de página.
# - ítem 11 (indice_apunta_secciones): cada entrada apunta a un título real.
# - ítem 12 (indice_numeracion_jerarquica): capítulos I..VI consecutivos y
#   subsecciones K.x en orden preorder bajo su capítulo.
TDC_ENTRADAS_BASE = [
    (1, "PRESENTACIÓN iii"),
    (1, "RESUMEN v"),
    (1, "ABSTRACT vii"),
    (1, "I. INTRODUCCIÓN 1"),
    (2, "1.1. SITUACIÓN PROBLEMÁTICA 2"),
    (2, "1.2. ENUNCIADO DEL PROBLEMA 4"),
    (2, "1.3. JUSTIFICACIÓN O IMPORTANCIA 6"),
    (2, "1.4. OBJETIVOS 9"),
    (2, "1.5 VARIABLE(S) Y OPERACIONALIZACIÓN 11"),
    (1, "II. MARCO TEÓRICO 13"),
    (2, "2.1. ANTECEDENTES (ESTADO DEL ARTE) 14"),
    (2, "2.2. BASES TEÓRICAS 17"),
    (1, "III. METODOLOGÍA 20"),
    (2, "3.1. POBLACIÓN Y MUESTRA 21"),
    (2, "3.2. DISEÑO DE INVESTIGACIÓN 23"),
    (2, "3.3. INSTRUMENTO(S) USADO(S) EN LA RECOLECCIÓN DE DATOS 25"),
    (
        2,
        "3.4. MÉTODOS, TÉCNICAS Y PROCEDIMIENTOS USADOS EN EL ANÁLISIS E INTERPRETACIÓN DE DATOS 27",
    ),
    (1, "IV. RESULTADOS 30"),
    (1, "V. CONCLUSIONES 33"),
    (1, "VI. ANEXOS 35"),
]


# ---------------------------------------------------------------------------
# Helpers XML (portados de test_paridad_formatos / test_f3_mecanizacion).
# ---------------------------------------------------------------------------


def _run(texto: str, rpr_inner: str = "") -> str:
    rpr = f"<w:rPr>{rpr_inner}</w:rPr>" if rpr_inner else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{texto}</w:t></w:r>'


def _run_portada(spec: dict) -> str:
    rpr = ""
    if spec.get("negrita"):
        rpr += "<w:b/>"
    if spec.get("sz"):
        rpr += f'<w:sz w:val="{spec["sz"]}"/>'
    return _run(spec["texto"], rpr)


def _cover_para(spec: dict) -> str:
    """Párrafo de la portada con alineación controlada."""
    if spec.get("logo"):
        return f"<w:p>{_logo()}</w:p>"
    if spec.get("orcid"):
        return (
            f'<w:p><w:pPr><w:jc w:val="{spec.get("jc", "center")}"/></w:pPr>'
            f'<w:hyperlink r:id="rIdOrc" xmlns:r="{RNS}">'
            f'<w:r><w:t xml:space="preserve">https://orcid.org/0000-0002-1825-0097</w:t></w:r>'
            f"</w:hyperlink></w:p>"
        )
    jc = spec.get("jc", "center")
    return f'<w:p><w:pPr><w:jc w:val="{jc}"/></w:pPr>{_run_portada(spec)}</w:p>'


def _body_para(texto: str) -> str:
    return f"<w:p>{_run(texto)}</w:p>"


def _cuerpo_para(texto: str, cfg: dict) -> str:
    """Párrafo de la última sección (contenido del cuerpo, estilos del manual)."""
    pPr = (
        f'<w:pPr><w:spacing w:line="{cfg["interlineado"]}" w:lineRule="auto"/>'
        f'<w:jc w:val="{cfg["jc_cuerpo"]}"/>'
        f'<w:ind w:firstLine="{cfg["sangria"]}"/></w:pPr>'
    )
    rpr = (
        f'<w:rFonts w:ascii="{cfg["fuente"]}" w:hAnsi="{cfg["fuente"]}"/>'
        f'<w:sz w:val="{cfg["sz_cuerpo"]}"/><w:szCs w:val="{cfg["sz_cuerpo"]}"/>'
    )
    return f"<w:p>{pPr}{_run(texto, rpr)}</w:p>"


def _nivel_heading(texto: str) -> int:
    if texto.startswith(("    ", "1.5 ")):
        return 3
    if texto.startswith("  "):
        return 2
    return 1


def _heading(texto: str) -> str:
    nivel = _nivel_heading(texto)
    return f'<w:p><w:pPr><w:pStyle w:val="Ttulo{nivel}"/></w:pPr>{_run(texto)}</w:p>'


def _tdc_para(entrada: tuple) -> str:
    """Párrafo del índice de contenidos (estilo TDC{nivel}, no es heading)."""
    nivel, texto = entrada
    return f'<w:p><w:pPr><w:pStyle w:val="TDC{nivel}"/></w:pPr>{_run(texto)}</w:p>'


def _logo() -> str:
    return (
        "<w:r><w:drawing><wp:inline><a:graphic><a:graphicData "
        'uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic><pic:blipFill><a:blip r:embed="rIdImg"/></pic:blipFill>'
        "<pic:spPr/></pic:pic></a:graphicData></a:graphic></wp:inline>"
        "</w:drawing></w:r>"
    )


def _footer_xml(jc: str) -> str:
    if jc == "right":
        instr = (
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> PAGE \\* MERGEFORMAT </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        )
        texto = instr
    else:
        texto = "<w:r><w:t>UNIVERSIDAD</w:t></w:r>"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:ftr xmlns:w="{WNS}">'
        f'<w:p><w:pPr><w:jc w:val="{jc}"/></w:pPr>{texto}'
        "</w:p></w:ftr>"
    )


def _header_xml(cfg: dict) -> str:
    """Encabezado con membrete: logo UNT (imagen) + nombre, en Times New Roman."""
    logo = _logo() if cfg.get("header_logo", True) else ""
    rpr = (
        '<w:rPr><w:rFonts w:ascii="'
        f'{cfg.get("header_fuente", "Times New Roman")}" w:hAnsi="'
        f'{cfg.get("header_fuente", "Times New Roman")}"/></w:rPr>'
    )
    texto = f"<w:r>{rpr}<w:t>UNIVERSIDAD NACIONAL DE TRUJILLO</w:t></w:r>"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:hdr xmlns:w="{WNS}" xmlns:r="{RNS}" xmlns:a="{ANS}" '
        f'xmlns:pic="{PNS}" xmlns:wp="{WPN}">'
        f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr>{logo}{texto}'
        "</w:p></w:hdr>"
    )


# ---------------------------------------------------------------------------
# Configuración base del documento "bueno".
# ---------------------------------------------------------------------------


def configuracion_base() -> dict:
    """Devuelve la configuración del DOCX que pasa 45/47 reglas."""
    portada = {
        "univ": {"texto": "UNIVERSIDAD NACIONAL DE TRUJILLO", "negrita": True, "sz": 36},
        "logo": {"logo": True},
        "facultad": {
            "texto": "FACULTAD DE EDUCACIÓN Y CIENCIAS DE LA COMUNICACIÓN",
            "negrita": True,
            "sz": 26,
        },
        "escuela": {"texto": "ESCUELA PROFESIONAL DE EDUCACIÓN INICIAL", "negrita": True, "sz": 26},
        "titulo": {
            "texto": "Título del trabajo de investigación: Estrategias lúdicas "
            "para el desarrollo de la motricidad fina.",
            "negrita": True,
            "sz": 28,
        },
        "optar": {
            "texto": "Para optar el Grado de Bachiller en Educación Inicial",
            "negrita": True,
            "sz": 26,
        },
        "autores_label": {"texto": "Autores: ", "negrita": False, "sz": 24},
        "autores_nombre": {"texto": "ANA MARÍA PÉREZ GARCÍA", "negrita": False, "sz": 24},
        "asesor": {
            "texto": "Asesor(a): Mag. Carlos Alberto RODRÍGUEZ MIRANDA",
            "negrita": True,
            "sz": 24,
        },
        "linea_label": {"texto": "Línea de investigación: ", "negrita": False, "sz": 24},
        "linea": {
            "texto": "Educación y Ciencias de la Comunicación y Desarrollo Sostenible",
            "negrita": False,
            "sz": 24,
        },
        "ciudad": {"texto": "TRUJILLO - PERÚ, 2026", "negrita": True, "sz": 24},
        "proyecto": {"texto": "PROYECTO DE INVESTIGACIÓN", "negrita": False, "sz": 26},
        "orcid": {"orcid": True, "jc": "center"},
    }
    return {
        "portada": portada,
        "headings": list(_HEADINGS_CUANT),
        "fuente": "Times New Roman",
        "sz_cuerpo": 24,
        "interlineado": 360,
        "jc_cuerpo": "both",
        "sangria": 720,
        "margenes": {"top": 1418, "right": 1418, "bottom": 1418, "left": 1701},
        "pg": {"w": 11906, "h": 16838},
        "prel_numfmt": "lowerRoman",
        "final_numtype": None,
        "titlepg": True,
        "footer_jc": "right",
        "resumen_palabras": 175,
        "palabras_clave_n": 3,
        "referencias_n": 30,
        "anexos_items": list(ANEXOS_BASE),
        "indices_paginas_separadas": True,
        "header_logo": True,
        "header_fuente": "Times New Roman",
        "notas_pie_ids": [],
        "tdc_entradas": list(TDC_ENTRADAS_BASE),
    }


# ---------------------------------------------------------------------------
# Compilación del DOCX a partir de la configuración.
# ---------------------------------------------------------------------------


def _headings_insertadas(base: list, anadidas: list) -> list:
    """Inserta cabeceras nuevas después de un ancla, sin duplicar."""
    resultado = []
    for h in base:
        resultado.append(h)
        for ancla, nueva in anadidas:
            if h == ancla:
                resultado.append(nueva)
    return resultado


def _page_break_para() -> str:
    """Párrafo con salto de página real (w:lastRenderedPageBreak) para
    simular paginación física en el DOCX sintético."""
    return (
        "<w:p><w:pPr><w:rPr>"
        "<w:rFonts w:ascii='Times New Roman' w:hAnsi='Times New Roman'/>"
        "</w:rPr></w:pPr>"
        "<w:r><w:lastRenderedPageBreak/></w:r>"
        "</w:p>"
    )


def _document_xml(cfg: dict) -> str:
    paras = []

    # Portada
    for spec in cfg["portada"].values():
        paras.append(_cover_para(spec))

    # Preliminares (resumen con su contenido, luego referencias y anexos)
    indices_separados = cfg.get("indices_paginas_separadas", False)
    for h in cfg["headings"]:
        if indices_separados and h in (
            "INDICE DE CONTENIDOS",
            "INDICE DE TABLAS",
            "INDICE DE FIGURAS",
        ):
            paras.append(_page_break_para())
        paras.append(_heading(h))
        if h == "INTRODUCCIÓN":
            # Párrafos de prosa del cuerpo: viven entre Introducción y
            # Referencias (el extractor define el cuerpo por ese rango
            # semántico, no por la última sección del documento).
            paras.append(
                _cuerpo_para(
                    "La motricidad fina se desarrolla a través de estrategias lúdicas.", cfg
                )
            )
            paras.append(
                _cuerpo_para("Se aplicó un estudio cuantitativo con diseño experimental.", cfg)
            )
            paras.append(_cuerpo_para("Los resultados muestran una mejora significativa.", cfg))
        if h == "INDICE DE CONTENIDOS":
            paras.extend(_tdc_para(e) for e in cfg.get("tdc_entradas", []))
        if h == "RESUMEN":
            paras.append(
                _body_para(" ".join(f"resumen{i}" for i in range(cfg["resumen_palabras"])))
            )
            claves = ", ".join(f"clave{i}" for i in range(cfg["palabras_clave_n"]))
            paras.append(_body_para(f"Palabras clave: {claves}"))
        if h == "REFERENCIAS":
            paras.extend(
                _body_para(f"Autor, A. ({1990 + i}). Fuente bibliográfica {i}.")
                for i in range(cfg["referencias_n"])
            )
        if h == "ANEXOS":
            paras.extend(
                _body_para(f"Anexo {i + 1}. {item}") for i, item in enumerate(cfg["anexos_items"])
            )

    # Marcador de sección (fin de preliminares); la prosa del cuerpo ya se
    # insertó tras el heading "INTRODUCCIÓN". Los párrafos que siguen al
    # marcador no son cuerpo (anexos finales y notas), solo cierran el doc.
    paras.append(_sect_marker(cfg))
    nota_pie = _notas_pie_para(cfg)
    if nota_pie:
        paras.append(nota_pie)
    paras.append(_sect_final(cfg))

    body = "".join(paras)
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}" xmlns:r="{RNS}" xmlns:a="{ANS}" '
        f'xmlns:pic="{PNS}" xmlns:wp="{WPN}">'
        f"<w:body>{body}</w:body></w:document>"
    )


def _sect_marker(cfg: dict) -> str:
    m = cfg["margenes"]
    titlepg = "<w:titlePg/>" if cfg["titlepg"] else ""
    return (
        "<w:p><w:pPr><w:sectPr>"
        f'<w:pgSz w:w="{cfg["pg"]["w"]}" w:h="{cfg["pg"]["h"]}"/>'
        f'<w:pgMar w:top="{m["top"]}" w:right="{m["right"]}" '
        f'w:bottom="{m["bottom"]}" w:left="{m["left"]}"/>'
        f"{titlepg}{_header_ref()}{_footer_ref()}"
        f'<w:pgNumType w:fmt="{cfg["prel_numfmt"]}"/>'
        '</w:sectPr></w:pPr><w:r><w:t xml:space="preserve"> </w:t></w:r></w:p>'
    )


def _header_ref() -> str:
    return '<w:headerReference w:type="default" r:id="rIdHeader"/>'


def _footer_ref() -> str:
    return '<w:footerReference w:type="default" r:id="rIdFooter"/>'


def _notas_pie_para(cfg: dict) -> str:
    """Párrafo con referencias a notas al pie (w:footnoteReference) si hay."""
    notas = cfg.get("notas_pie_ids", [])
    if not notas:
        return ""
    refs = "".join(f'<w:r><w:footnoteReference w:id="{i}"/></w:r>' for i in notas)
    return f"<w:p>{refs}</w:p>"


def _footnotes_xml(ids: list) -> str:
    """Parte `word/footnotes.xml` con los separadores y las notas indicadas."""
    separadores = '<w:footnote w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:p></w:footnote><w:footnote w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:p></w:footnote>'
    notas = "".join(
        f'<w:footnote w:id="{i}"><w:p><w:r><w:t>{i}</w:t></w:r></w:p></w:footnote>' for i in ids
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{WNS}">{separadores}{notas}</w:footnotes>'
    )


def _sect_final(cfg: dict) -> str:
    m = cfg["margenes"]
    pgtype = f'<w:pgNumType w:fmt="{cfg["final_numtype"]}"/>' if cfg["final_numtype"] else ""
    return (
        "<w:sectPr>"
        f'<w:pgSz w:w="{cfg["pg"]["w"]}" w:h="{cfg["pg"]["h"]}"/>'
        f'<w:pgMar w:top="{m["top"]}" w:right="{m["right"]}" '
        f'w:bottom="{m["bottom"]}" w:left="{m["left"]}"/>'
        f"{_header_ref()}{_footer_ref()}{pgtype}"
        "</w:sectPr>"
    )


def compilar_docx(cfg: dict) -> str:
    """Compila la configuración a un DOCX temporal y devuelve la ruta."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", _document_xml(cfg))
        z.writestr("word/header1.xml", _header_xml(cfg))
        z.writestr("word/footer1.xml", _footer_xml(cfg["footer_jc"]))
        notas = cfg.get("notas_pie_ids", [])
        if notas:
            z.writestr("word/footnotes.xml", _footnotes_xml(notas))
    return path
