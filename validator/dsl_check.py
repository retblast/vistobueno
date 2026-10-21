"""Linter del DSL de reglas (F4).

Valida la configuración de las reglas en TIEMPO DE CARGA: un error de
configuración debe fallar al COMPILAR, no al ejecutar contra un documento.

Detecta:
- regex inválida en cualquier campo `patron`/`filtro`;
- `comparacion` de atributo (eq/all_eq/contains) sin `esperado` o sin
  `atributo`;
- estados inalcanzables en autómatas (`automata_pila`) y estados
  duplicados / esquema vacío en `automata_secuencia`;
- ciclos épsilon (transiciones que no consumen y forman un ciclo): riesgo
  de bucle infinito en el reconocedor greedy de DFA/PDA;
- contexto entre reglas: `aplicar_si` mal formado o apuntando a una clave
  que nadie expone, `expone` duplicado, y `expone` + `aplicar_si` en la
  misma regla;
- `aplicar_si` con un valor que no es un tipo documental declarado: la
  regla no aplicaría nunca y el semáforo quedaría verde sin comprobar;
- secciones mal escritas (la regla desaparecería del reporte en silencio);
- prefijos de namespace desconocidos en los XPath;
- `severidad` fuera del catálogo y `id` de regla duplicado.

El compilador invoca `linter_o_alzar` al principio de `compilar()`.
"""

from __future__ import annotations

import difflib
import re

# Las mismas secciones que conoce el compilador (sin importarlo para
# evitar una dependencia circular: compilador -> dsl_check).
_SECCIONES = (
    "atributo_xml",
    "presencia_xml",
    "patron_texto",
    "lista_texto",
    "imagen",
    "automata_secuencia",
    "gramatica_estructura",
    "automata_pila",
    "patron_cantidad",
    "conteo_nodos",
    "lista_obligatoria",
    "hipervinculo_texto",
    "paginacion",
    "nota_pie",
    "toc_apunta",
    "toc_numeracion",
    "deteccion_tipo",
    "extraccion",
)

# Campos interpretados como expresiones regulares por los analizadores.
_CAMPOS_REGEX = ("patron", "filtro", "regex_indice")

# Claves de nivel de REGLA (no de sección) que el motor reconoce. Cualquier
# otra clave es o una sección mal escrita o un error de configuración.
_CLAVES_REGLA = frozenset(
    {
        "id",
        "tipo",
        "descripcion",
        "severidad",
        "valor_esperado",
        "ubicacion",
        "fuente",
        "cita",
        "expone",
        "aplicar_si",
        "mecanismo_verificable",
    }
)

# Severidades válidas (las de `validator.models.Severity`).
_SEVERIDADES = frozenset({"error", "warning"})

# Prefijos de namespace que el extractor declara y que lxml puede resolver.
# Copia local de `validator.extractor.NS` para no introducir una dependencia
# circular (extractor -> ... -> dsl_check).
_PREFIXOS_NAMESPACE = frozenset({"w", "r", "a", "pic"})

# Ejes de XPath que llevan dos puntos y NO son prefijos de namespace.
# Se ignoran al validar prefijos: `following-sibling::w:p` es correcto.
_EJES_XPATH = frozenset(
    {
        "ancestor",
        "ancestor-or-self",
        "attribute",
        "child",
        "descendant",
        "descendant-or-self",
        "following",
        "following-sibling",
        "namespace",
        "parent",
        "preceding",
        "preceding-sibling",
        "self",
    }
)


class DSLValidationError(ValueError):
    """Error en tiempo de carga: el DSL no pasa el linter."""


def _regex_invalida(valor: str) -> str:
    try:
        re.compile(valor)
    except re.error as e:
        return str(e)
    return ""


def _escanear_regex(
    config: dict, hallazgos: list[str], rule_id: str, seccion: str, contexto: str = ""
) -> None:
    for clave in _CAMPOS_REGEX:
        valor = config.get(clave)
        if isinstance(valor, str) and valor:
            err = _regex_invalida(valor)
            if err:
                etiqueta = f"{seccion} ({contexto})" if contexto else seccion
                hallazgos.append(f"[{rule_id}] {etiqueta}: regex inválida en '{clave}': {err}")


