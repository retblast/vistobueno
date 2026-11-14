"""Tests de T2: endurecimiento del linter del DSL.

Cubre los cinco casos de configuración inválida que el linter NO detectaba
y que solo se manifestaban en runtime (o, peor, en silencio):

1. Sección mal escrita (`atributo_xmls`): la regla desaparecía del reporte
   sin ningún aviso, porque el compilador no la reconocía.
2. XPath con prefijo de namespace desconocido (`//wp:ind`): reventaba al
   EVALUAR contra el documento, con un `XPathEvalError` que la API
   mostraba al estudiante como si fuera un defecto de su tesis.
3. Severidad inventada (`aviso`): `Severity(...)` reventaba en runtime.
4. `aplicar_si` con un valor que no es un tipo documental declarado: la
   regla no aplicaba nunca y el semáforo quedaba verde sin comprobar.
5. `id` de regla duplicado: doble conteo en el resumen y dos observaciones
   indistinguibles con el mismo identificador.

Uso:
    pytest tests/test_t2_linter.py -v
"""

import ast
from pathlib import Path

import pytest
import yaml

from validator.dsl_check import DSLValidationError, linter, linter_o_alzar

# ---------------------------------------------------------------------------
# Helpers: construir DSL mínimo
# ---------------------------------------------------------------------------

PAGINA = {
    "parte": "document",
    "xpath": "//w:pgSz",
    "atributo": "@w:w",
}


def _regla(rule_id: str, **extra) -> dict:
    """Regla mínima con sección `atributo_xml`."""
    regla = {
        "id": rule_id,
        "tipo": "atributo_xml",
        "severidad": "error",
        "descripcion": "descripción de prueba",
        "atributo_xml": dict(PAGINA),
    }
    regla.update(extra)
    return regla


def _dsl(*reglas: dict) -> dict:
    return {"reglas": list(reglas)}


def _hallazgos(*reglas: dict) -> list[str]:
    return linter(_dsl(*reglas))


# ---------------------------------------------------------------------------
# 1. Sección mal escrita
# ---------------------------------------------------------------------------


def test_seccion_mal_escrita_se_detecta():
    hallazgos = _hallazgos(
        {
            "id": "r1",
            "tipo": "atributo_xml",
            "severidad": "error",
            "descripcion": "d",
            "atributo_xmls": dict(PAGINA),
        }
    )
    assert hallazgos, "una sección mal escrita debe producir un hallazgo"
    assert any("atributo_xmls" in h for h in hallazgos)


def test_seccion_mal_escrita_sugiere_la_correcta():
    hallazgos = _hallazgos(
        {
            "id": "r1",
            "tipo": "atributo_xml",
            "severidad": "error",
            "descripcion": "d",
            "atributo_xmls": dict(PAGINA),
        }
    )
    assert any("atributo_xml" in h and "quiso decir" in h for h in hallazgos)


def test_seccion_mal_escrita_era_silenciosa_antes():
    """El compilador se saltaba la regla sin avisar: la regla desaparecía."""
    from validator.compilador import CompilerDSL

    dsl = _dsl(
        {
            "id": "r1",
            "tipo": "atributo_xml",
            "severidad": "error",
            "descripcion": "d",
            "atributo_xmls": dict(PAGINA),
        }
    )
    compiladas = CompilerDSL().compilar(dsl, linter=False)
    assert compiladas == [], "sin linter la regla se pierde (motivo del fallo)"

    with pytest.raises(DSLValidationError):
        CompilerDSL().compilar(dsl)


def test_clave_legitima_no_se_confunde_con_seccion():
    """Las claves de nivel de regla no se reportan como secciones."""
    assert _hallazgos(_regla("r1", tipo="atributo_xml", valor_esperado="11906")) == []


def test_campo_propio_del_analizador_no_se_reporta():
    """Un campo extra de una sección no es una sección mal escrita."""
    config = dict(PAGINA)
    config["campo_propio"] = 1
    assert _hallazgos(_regla("r1", atributo_xml=config)) == []


