"""Mutaciones del factory de DOCX sintéticos (soporte de F6).

Cada regla de `reglas_unt.yaml` tiene aquí UNA mutación: un desvío MÍNIMO
sobre la configuración base que la hace fallar (solo a ella, o a su par
acoplado). También centraliza la metadata de cobertura de reglas
(`REGLAS`, `REGLAS_ACOPLADAS`, `NO_APLICABLES_BASE`).

Sincronización obligatoria: al importar este módulo se verifica que
`_MUTACIONES` tenga exactamente las mismas reglas que `reglas_unt.yaml`.
Si alguien agrega una regla al YAML sin mutación (o muere una mutación
sin quitarse del YAML), el import falla con un error claro — fallo en
recolecta de tests, no un test más que recordar actualizar.
"""

import copy
from pathlib import Path

import yaml
from _docx_builder import _ANADIDAS_REVISION, _HEADINGS_CUANT, _headings_insertadas

# ---------------------------------------------------------------------------
# Nombres de las reglas de reglas_unt.yaml (48).
# ---------------------------------------------------------------------------

REGLAS = [
    "deteccion_tipo_documento",
    "papel_tamano",
    "fuente_principal",
    "tamano_cuerpo",
    "caratula_universidad_tamano",
    "caratula_facultad_escuela_tamano",
    "caratula_titulo_trabajo_tamano",
    "caratula_optar_grado_tamano",
    "caratula_autores_tamano",
    "caratula_logotipo_tamano",
    "interlineado",
    "alineacion_cuerpo",
    "alineacion_caratula_todos_elementos",
    "margen_superior",
    "margen_inferior",
    "margen_derecho",
    "margen_izquierdo",
    "sangria_parrafo",
    "numeracion_posicion",
    "numeracion_preliminares_romano",
    "numeracion_cuerpo_arabigo",
    "caratula_no_se_enumera",
    "caratula_universidad_negrita_mayusculas",
    "caratula_facultad_negrita_mayusculas",
    "caratula_titulo_negrita_mixta",
    "caratula_autores_mayusculas_sin_negrita",
    "caratula_asesor_negrita",
    "caratula_ciudad_pais_negrita",
    "caratula_linea_investigacion",
    "estructura_tinv_cuantitativo",
    "estructura_tinv_cualitativo",
    "estructura_tinv_revision_literatura",
    "indice_subdivisiones",
    "resumen_longitud",
    "palabras_clave_minimo",
    "referencias_minimo_cuantitativo",
    "referencias_minimo_cualitativo",
    "referencias_minimo_revision",
    "anexos_minimos_cuantitativo",
    "anexos_minimos_cualitativo",
    "caratula_orcid",
    "proyecto_caratula_texto",
    "indice_paginas_separadas",
    "encabezado_membrete",
    "encabezado_formato",
    "notas_al_pie_consistencia",
    "indice_apunta_secciones",
    "indice_numeracion_jerarquica",
]