def _lint_xml(config: dict, hallazgos: list[str], rule_id: str, seccion: str) -> None:
    comp = config.get("comparacion", "exists")
    if comp in ("eq", "all_eq", "contains"):
        if config.get("esperado") is None:
            hallazgos.append(f"[{rule_id}] {seccion}: 'comparacion: {comp}' requiere 'esperado'")
        if not config.get("atributo"):
            hallazgos.append(f"[{rule_id}] {seccion}: 'comparacion: {comp}' requiere 'atributo'")


def _lint_automata_secuencia(config: dict, hallazgos: list[str], rule_id: str) -> None:
    estados = config.get("estados", [])
    if not estados:
        hallazgos.append(f"[{rule_id}] automata_secuencia: sin 'estados'")
        return
    nombres = [e.get("nombre") for e in estados if isinstance(e, dict)]
    nombres_ok: list[str] = [n for n in nombres if isinstance(n, str)]
    duplicados = {n for n in nombres_ok if nombres_ok.count(n) > 1}
    if duplicados:
        hallazgos.append(f"[{rule_id}] automata_secuencia: estados duplicados {sorted(duplicados)}")
    # Esquema "solo opcional": tras omitir los opcionales no queda ningún
    # estado obligatorio -> el DFA no tendría estado de aceptación.
    obligatorios = [e for e in estados if not e.get("opcional")]
    if not obligatorios:
        hallazgos.append(
            f"[{rule_id}] automata_secuencia: todos los estados son opcionales "
            "(sin estado de aceptación)"
        )
    for e in estados:
        if isinstance(e, dict):
            if not e.get("nombre"):
                hallazgos.append(f"[{rule_id}] automata_secuencia: estado sin 'nombre'")
            _escanear_regex(e, hallazgos, rule_id, "automata_secuencia", e.get("nombre", ""))


def _lint_automata_pila(config: dict, hallazgos: list[str], rule_id: str) -> None:
    transiciones = config.get("transiciones", [])
    if not transiciones:
        hallazgos.append(f"[{rule_id}] automata_pila: sin 'transiciones'")
        return

    inicial = config.get("inicial", "__inicio__")
    aceptacion = config.get("aceptacion", [])
    aristas: list[tuple] = []
    for t in transiciones:
        if not isinstance(t, dict):
            hallazgos.append(f"[{rule_id}] automata_pila: transición inválida {t!r}")
            continue
        if not t.get("patron"):
            hallazgos.append(
                f"[{rule_id}] automata_pila: transición {t.get('desde', '?')} sin 'patron'"
            )
        _escanear_regex(t, hallazgos, rule_id, "automata_pila", t.get("desde", ""))
        if "desde" in t and "hacia" in t:
            aristas.append((t["desde"], t["hacia"], bool(t.get("consumir", True))))

    # Alcance: nodos alcanzables desde el inicial.
    alcanzables = set()
    pila_nodos = [inicial]
    while pila_nodos:
        s = pila_nodos.pop()
        if s in alcanzables:
            continue
        alcanzables.add(s)
        for desde, hacia, _ in aristas:
            if desde == s and hacia not in alcanzables:
                pila_nodos.append(hacia)
    todos = {s for a in aristas for s in (a[0], a[1])}
    no_alcanzables = sorted(todos - alcanzables)
    if no_alcanzables:
        hallazgos.append(f"[{rule_id}] automata_pila: estados inalcanzables {no_alcanzables}")
    acept_no_alcanzables = sorted((set(aceptacion) or set()) - alcanzables)
    if acept_no_alcanzables:
        hallazgos.append(
            f"[{rule_id}] automata_pila: aceptación inalcanzable {acept_no_alcanzables}"
        )

    # Ciclos épsilon: ciclos de transiciones que NO consumen -> el
    # reconocedor greedy iteraría sin avanzar la entrada.
    epsilon_ady: dict[str, list[str]] = {}
    for desde, hacia, consumir in aristas:
        if not consumir:
            epsilon_ady.setdefault(desde, []).append(hacia)
    visitados = set()
    en_pila = set()

    def _ciclo(nodo: str) -> bool:
        if nodo in en_pila:
            return True
        if nodo in visitados:
            return False
        visitados.add(nodo)
        en_pila.add(nodo)
        for vecino in epsilon_ady.get(nodo, []):
            if _ciclo(vecino):
                return True
        en_pila.remove(nodo)
        return False

    if any(_ciclo(n) for n in list(epsilon_ady)):
        hallazgos.append(
            f"[{rule_id}] automata_pila: ciclo de transiciones épsilon "
            "(no consumen -> riesgo de bucle infinito)"
        )


