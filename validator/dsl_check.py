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
  misma regla.

El compilador invoca `linter_o_alzar` al principio de `compilar()`.
"""

from __future__ import annotations

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
)

# Campos interpretados como expresiones regulares por los analizadores.
_CAMPOS_REGEX = ("patron", "filtro", "regex_indice")


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


def linter(rules_data: dict) -> list[str]:
    """Devuelve la lista de hallazgos (vacía si el DSL está sano)."""
    hallazgos: list[str] = []
    rules = rules_data.get("reglas", [])
    for rule in rules:
        rule_id = rule.get("id", "<sin id>")
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
    _lint_contexto(rules, hallazgos)
    return hallazgos


def linter_o_alzar(rules_data: dict) -> None:
    """Levanta `DSLValidationError` si el DSL tiene errores de carga."""
    hallazgos = linter(rules_data)
    if hallazgos:
        detalle = "\n  - ".join(hallazgos)
        raise DSLValidationError(f"{len(hallazgos)} error(es) de configuración DSL:\n  - {detalle}")