# Con `aplicar_si` (handover issue #5) las reglas tipo-específicas SOLO se
# evalúan en su propio tipo de documento. El documento base es cuantitativo,
# así que una mutación que VOLTEA el tipo (los esquemas alternativos) o lo
# vuelve contradictorio mueve, de paso, a todas las reglas condicionadas:
# las del tipo que se deja dejan de aplicar (`aplicable` pasa a False) y las
# del tipo al que se llega pasan a aplicarse. Ese acople es inherente a la
# detección y se documenta aquí, regla por regla:
#
# - Volteo a cualitativo (estructura_tinv_cualitativo y las mutaciones que lo
#   componen): 7 reglas — detección, la estructura cuantitativa deja de
#   aplicar, la cualitativa pasa a aplicarse, y los mínimos de referencias y
#   anexos de ambos tipos voltean su aplicabilidad.
# - Volteo a revisión: 6 reglas — las reglas del tipo cualitativo NO se
#   mueven (ya eran no aplicables y siguen siéndolo: la revisión tampoco es
#   su tipo).
# - Detección contradictoria (deteccion_tipo_documento): el tipo deja de ser
#   "uno de los tres", así que las reglas del cuantitativo dejan de aplicar.
# - Volteo a proyecto (proyecto_caratula_texto): 5 reglas — las reglas de los
#   tipos tinv alternativos ya eran no aplicables y no se mueven.
#
# - caratula_universidad_negrita_mayusculas y caratula_ciudad_pais_negrita
#   seleccionan el MISMO párrafo: la línea "UNIVERSIDAD NACIONAL DE TRUJILLO"
#   contiene "trujillo", así que `[1]` de la regla de ciudad resuelve al
#   párrafo de la universidad. Un cambio de negrita en esa línea las afecta
#   a ambas (quirk del XPath heredado del reglamento).
REGLAS_ACOPLADAS = {
    "estructura_tinv_cualitativo": {
        "deteccion_tipo_documento",
        "estructura_tinv_cuantitativo",
        "referencias_minimo_cuantitativo",
        "referencias_minimo_cualitativo",
        "anexos_minimos_cuantitativo",
        "anexos_minimos_cualitativo",
    },
    "referencias_minimo_cualitativo": {
        "deteccion_tipo_documento",
        "estructura_tinv_cualitativo",
        "estructura_tinv_cuantitativo",
        "referencias_minimo_cuantitativo",
        "anexos_minimos_cuantitativo",
        "anexos_minimos_cualitativo",
    },
    "anexos_minimos_cualitativo": {
        "deteccion_tipo_documento",
        "estructura_tinv_cualitativo",
        "estructura_tinv_cuantitativo",
        "referencias_minimo_cuantitativo",
        "referencias_minimo_cualitativo",
        "anexos_minimos_cuantitativo",
    },
    "estructura_tinv_revision_literatura": {
        "deteccion_tipo_documento",
        "estructura_tinv_cuantitativo",
        "referencias_minimo_cuantitativo",
        "referencias_minimo_revision",
        "anexos_minimos_cuantitativo",
    },
    "referencias_minimo_revision": {
        "deteccion_tipo_documento",
        "estructura_tinv_cuantitativo",
        "estructura_tinv_revision_literatura",
        "referencias_minimo_cuantitativo",
        "anexos_minimos_cuantitativo",
    },
    "proyecto_caratula_texto": {
        "deteccion_tipo_documento",
        "estructura_tinv_cuantitativo",
        "referencias_minimo_cuantitativo",
        "anexos_minimos_cuantitativo",
    },
    "caratula_universidad_negrita_mayusculas": {"caratula_ciudad_pais_negrita"},
    "caratula_ciudad_pais_negrita": {"caratula_universidad_negrita_mayusculas"},
    # indice_subdivisiones renombra "INDICE DE CONTENIDOS" -> "ÍNDICE GENERAL".
    # Con el xpath tolerante ("indice") el primer match cae en "INDICE DE
    # TABLAS": las páginas pasan de distintas a repetidas, así que
    # indice_paginas_separadas detecta el desvío. Acople unidireccional.
    # (Las reglas de TOC pasan a n/a con ese renombre, pero el `found` exitoso
    # es "cumple" en ambos casos -> sin acople observable.)
    "indice_subdivisiones": {"indice_paginas_separadas"},
    # estructura_tinv_cuantitativo renombra "SITUACIÓN PROBLEMÁTICA" ->
    # "PROBLEMÁTICA Y CONTEXTO": la entrada "1.1. SITUACIÓN PROBLEMÁTICA" del
    # índice deja de apuntar a una sección real (falla indice_apunta_secciones).
    "estructura_tinv_cuantitativo": {"indice_apunta_secciones"},
    # Al revés que las de arriba: una detección contradictoria (el Anexo 10
    # declara un tipo que la estructura desmiente) hace que el tipo real ya no
    # sea "una de las tres", así que la estructura que antes aplicaba
    # (cuantitativo) deja de aplicar, y con ella los mínimos de referencias y
    # anexos del tipo cuantitativo. Las reglas de los otros tipos ya eran no
    # aplicables y siguen siéndolo. El paso 6 turns el caso contradictorio en
    # un error centinela propio en vez de validar contra las tres.
    # NOTA: el centinela `tipo_documento_contradictorio` aparece en el
    # documento mutado pero no se cuenta aquí porque no es una de las 48
    # reglas (lo deriva la detección).
    "deteccion_tipo_documento": {
        "estructura_tinv_cuantitativo",
        "referencias_minimo_cuantitativo",
        "anexos_minimos_cuantitativo",
    },
}