def _lint_contexto(rules: list[dict], hallazgos: list[str]) -> None:
    """Valida `expone` / `aplicar_si` de forma transversal.

    Necesita ver todas las reglas a la vez, porque una condición puede
    apuntar a una clave que expone otra regla cualquiera del archivo. Se
    recorre en dos pasadas: primero se recogen las claves expuestas y después
    se resuelven las condiciones, para que el orden en el YAML sea irrelevante
    (la evaluación también es en dos fases).
    """
    expuestas: dict[str, str] = {}  # clave -> rule_id que la expone
    for rule in rules:
        rule_id = rule.get("id", "<sin id>")
        # Se comprueba la PRESENCIA de la clave, no su valor: `expone:`
        # a secas se parsea como None y sería una condición inactiva
        # silenciosa. Es un error de configuración, no un "sin condición".
        declarada, expone = _expone_bruto(rule)

        if declarada:
            if not isinstance(expone, str) or not expone.strip():
                hallazgos.append(f"[{rule_id}] expone: debe ser un texto no vacío")
            elif expone in expuestas:
                hallazgos.append(
                    f"[{rule_id}] expone: la clave '{expone}' ya la expone "
                    f"[{expuestas[expone]}] (el contexto sería ambiguo)"
                )
            else:
                expuestas[expone] = rule_id
            if not any(s in rule for s in _SECCIONES):
                hallazgos.append(
                    f"[{rule_id}] expone: no declara ninguna sección de analizador, "
                    "así que nunca se ejecuta y nunca publica su clave"
                )
            if "aplicar_si" in rule:
                hallazgos.append(
                    f"[{rule_id}] expone y aplicar_si en la misma regla: "
                    "una regla no puede condicionarse a un valor que ella misma produce"
                )

    # Segunda pasada: las condiciones se validan contra el conjunto COMPLETO de
    # claves expuestas. La evaluación es en dos fases, así que una regla
    # condicionada puede declararse antes que la regla que produce su clave.
    tipos_declarados = _tipos_declarados(rules)
    for rule in rules:
        rule_id = rule.get("id", "<sin id>")
        if "aplicar_si" not in rule:
            continue
        aplicar_si = rule.get("aplicar_si")
        if not isinstance(aplicar_si, dict) or not aplicar_si:
            hallazgos.append(f"[{rule_id}] aplicar_si: debe ser un mapa clave -> valor no vacío")
            continue
        for clave in aplicar_si:
            if not isinstance(clave, str) or not clave.strip():
                hallazgos.append(f"[{rule_id}] aplicar_si: clave vacía o no textual")
            elif clave not in expuestas:
                hallazgos.append(
                    f"[{rule_id}] aplicar_si: '{clave}' no la expone ninguna regla; "
                    f"claves expuestas: {sorted(expuestas) or 'ninguna'}"
                )
        for clave, valor in aplicar_si.items():
            _lintar_valor_aplicar_si(valor, clave, hallazgos, rule_id)
            _lintar_valor_tipo_documento(valor, clave, tipos_declarados, hallazgos, rule_id)