@pytest.mark.parametrize(
    "clave",
    ["conteo", "patron", "lista", "nota", "gramatica"],
)
def test_clave_de_regla_truncada_se_detecta(clave):
    """Los truncamientos no llegan al umbral difuso, pero igual se reportan."""
    hallazgos = _hallazgos(
        {
            "id": "r1",
            "tipo": "atributo_xml",
            "severidad": "error",
            clave: dict(PAGINA),
        }
    )
    assert any(clave in h for h in hallazgos)


def test_clave_de_regla_desconocida_sin_sugerencia_se_detecta():
    """Aunque no haya una sección parecida, la clave inválida se reporta."""
    hallazgos = _hallazgos(
        {
            "id": "r1",
            "tipo": "atributo_xml",
            "severidad": "error",
            "campo_inventado": 1,
        }
    )
    assert any("campo_inventado" in h and "clave desconocida" in h for h in hallazgos)


def test_configuracion_de_seccion_no_dict_se_detecta():
    """Una sección que no es diccionario reventaba con `AttributeError`."""
    hallazgos = _hallazgos(
        {
            "id": "r1",
            "tipo": "lista_obligatoria",
            "severidad": "error",
            "lista_obligatoria": "x",
        }
    )
    assert any("diccionario" in h for h in hallazgos)


# ---------------------------------------------------------------------------
# 2. XPath con prefijo de namespace desconocido
# ---------------------------------------------------------------------------


def test_prefijo_xpath_desconocido_se_detecta():
    hallazgos = _hallazgos(_regla("r1", atributo_xml={"parte": "document", "xpath": "//wp:ind"}))
    assert hallazgos
    assert any("wp" in h for h in hallazgos)


def test_prefijo_xpath_desconocido_antes_fallaba_en_runtime():
    """Sin linter, el XPath inválido se evalúa contra el documento y falla."""
    from pathlib import Path

    from docx_factory import compilar_docx, configuracion_base

    from validator.compilador import CompilerDSL
    from validator.extractor import extract

    dsl = _dsl(_regla("r1", atributo_xml={"parte": "document", "xpath": "//wp:ind"}))
    regla = CompilerDSL().compilar(dsl, linter=False)[0]
    path = compilar_docx(configuracion_base())
    try:
        resultado = regla.ejecutar(extract(path))
    finally:
        Path(path).unlink(missing_ok=True)

    assert not resultado.passed
    assert "XPathEvalError" in resultado.found
    assert "Undefined namespace prefix" in resultado.found

    with pytest.raises(DSLValidationError):
        CompilerDSL().compilar(dsl)


@pytest.mark.parametrize(
    "xpath",
    [
        "//w:p[following-sibling::w:p]",
        "//w:p[preceding-sibling::w:tbl]",
        "//w:pgSz",
        "//a:blip",
        "//sectPr",
    ],
)
def test_xpath_valido_no_produce_hallazgo(xpath):
    """Los ejes de XPath no son prefijos: no deben dar falsos positivos."""
    assert _hallazgos(_regla("r1", atributo_xml={"parte": "document", "xpath": xpath})) == []


def test_prefijo_xpath_tambien_se_valida_en_paginacion():
    hallazgos = _hallazgos(
        _regla(
            "r1",
            paginacion={"xpaths": ["//wp:p", "//w:tbl"], "parrafo": "//w:p"},
        )
    )
    assert any("wp" in h for h in hallazgos)


@pytest.mark.parametrize(
    "xpath",
    [
        "//w:p[contains(., 'Palabras clave:')]",
        "//w:p[contains(., 'Escuela:')]",
        "//w:p[contains(., 'http://ejemplo.test')]",
    ],
)
def test_dos_puntos_dentro_de_un_literal_no_es_un_prefijo(xpath):
    """Los literales del XPath no se confunden con prefijos de namespace."""
    assert _hallazgos(_regla("r1", atributo_xml={"parte": "document", "xpath": xpath})) == []