# El documento base es un plan tipo CUANTITATIVO, así que no le aplican ni los
# esquemas de los otros dos tipos de TINV ni, desde el issue #5 del handover,
# sus mínimos de referencias/anexos ni el texto de carátula del Proyecto.
# Desde el paso 4 no "fallan": la detección de tipo los marca como no
# aplicables (`aplicable=False`), que es la diferencia entre un error
# corregible y un error que no le toca al documento. Antes de ese paso las
# estructuras fallaban y ponían el semáforo en rojo.
NO_APLICABLES_BASE = {
    "estructura_tinv_cualitativo",
    "estructura_tinv_revision_literatura",
    "referencias_minimo_cualitativo",
    "referencias_minimo_revision",
    "anexos_minimos_cualitativo",
    "proyecto_caratula_texto",
}


# ---------------------------------------------------------------------------
# Aplicación de mutaciones.
# ---------------------------------------------------------------------------


def aplicar_mutacion(rule_id: str, cfg: dict) -> dict:
    """Devuelve una copia de `cfg` con el desvío mínimo para `rule_id`.

    Levanta `KeyError` si la regla no tiene mutación definida.
    """
    nuevo = _copia(cfg)
    _MUTACIONES[rule_id](nuevo)
    return nuevo


def _copia(cfg: dict) -> dict:
    return copy.deepcopy(cfg)


def _mut_margen(attr: str):
    def _f(cfg: dict) -> None:
        cfg["margenes"][attr] = 1300

    return _f


def _renombrar_heading(cfg: dict, actual: str, nuevo: str) -> None:
    cfg["headings"] = [nuevo if h == actual else h for h in cfg["headings"]]


def _renumerar_tdc(cfg: dict, actual: str, nuevo: str) -> None:
    """Renumera una entrada del índice (nivel, texto) para el ítem 12."""
    cfg["tdc_entradas"] = [(n, nuevo if t == actual else t) for n, t in cfg["tdc_entradas"]]


def _insertar_tdc(cfg: dict, despues_de: str, entrada: tuple) -> None:
    """Inserta una entrada del índice en orden, tras la que tenga `despues_de`."""
    acum = []
    for n, t in cfg["tdc_entradas"]:
        acum.append((n, t))
        if t == despues_de:
            acum.append(entrada)
    cfg["tdc_entradas"] = acum


def _interleaved_cualitativo() -> list:
    """Plan cuantitativo + cabeceras del esquema cualitativo intercaladas."""
    res = []
    for h in _HEADINGS_CUANT:
        res.append(h)
        if h == "OBJETIVOS":
            res.append("CATEGORÍAS, MATRIZ DE CATEGORIZACIÓN Y UNIDAD DE ANÁLISIS")
        if h == "METODOLOGÍA":
            res.append("PARTICIPANTES")
        if h == "DISEÑO DE INVESTIGACIÓN":
            res.append("INSTRUMENTOS USADOS EN LA RECOLECCIÓN DE INFORMACIÓN")
        if (
            h
            == "MÉTODOS, TÉCNICAS Y PROCEDIMIENTOS USADOS EN EL ANÁLISIS E INTERPRETACIÓN DE DATOS"
        ):
            res.append(
                "MÉTODOS, TÉCNICAS, PROCEDIMIENTOS Y ESTRATEGIAS USADAS EN EL ANÁLISIS E INTERPRETACIÓN DE DATOS"
            )
            res.append("ANÁLISIS Y DISCUSIÓN DE RESULTADOS")
    return res


# Volteos de tipo (handover issue #5): las reglas condicionadas con
# `aplicar_si` no se evalúan en el doc base (cuantitativo), así que su
# mutación primero vuelve el documento legible para su propio tipo y
# después agrega el desvío que la regla debe detectar.


def _voltear_cualitativo(c: dict) -> None:
    """Misma mutación de headings que `estructura_tinv_cualitativo`: el
    documento pasa a leerse como TINV cualitativo."""
    c["headings"] = _interleaved_cualitativo()


def _voltear_revision(c: dict) -> None:
    """Misma mutación de headings que `estructura_tinv_revision_literatura`:
    el documento pasa a leerse como revisión de la literatura."""
    c["headings"] = _headings_insertadas(_HEADINGS_CUANT, _ANADIDAS_REVISION)