def _tipos_declarados(rules: list[dict]) -> dict[str, set[str]]:
    """Claves de tipo documental y los tipos que cada una puede tomar.

    Solo las reglas con sección `deteccion_tipo` declaran tipos: su `expone`
    es la clave que publica el tipo detectado, y sus `firmas` enumeran los
    tipos válidos. Las demás claves expuestas no son de tipo documental y no
    se pueden contrastar contra un catálogo.
    """
    declarados: dict[str, set[str]] = {}
    for rule in rules:
        config = rule.get("deteccion_tipo")
        if not isinstance(config, dict):
            continue
        clave = config.get("expone")
        if not isinstance(clave, str) or not clave.strip():
            continue
        firmas = config.get("firmas")
        if not isinstance(firmas, list):
            continue
        tipos = {
            firma["tipo"]
            for firma in firmas
            if isinstance(firma, dict) and isinstance(firma.get("tipo"), str)
        }
        declarados.setdefault(clave, set()).update(tipos)
    return declarados


def _lintar_valor_tipo_documento(
    valor: object,
    clave: str,
    tipos_declarados: dict[str, set[str]],
    hallazgos: list[str],
    rule_id: str,
) -> None:
    """Comprueba que el valor de la condición sea un tipo documental válido.

    Una condición con un valor que no existe (`tinv_cuantitativa` en vez de
    `tinv_cuantitativo`) no casa con nada: la regla NO se aplica nunca, y
    el estudiante ve un semáforo verde sobre una comprobación que jamás se
    hizo. El linter ya detectaba la clave mal escrita; este cierra el caso
    del valor mal escrito.
    """
    validos = tipos_declarados.get(clave)
    if not validos:
        return
    if isinstance(valor, list):
        for v in valor:
            if isinstance(v, str) and v not in validos:
                hallazgos.append(
                    f"[{rule_id}] aplicar_si: '{v}' no es un tipo documental válido "
                    f"para '{clave}' (tipos declarados: {sorted(validos)})"
                )
    elif isinstance(valor, str) and valor not in validos:
        hallazgos.append(
            f"[{rule_id}] aplicar_si: '{valor}' no es un tipo documental válido "
            f"para '{clave}' (tipos declarados: {sorted(validos)})"
        )


def _lintar_valor_aplicar_si(valor: object, clave: str, hallazgos: list[str], rule_id: str) -> None:
    """Valida el valor de una condición: escalar o lista de aceptados.

    Un escalar puede ser cualquier tipo (en la práctica siempre son cadenas
    de ids de tipo documental). Una lista debe ser no vacía y de escalares:
    una lista vacía no casaría con nada y dejaría la regla muerta, que es
    justo el silencio que se quiere evitar.
    """
    if isinstance(valor, list):
        if not valor:
            hallazgos.append(
                f"[{rule_id}] aplicar_si: '{clave}' tiene una lista vacía, "
                "así que la regla nunca aplicaría"
            )
        elif not all(isinstance(v, (str, int, float, bool)) for v in valor):
            hallazgos.append(f"[{rule_id}] aplicar_si: '{clave}' solo admite escalares en la lista")
    elif valor is None:
        hallazgos.append(
            f"[{rule_id}] aplicar_si: '{clave}' no declara valor, "
            "así que la condición quedaría inactiva"
        )


def _expone_bruto(rule: dict) -> tuple[bool, object]:
    """`(declarada, valor)` de la clave que la regla publica.

    La clave puede declararse a nivel de regla o dentro de la sección del
    analizador que produce el valor (`deteccion_tipo` lo hace así). Si
    apareciera en ambos sitios, manda la sección.
    """
    for seccion in _SECCIONES:
        cfg = rule.get(seccion)
        if isinstance(cfg, dict) and "expone" in cfg:
            return True, cfg.get("expone")
    if "expone" in rule:
        return True, rule.get("expone")
    return False, None


def _expone_de(rule: dict) -> str | None:
    """Clave válida que publica la regla, o None si no declara o no es válida."""
    declarada, valor = _expone_bruto(rule)
    if declarada and isinstance(valor, str) and valor.strip():
        return valor
    return None