def test_xpath_con_sintaxis_invalida_se_detecta():
    """lxml también detecta la expresión mal formada, no solo el prefijo."""
    hallazgos = _hallazgos(_regla("r1", atributo_xml={"parte": "document", "xpath": "//w:p["}))
    assert any("sintaxis" in h for h in hallazgos)


def _regla_formato(**extra) -> dict:
    regla = {
        "id": "r1",
        "tipo": "formato_efectivo",
        "severidad": "error",
        "descripcion": "formato efectivo",
        "formato_efectivo": {
            "parte": "document",
            "parrafo_xpath": "//w:body//w:p",
            "propiedad": "w:sz/@w:val",
            "comparacion": "all_eq",
            "esperado": "24",
        },
    }
    regla["formato_efectivo"].update(extra)
    return regla


def test_parrafo_xpath_invalido_en_formato_efectivo_se_detecta():
    """El XPath de selección también se valida al cargar (M1)."""
    hallazgos = _hallazgos(_regla_formato(parrafo_xpath="//wp:p"))
    assert any("formato_efectivo" in h and "XPath inválido" in h for h in hallazgos), hallazgos


def test_propiedad_de_formato_invalida_se_detecta():
    """Una propiedad que el resolvedor no entiende falla al cargar, no en runtime."""
    hallazgos = _hallazgos(_regla_formato(propiedad="rFonts"))
    assert any("propiedad" in h and "inválida" in h for h in hallazgos), hallazgos


# ---------------------------------------------------------------------------
# 3. Severidad inventada
# ---------------------------------------------------------------------------


def test_severidad_inventada_se_detecta():
    hallazgos = _hallazgos(_regla("r1", severidad="aviso"))
    assert hallazgos
    assert any("aviso" in h for h in hallazgos)


def test_severidad_inventada_antes_reventaba_en_runtime():
    """Sin linter, `Severity('aviso')` revienta al construir el resultado."""
    from pathlib import Path

    from docx_factory import compilar_docx, configuracion_base

    from validator.compilador import CompilerDSL
    from validator.extractor import extract

    dsl = _dsl(_regla("r1", severidad="aviso"))
    regla = CompilerDSL().compilar(dsl, linter=False)[0]
    path = compilar_docx(configuracion_base())
    try:
        with pytest.raises(ValueError, match="aviso"):
            regla.ejecutar(extract(path))
    finally:
        Path(path).unlink(missing_ok=True)

    with pytest.raises(DSLValidationError):
        CompilerDSL().compilar(dsl)


@pytest.mark.parametrize("severidad", ["error", "warning"])
def test_severidad_valida_no_produce_hallazgo(severidad):
    assert _hallazgos(_regla("r1", severidad=severidad)) == []


def test_catalogo_de_severidades_sincronizado_con_models():
    """El linter no debe mantener una copia manual de `Severity`."""
    from validator.dsl_check import _SEVERIDADES
    from validator.models import Severity

    assert _SEVERIDADES == {s.value for s in Severity}


# ---------------------------------------------------------------------------
# 4. aplicar_si con valor que no es un tipo documental declarado
# ---------------------------------------------------------------------------

DETECCION = {
    "id": "deteccion_tipo_documento",
    "tipo": "deteccion_tipo",
    "severidad": "error",
    "descripcion": "d",
    "deteccion_tipo": {
        "expone": "tipo_documento",
        "firmas": [
            {"tipo": "tinv_cuantitativo", "evidencia": ["cuantitativo"], "minimo": 1},
            {"tipo": "tinv_cualitativo", "evidencia": ["cualitativo"], "minimo": 1},
        ],
    },
}


def test_aplicar_si_con_valor_invalido_se_detecta():
    hallazgos = _hallazgos(
        DETECCION,
        _regla("consumidor", aplicar_si={"tipo_documento": "tinv_cuantiativo"}),
    )
    assert hallazgos
    assert any("tinv_cuantiativo" in h for h in hallazgos)