def _voltear_proyecto(c: dict) -> None:
    """Añade dos firmas de proyecto (párrafos con estilo de título) para que
    la detección lea el documento como proyecto cuantitativo.

    `proyecto_cuantitativo` se evalúa ANTES que los TINV en el orden de
    especificidad de la detección, así que con dos firmas gana. El doc no
    declara nada en el Anexo 10, no hay contradicción: el tipo queda
    `proyecto_cuantitativo` y las reglas de proyecto pasan a aplicarse.
    """
    c["headings"] = list(c["headings"]) + [
        "PLAN DE INVESTIGACIÓN",
        "RECURSOS Y MATERIALES",
    ]


def _mut_referencias_cualitativo(c: dict) -> None:
    _voltear_cualitativo(c)
    c["referencias_n"] = 29


def _mut_referencias_revision(c: dict) -> None:
    _voltear_revision(c)
    c["referencias_n"] = 19


def _mut_anexos_cualitativo(c: dict) -> None:
    _voltear_cualitativo(c)
    c["anexos_items"].remove("Juicio de expertos")


def _mut_proyecto_caratula(c: dict) -> None:
    _voltear_proyecto(c)
    c["portada"]["proyecto"].update(sz=24)


_MUTACIONES = {
    "papel_tamano": lambda c: c["pg"].update(w=10000),
    "fuente_principal": lambda c: c.update(fuente="Arial"),
    "tamano_cuerpo": lambda c: c.update(sz_cuerpo=30),
    "caratula_universidad_tamano": lambda c: c["portada"]["univ"].update(sz=24),
    "caratula_facultad_escuela_tamano": lambda c: c["portada"]["facultad"].update(sz=20),
    "caratula_titulo_trabajo_tamano": lambda c: c["portada"]["titulo"].update(sz=26),
    "caratula_optar_grado_tamano": lambda c: c["portada"]["optar"].update(sz=24),
    "caratula_autores_tamano": lambda c: c["portada"]["autores_nombre"].update(sz=30),
    "caratula_logotipo_tamano": lambda c: c["portada"].pop("logo"),
    "interlineado": lambda c: c.update(interlineado=300),
    "alineacion_cuerpo": lambda c: c.update(jc_cuerpo="left"),
    "alineacion_caratula_todos_elementos": lambda c: c["portada"]["asesor"].update(jc="left"),
    "margen_superior": _mut_margen("top"),
    "margen_inferior": _mut_margen("bottom"),
    "margen_derecho": _mut_margen("right"),
    "margen_izquierdo": _mut_margen("left"),
    "sangria_parrafo": lambda c: c.update(sangria=0),
    "numeracion_posicion": lambda c: c.update(footer_jc="center"),
    "numeracion_preliminares_romano": lambda c: c.update(prel_numfmt="decimal"),
    "numeracion_cuerpo_arabigo": lambda c: c.update(final_numtype="decimal"),
    "caratula_no_se_enumera": lambda c: c.update(titlepg=False),
    "caratula_universidad_negrita_mayusculas": lambda c: c["portada"]["univ"].update(negrita=False),
    "caratula_facultad_negrita_mayusculas": lambda c: c["portada"]["facultad"].update(
        negrita=False
    ),
    "caratula_titulo_negrita_mixta": lambda c: c["portada"]["titulo"].update(negrita=False),
    "caratula_autores_mayusculas_sin_negrita": lambda c: c["portada"]["autores_nombre"].update(
        negrita=True
    ),
    "caratula_asesor_negrita": lambda c: c["portada"]["asesor"].update(negrita=False),
    "caratula_ciudad_pais_negrita": lambda c: c["portada"]["univ"].update(negrita=False),
    "caratula_linea_investigacion": lambda c: c["portada"]["linea"].update(
        texto="Tecnologías disruptivas"
    ),
    "estructura_tinv_cuantitativo": lambda c: _renombrar_heading(
        c, "SITUACIÓN PROBLEMÁTICA", "PROBLEMÁTICA Y CONTEXTO"
    ),
    "estructura_tinv_cualitativo": lambda c: c.update(headings=_interleaved_cualitativo()),
    "estructura_tinv_revision_literatura": lambda c: c.update(
        headings=_headings_insertadas(_HEADINGS_CUANT, _ANADIDAS_REVISION)
    ),
    "indice_subdivisiones": lambda c: _renombrar_heading(
        c, "INDICE DE CONTENIDOS", "ÍNDICE GENERAL"
    ),
    "resumen_longitud": lambda c: c.update(resumen_palabras=60),
    "palabras_clave_minimo": lambda c: c.update(palabras_clave_n=2),
    "referencias_minimo_cuantitativo": lambda c: c.update(referencias_n=19),
    "referencias_minimo_cualitativo": _mut_referencias_cualitativo,
    "referencias_minimo_revision": _mut_referencias_revision,
    "anexos_minimos_cuantitativo": lambda c: c["anexos_items"].remove("Reporte de similitud"),
    "anexos_minimos_cualitativo": _mut_anexos_cualitativo,
    "caratula_orcid": lambda c: c["portada"].pop("orcid"),
    "proyecto_caratula_texto": _mut_proyecto_caratula,
    "indice_paginas_separadas": lambda c: c.update(indices_paginas_separadas=False),
    "encabezado_membrete": lambda c: c.update(header_logo=False),
    "encabezado_formato": lambda c: c.update(header_fuente="Arial"),
    "notas_al_pie_consistencia": lambda c: c.update(notas_pie_ids=[1, 2, 4]),
    # ítem 11 (indice_apunta_secciones): agregar una entrada que NO apunta a
    # ninguna sección real. El token significativo "DELIMITACIÓN" no está en
    # ningún título del cuerpo. Se inserta en orden (1.6 tras 1.5) para no
    # alterar la jerarquía del ítem 12.
    "indice_apunta_secciones": lambda c: _insertar_tdc(
        c,
        "1.5 VARIABLE(S) Y OPERACIONALIZACIÓN 11",
        (2, "1.6. DELIMITACIÓN DE LA INVESTIGACIÓN 40"),
    ),
    # ítem 12 (indice_numeracion_jerarquica): renumera una subsección fuera de
    # su capítulo (2.2 bajo el capítulo I) -> capitulo_descolgado.
    "indice_numeracion_jerarquica": lambda c: _renumerar_tdc(
        c, "1.2. ENUNCIADO DEL PROBLEMA 4", "2.2. ENUNCIADO DEL PROBLEMA 4"
    ),
    # deteccion_tipo_documento: el autor declara en el Anexo 10 un tipo que no
    # corresponde a la estructura del documento (marca "cualitativo" sobre un
    # plan cuantitativo). Es el desvío mínimo posible para esta regla: con
    # `minimo: 1` no se puede quitar la firma sin renombrar tres títulos, y
    # renombrarlos rompería además la estructura y el índice.
    "deteccion_tipo_documento": lambda c: c["anexos_items"].append(
        "☒ PROYECTO DE INVESTIGACIÓN CUALITATIVO"
    ),
}