def _lint_deteccion_tipo(
    config: dict, hallazgos: list[str], rule_id: str, rule: dict | None = None
) -> None:
    """Valida la sección `deteccion_tipo`.

    Además de lo específico de la sección, comprueba que la regla publique una
    clave: una detección que no expone nada no sirve de nada, y es un error
    silencioso fácil de cometer.
    """
    if _expone_de(rule if rule is not None else config) is None:
        hallazgos.append(
            f"[{rule_id}] deteccion_tipo: falta 'expone' (la clave que publica "
            "el tipo detectado, para que las reglas de estructura la consulten)"
        )

    minimo_global = config.get("minimo_global", 1)
    if not isinstance(minimo_global, int) or minimo_global < 1:
        hallazgos.append(f"[{rule_id}] deteccion_tipo: 'minimo_global' debe ser un entero >= 1")

    firmas = config.get("firmas")
    if not isinstance(firmas, list) or not firmas:
        hallazgos.append(f"[{rule_id}] deteccion_tipo: 'firmas' debe ser una lista no vacía")
        return

    vistos: set[str] = set()
    for firma in firmas:
        if not isinstance(firma, dict):
            hallazgos.append(f"[{rule_id}] deteccion_tipo: firma inválida {firma!r}")
            continue
        tipo = firma.get("tipo")
        if not isinstance(tipo, str) or not tipo.strip():
            hallazgos.append(f"[{rule_id}] deteccion_tipo: firma sin 'tipo'")
        elif tipo in vistos:
            hallazgos.append(
                f"[{rule_id}] deteccion_tipo: tipo '{tipo}' repetido en 'firmas' "
                "(el orden de especificidad dejaría de estar definido)"
            )
        else:
            vistos.add(tipo)

        evidencia = firma.get("evidencia")
        if not isinstance(evidencia, list) or not evidencia:
            hallazgos.append(
                f"[{rule_id}] deteccion_tipo: firma '{tipo}' necesita 'evidencia' no vacía"
            )
        elif not all(isinstance(e, str) and e.strip() for e in evidencia):
            hallazgos.append(
                f"[{rule_id}] deteccion_tipo: firma '{tipo}' tiene 'evidencia' no textual"
            )

        minimo = firma.get("minimo", 1)
        if not isinstance(minimo, int) or minimo < 1:
            hallazgos.append(f"[{rule_id}] deteccion_tipo: firma '{tipo}' necesita 'minimo' >= 1")
        elif isinstance(minimo_global, int) and minimo < minimo_global:
            hallazgos.append(
                f"[{rule_id}] deteccion_tipo: firma '{tipo}' tiene 'minimo' {minimo} "
                f"por debajo de 'minimo_global' {minimo_global}"
            )
        if isinstance(evidencia, list) and isinstance(minimo, int) and minimo > len(evidencia):
            hallazgos.append(
                f"[{rule_id}] deteccion_tipo: firma '{tipo}' exige {minimo} firmas pero "
                f"declara {len(evidencia)}: nunca puede cumplirse"
            )

    declaracion = config.get("declaracion")
    if declaracion is not None:
        if not isinstance(declaracion, dict):
            hallazgos.append(f"[{rule_id}] deteccion_tipo: 'declaracion' debe ser un mapa")
        else:
            etiquetas = declaracion.get("etiquetas")
            if not isinstance(etiquetas, dict) or not etiquetas:
                hallazgos.append(
                    f"[{rule_id}] deteccion_tipo: 'declaracion.etiquetas' debe mapear cada tipo "
                    "a sus etiquetas del Anexo 10 (sin ellas el nivel 1 nunca dispara)"
                )
            else:
                for tipo, alias in etiquetas.items():
                    if tipo not in vistos:
                        hallazgos.append(
                            f"[{rule_id}] deteccion_tipo: 'declaracion.etiquetas' declara el tipo "
                            f"'{tipo}', que no aparece en 'firmas'"
                        )
                    if not isinstance(alias, list) or not all(
                        isinstance(a, str) and a.strip() for a in alias
                    ):
                        hallazgos.append(
                            f"[{rule_id}] deteccion_tipo: 'declaracion.etiquetas[{tipo}]' "
                            "debe ser una lista de textos no vacíos"
                        )