def test_aplicar_si_con_lista_de_valores_invalidos_se_detecta():
    hallazgos = _hallazgos(
        DETECCION,
        _regla("consumidor", aplicar_si={"tipo_documento": ["tinv_cuantitativo", "tinv_x"]}),
    )
    assert any("tinv_x" in h for h in hallazgos)


def test_aplicar_si_con_valor_valido_no_produce_hallazgo():
    assert (
        _hallazgos(
            DETECCION,
            _regla("consumidor", aplicar_si={"tipo_documento": "tinv_cuantitativo"}),
        )
        == []
    )


def test_aplicar_si_sobre_clave_no_documental_no_se_contrasta():
    """Solo las claves de tipo documental se contrastan contra un catálogo."""
    assert (
        _hallazgos(
            _regla("expone", expone="mi_clave"),
            _regla("consumidor", aplicar_si={"mi_clave": "cualquier_cosa"}),
        )
        == []
    )


@pytest.mark.parametrize("centinela", ["sin_determinar", "contradictorio"])
def test_aplicar_si_con_centinelas_es_valido(centinela):
    """Los centinelas de `DeteccionTipo` son valores legítimos."""
    assert (
        _hallazgos(DETECCION, _regla("consumidor", aplicar_si={"tipo_documento": centinela})) == []
    )


def test_centinelas_sincronizados_con_analizadores():
    """El linter no debe inventar centinelas que el motor no publica."""
    from validator.analizadores import TIPO_CONTRADICTORIO, TIPO_SIN_DETERMINAR
    from validator.dsl_check import _TIPOS_SENTINELA

    assert _TIPOS_SENTINELA == {TIPO_SIN_DETERMINAR, TIPO_CONTRADICTORIO}


# ---------------------------------------------------------------------------
# 5. id duplicado
# ---------------------------------------------------------------------------


def test_id_duplicado_se_detecta():
    hallazgos = _hallazgos(_regla("dup"), _regla("dup"))
    assert hallazgos
    assert any("duplicado" in h for h in hallazgos)


def test_id_duplicado_produce_un_solo_hallazgo():
    """El id repetido se reporta una vez, no una por regla afectada."""
    hallazgos = linter(_dsl(_regla("dup"), _regla("dup")))
    assert len(hallazgos) == 1
    assert "duplicado" in hallazgos[0]


def test_ids_unicos_no_producen_hallazgo():
    assert _hallazgos(_regla("r1"), _regla("r2")) == []


# ---------------------------------------------------------------------------
# Guard: los archivos de producción pasan el linter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "archivo",
    ["reglas_unt.yaml", "reglas_unt_pendientes.yaml", "reglas_ficha.yaml"],
)
def test_yaml_de_produccion_pasa_el_linter(archivo):
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    datos = yaml.safe_load((raiz / archivo).read_text(encoding="utf-8"))
    assert linter(datos) == [], f"{archivo} tiene hallazgos del linter"


def test_linter_o_alzar_mensaje_legible():
    with pytest.raises(DSLValidationError) as exc:
        linter_o_alzar(_dsl(_regla("dup"), _regla("dup")))
    assert "duplicado" in str(exc.value)


_NOMBRES_REGLA = frozenset({"rule", "regla"})
_NOMBRES_CONTENEDOR = frozenset({"reglas", "rules"})


def _es_acceso_a_contenedor_de_reglas(nodo: ast.AST) -> bool:
    """¿La expresión lee la lista de reglas: `.get("reglas")` o `["rules"]`?

    Solo se mira la clave (primer argumento de `.get` o del subíndice), no
    cualquier cadena del iterable: `config.get("otra", "rules")` no es el
    contenedor de reglas (L-12).
    """
    if (
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "get"
    ):
        argumentos = nodo.args
    elif isinstance(nodo, ast.Subscript):
        argumentos = [nodo.slice]
    else:
        return False
    if not argumentos:
        return False
    clave = argumentos[0]
    return isinstance(clave, ast.Constant) and clave.value in _NOMBRES_CONTENEDOR