# ---------------------------------------------------------------------------
# Sincronización con reglas_unt.yaml (garantía en import, no solo a runtime).
# ---------------------------------------------------------------------------

RUTA_REGLAS_YAML = Path(__file__).resolve().parent.parent / "reglas_unt.yaml"


def _validar_sincronizacion() -> None:
    """Falla el import si `_MUTACIONES` no cubre exactamente las 48 reglas.

    Evita la desincronización silenciosa factory↔YAML: el error ocurre en la
    recolecta de tests (cuando se importa el factory), no cuando un test
    específico decide recordar revisar el YAML.
    """
    datos = yaml.safe_load(RUTA_REGLAS_YAML.read_text(encoding="utf-8"))
    ids_yaml = {r["id"] for r in datos["reglas"]}
    ids_mut = set(_MUTACIONES)
    faltan = ids_yaml - ids_mut
    sobra = ids_mut - ids_yaml
    if faltan or sobra:
        raise RuntimeError(
            "docx_factory desincronizado con reglas_unt.yaml: "
            f"reglas en YAML sin mutación={sorted(faltan)} "
            f"mutaciones sin regla en YAML={sorted(sobra)}"
        )


_validar_sincronizacion()


# Conveniencia: exposición del resultado esperado del documento base.
# Desde el paso 4 el documento base pasa las 48 reglas: no hay desvíos, solo
# 2 esquemas que no le aplican.
DESVIOS_BASE = 0
TOTAL_REGLAS = len(REGLAS)
REGLAS_OK_BASE = TOTAL_REGLAS - DESVIOS_BASE
NO_APLICABLES_TOTAL = len(NO_APLICABLES_BASE)