def _lint_lista_obligatoria(config: dict, hallazgos: list[str], rule_id: str) -> None:
    """Valida la sección `lista_obligatoria`.

    `items` debe ser una lista no vacía: una lista vacía no comprueba nada y
    la regla pasaría siempre (falso verde silencioso).
    """
    items = config.get("items")
    if not isinstance(items, list) or not items:
        hallazgos.append(
            f"[{rule_id}] lista_obligatoria: 'items' debe ser una lista no vacía "
            "(si no, la regla no comprueba nada y pasa siempre)"
        )
    elif not all(isinstance(it, str) and it.strip() for it in items):
        hallazgos.append(f"[{rule_id}] lista_obligatoria: 'items' solo admite textos no vacíos")


def _lint_paginacion(config: dict, hallazgos: list[str], rule_id: str) -> None:
    """Valida la sección `paginacion`.

    `xpaths` debe traer al menos 2 entradas: la sección compara la página
    física de los párrafos objetivo, así que con menos no hay nada que
    comparar y la regla no puede sino fallar.
    """
    xpaths = config.get("xpaths")
    if not isinstance(xpaths, list) or len(xpaths) < 2:
        hallazgos.append(
            f"[{rule_id}] paginacion: 'xpaths' debe ser una lista con al menos 2 "
            "entradas (la regla compara la página física de los párrafos objetivo)"
        )
    elif not all(isinstance(x, str) and x.strip() for x in xpaths):
        hallazgos.append(f"[{rule_id}] paginacion: 'xpaths' solo admite textos no vacíos")


def _prefijos_de_xpath(xpath: str) -> set[str]:
    """Prefijos de namespace usados en un XPath.

    Se ignoran los ejes (`following-sibling::w:p`), que también llevan dos
    puntos pero no son prefijos: confundirlos daría falsos positivos.
    """
    prefijos: set[str] = set()
    for coincidencia in re.finditer(r"([A-Za-z_][\w.-]*):", xpath):
        candidato = coincidencia.group(1)
        if candidato in _EJES_XPATH:
            continue
        prefijos.add(candidato)
    return prefijos


def _lint_xpath(config: dict, hallazgos: list[str], rule_id: str, seccion: str) -> None:
    """Valida que los prefijos de namespace de un XPath existan.

    Un XPath con un prefijo desconocido (`//wp:ind`) no lo detecta lxml al
    parsear el YAML: revienta al EVALUAR contra el documento, con un
    `XPathEvalError` que la API muestra al estudiante como si fuera un
    defecto de su tesis. Con el linter, el error aparece al cargar las
    reglas, que es donde pertenece.
    """
    valores: list[str] = []
    xpath = config.get("xpath")
    if isinstance(xpath, str):
        valores.append(xpath)
    xpaths = config.get("xpaths")
    if isinstance(xpaths, list):
        valores.extend(x for x in xpaths if isinstance(x, str))
    for valor in valores:
        for prefijo in sorted(_prefijos_de_xpath(valor)):
            if prefijo not in _PREFIXOS_NAMESPACE:
                hallazgos.append(
                    f"[{rule_id}] {seccion}: prefijo de namespace desconocido "
                    f"'{prefijo}' en el XPath '{valor}' "
                    f"(prefijos válidos: {sorted(_PREFIXOS_NAMESPACE)})"
                )


def _lint_severidad(config: dict, hallazgos: list[str], rule_id: str) -> None:
    """Valida el campo `severidad` de la regla.

    `Severity(...)` se construye al EVALUAR: una severidad mal escrita
    reventaba en runtime, con el estudiante esperando el resultado. Se
    comprueba al cargar, donde el error es de configuración y no del
    documento.
    """
    severidad = config.get("severidad")
    if severidad is None:
        return
    if not isinstance(severidad, str) or severidad not in _SEVERIDADES:
        hallazgos.append(
            f"[{rule_id}] severidad: '{severidad}' no es válida "
            f"(valores admitidos: {sorted(_SEVERIDADES)})"
        )