def _itera_contenedor_de_reglas(nodo: ast.AST, contenedores: set[str]) -> bool:
    """¿El iterable de un `for` es la lista de reglas, directa o por variable?"""
    if _es_acceso_a_contenedor_de_reglas(nodo):
        return True
    return isinstance(nodo, ast.Name) and nodo.id in contenedores


def _agregar_nombres(destinos: list[ast.AST], conjunto: set[str]) -> bool:
    """Añade al conjunto los nombres asignados en los destinos."""
    cambiado = False
    for destino in destinos:
        for nombre in ast.walk(destino):
            if isinstance(nombre, ast.Name) and nombre.id not in conjunto:
                conjunto.add(nombre.id)
                cambiado = True
    return cambiado


def _propagar_asignacion(
    valor: ast.AST,
    destinos: list[ast.AST],
    receptores: set[str],
    contenedores: set[str],
) -> bool:
    """Propaga receptores de regla y contenedores de reglas en una asignación."""
    if isinstance(valor, ast.Name) and valor.id in receptores:
        return _agregar_nombres(destinos, receptores)
    if _itera_contenedor_de_reglas(valor, contenedores):
        return _agregar_nombres(destinos, contenedores)
    return False


def _es_receptor_de_regla(nodo: ast.AST, receptores: set[str]) -> bool:
    """¿El receptor de un acceso es un diccionario de regla?"""
    if isinstance(nodo, ast.Name):
        return nodo.id in receptores
    # `self.rule` y cualquier otro `<objeto>.rule` / `.regla`.
    return isinstance(nodo, ast.Attribute) and nodo.attr in _NOMBRES_REGLA


def _claves_de_regla_en_fuente(codigo: str) -> set[str]:
    """Claves de nivel de regla leídas en un fragmento, vía AST.

    Se considera receptor de regla una variable llamada `rule`/`regla` o
    cualquier atributo `.rule`/`.regla` (p. ej. `self.rule`). Además se
    propagan los alias, los destinos de un `for` sobre
    `.get("reglas"/"rules")` y las variables que guardan esa lista
    (`reglas = rules_data.get("reglas", [])`), para que renombrar la
    variable no deje el guard en verde sin cubrir nada (L-7 y L-11).

    Al recorrer el AST da igual la comilla usada y se detectan también los
    accesos con subíndice, que un regex sobre el texto no veía.
    """
    arbol = ast.parse(codigo)
    receptores = set(_NOMBRES_REGLA)
    contenedores: set[str] = set()

    # Propagación hasta punto fijo:
    # - `for r in rules_data.get("reglas", [])` y `for r in reglas` marcan el
    #   destino como receptor de regla;
    # - `reglas = rules_data.get("reglas", [])` recuerda el contenedor, para
    #   que un `for` posterior sobre esa variable también cuente (L-11);
    # - `alias = rule` propaga el receptor.
    cambiado = True
    while cambiado:
        cambiado = False
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.For):
                if _itera_contenedor_de_reglas(nodo.iter, contenedores):
                    cambiado |= _agregar_nombres([nodo.target], receptores)
            elif isinstance(nodo, ast.Assign):
                cambiado |= _propagar_asignacion(
                    nodo.value, list(nodo.targets), receptores, contenedores
                )
            elif isinstance(nodo, ast.AnnAssign) and nodo.value is not None:
                cambiado |= _propagar_asignacion(
                    nodo.value, [nodo.target], receptores, contenedores
                )

    claves: set[str] = set()
    for nodo in ast.walk(arbol):
        receptor: ast.AST | None = None
        argumentos: list[ast.AST] = []
        if (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "get"
        ):
            receptor = nodo.func.value
            argumentos = nodo.args
        elif isinstance(nodo, ast.Subscript):
            receptor = nodo.value
            argumentos = [nodo.slice]
        if receptor is None or not _es_receptor_de_regla(receptor, receptores):
            continue
        if (
            argumentos
            and isinstance(argumentos[0], ast.Constant)
            and isinstance(argumentos[0].value, str)
        ):
            claves.add(argumentos[0].value)
    return claves