def _lint_secciones_desconocidas(rules: list[dict], hallazgos: list[str]) -> None:
    """Detecta secciones mal escritas y reglas que no declaran ninguna.

    Una sección mal escrita (por ejemplo `atributo_xmls` en vez de
    `atributo_xml`) no la reconoce el compilador: la regla se salta en
    silencio y DESAPARECE del reporte sin ningún aviso. Para el estudiante
    eso es indistinguishable de "cumplió la regla".

    Se distinguen tres situaciones:
    - la clave parece una sección (comparación difusa) → se sugiere la
      correcta, que es el error más probable;
    - la clave no se parece a nada conocido → se descarta, porque el DSL
      admite campos propios de cada analizador;
    - la regla no declara ninguna sección → se descarta, porque las reglas
      no mecanizadas son legítimas (el campo `mecanismo_verificable` las
      marca).
    """
    for rule in rules:
        rule_id = rule.get("id", "<sin id>")
        for clave in rule:
            if clave in _SECCIONES or clave in _CLAVES_REGLA:
                continue
            cercania = difflib.get_close_matches(clave, _SECCIONES, n=1, cutoff=0.75)
            if cercania:
                hallazgos.append(
                    f"[{rule_id}] sección desconocida '{clave}' (¿quiso decir '{cercania[0]}'?)"
                )


def _lint_ids_duplicados(rules: list[dict], hallazgos: list[str]) -> None:
    """Detecta ids de regla repetidos.

    Un id duplicado hace que dos reglas compartan identificador: el
    estudiante ve dos observaciones indistinguibles con el mismo id, y el
    resumen cuenta la misma regla dos veces.
    """
    vistos: dict[str, int] = {}
    duplicados: set[str] = set()
    for rule in rules:
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            continue
        if rule_id in vistos:
            duplicados.add(rule_id)
        vistos[rule_id] = vistos.get(rule_id, 0) + 1
    for rule_id in sorted(duplicados):
        hallazgos.append(
            f"[{rule_id}] id duplicado: aparece {vistos[rule_id]} veces en el archivo "
            "(las reglas deben tener identificadores únicos)"
        )


def linter(rules_data: dict) -> list[str]:
    """Devuelve la lista de hallazgos (vacía si el DSL está sano)."""
    hallazgos: list[str] = []
    rules = rules_data.get("reglas", [])
    for rule in rules:
        rule_id = rule.get("id", "<sin id>")
        _lint_severidad(rule, hallazgos, rule_id)
        for seccion in _SECCIONES:
            cfg = rule.get(seccion)
            if cfg is None:
                continue
            configs = cfg if isinstance(cfg, list) else [cfg]
            for c in configs:
                if not isinstance(c, dict):
                    continue
                _escanear_regex(c, hallazgos, rule_id, seccion)
                if seccion in ("atributo_xml", "presencia_xml"):
                    _lint_xml(c, hallazgos, rule_id, seccion)
                elif seccion == "automata_secuencia":
                    _lint_automata_secuencia(c, hallazgos, rule_id)
                elif seccion == "automata_pila":
                    _lint_automata_pila(c, hallazgos, rule_id)
                elif seccion == "deteccion_tipo":
                    _lint_deteccion_tipo(c, hallazgos, rule_id, rule)
                elif seccion == "lista_obligatoria":
                    _lint_lista_obligatoria(c, hallazgos, rule_id)
                elif seccion == "paginacion":
                    _lint_paginacion(c, hallazgos, rule_id)
                _lint_xpath(c, hallazgos, rule_id, seccion)
    _lint_contexto(rules, hallazgos)
    _lint_secciones_desconocidas(rules, hallazgos)
    _lint_ids_duplicados(rules, hallazgos)
    return hallazgos


def linter_o_alzar(rules_data: dict) -> None:
    """Levanta `DSLValidationError` si el DSL tiene errores de carga."""
    hallazgos = linter(rules_data)
    if hallazgos:
        detalle = "\n  - ".join(hallazgos)
        raise DSLValidationError(f"{len(hallazgos)} error(es) de configuración DSL:\n  - {detalle}")