def _claves_de_regla_leidas(ruta: Path) -> set[str]:
    """Claves de nivel de regla que el motor lee en `ruta`."""
    return _claves_de_regla_en_fuente(ruta.read_text(encoding="utf-8"))


def test_el_guard_de_claves_no_depende_del_nombre_ni_de_las_comillas():
    """L-7: el guard detecta comillas simples, `self.rule` y variables renombradas."""
    codigo = """
for r in rules_data.get("reglas", []):
    r.get('valor_esperado')
    r["ubicacion"]
self.rule.get('cita')
alias = r
alias.get("fuente")
"""
    assert _claves_de_regla_en_fuente(codigo) == {
        "valor_esperado",
        "ubicacion",
        "cita",
        "fuente",
    }


def test_el_guard_detecta_reglas_extraidas_a_una_variable():
    """L-11: extraer la lista a una variable no oculta las claves del `for`."""
    codigo = """
reglas = rules_data.get("reglas", [])
for r in reglas:
    r.get("clave_nueva")
"""
    assert _claves_de_regla_en_fuente(codigo) == {"clave_nueva"}


def test_el_guard_detecta_reglas_extraidas_por_subindice():
    """L-11: la variante con subíndice y destino renombrado también se detecta."""
    codigo = """
reglas = rules_data["rules"]
for rule in reglas:
    rule["otra_clave"]
"""
    assert _claves_de_regla_en_fuente(codigo) == {"otra_clave"}


def test_el_guard_ignora_cadenas_que_no_son_el_contenedor_de_reglas():
    """L-12: una constante "rules"/"reglas" que no es la clave no marca receptor.

    Antes, cualquier cadena "reglas"/"rules" dentro del iterable hacía que el
    destino se tratara como diccionario de regla y generaba un falso positivo.
    """
    codigo = """
for x in config.get("otra", "rules"):
    x.get("clave")
for y in algo("reglas"):
    y.get("otra")
"""
    assert _claves_de_regla_en_fuente(codigo) == set()


def test_claves_de_regla_sincronizadas_con_el_motor():
    """Toda clave de regla que el motor lee debe estar en `_CLAVES_VALIDAS`.

    El linter rechaza como error de carga cualquier clave de nivel de regla
    que no conozca. Si el motor empieza a leer una clave nueva y no se añade
    al conjunto cerrado, las reglas que la usen se caerían con un 500. Este
    test compara `_CLAVES_VALIDAS` con las claves que leen `compilador.py` y
    `engine.py`.
    """
    from validator.dsl_check import _CLAVES_VALIDAS

    raiz = Path(__file__).resolve().parent.parent / "validator"
    leidas: set[str] = set()
    for archivo in ("compilador.py", "engine.py"):
        leidas |= _claves_de_regla_leidas(raiz / archivo)

    faltantes = leidas - _CLAVES_VALIDAS
    assert not faltantes, f"claves leídas por el motor fuera del linter: {sorted(faltantes)}"


def test_secciones_del_linter_sincronizadas_con_el_compilador():
    """M-B: el linter y el compilador conocen el MISMO conjunto de secciones.

    Si el linter conoce una sección que el compilador ya no (deriva A), la
    regla compila a 0 analizadores y desaparece del reporte sin error; si es
    al revés (deriva B), la regla revienta con `DSLValidationError` y la API
    devuelve un 500 global. Comparar los conjuntos convierte la deriva futura
    en un fallo de test.
    """
    from validator import compilador, dsl_check

    assert set(dsl_check._SECCIONES) == set(compilador.SECCIONES_ANALIZADOR)
