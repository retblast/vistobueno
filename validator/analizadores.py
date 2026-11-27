"""Analizadores de hoja para el DSL declarativo.

Definen la clase base `Analizador` y los analizadores atómicos:
- AnalizadorXML: atributos y presencia de nodos XML (xpath).
- AnalizadorRegex: patrones de texto sobre el contenido del documento.
- AnalizadorLista: pertenencia a una lista de valores permitidos.
- AnalizadorConteoNodos: contador genérico de nodos / párrafos (conteo_nodos).
- AnalizadorImagen: presencia de imágenes (blips) — subclase del anterior.
- AnalizadorCantidadPatron: cuenta palabras/matches/entradas (patron_cantidad).
- AnalizadorListaObligatoria: ítems obligatorios en una sección (lista_obligatoria).
- AnalizadorHipervinculo: hipervínculos que matchean un patrón (hipervinculo_texto).
- AnalizadorTocApunta: entradas del índice apuntan a secciones reales (toc_apunta).
- AnalizadorTocNumeracion: jerarquía de numeración del índice (toc_numeracion).

Los analizadores de tipo compuesto (secuencia, gramática, pila) viven en
`automata.py`; la clase base `Analizador` los integra a todos.

A diferencia del `checks.py` legacy (que opera sobre una regla completa
`{"checks": [...]}`), los analizadores del DSL reciben **una sola**
comprobación declarada y la ejecutan de forma autocontenida. Esto los
hace componibles y testables por separado.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from . import orcid
from .detalle import (
    detalle_jerarquia,
    detalle_lista_acotada,
    detalle_texto_lista,
    detalle_texto_regex,
    detalle_xml_atributo,
    detalle_xml_presencia,
    evaluar_atributo,
)
from .dsl_check import DSLValidationError
from .extractor import (
    NS,
    PAGINA_DESCONOCIDA,
    PAGINA_ESTIMADA,
    CicloEstilosError,
    ExtractedDocx,
    W,
    text_of,
)
from .tokenizer import PARRAFO, TITULO, es_heading, seccion, solo, tokenizar

# Prefijos de namespace para resolver names en atributos (ej. "@w:val").
PREFIX_NS = NS

# Atributo `r:id` de `w:hyperlink` (relación con el destino del enlace).
_R_ID = "{" + NS["r"] + "}id"

AUSENTE = "(ausente)"
"""Centinela de una propiedad de formato que no aparece en ninguna capa.

No se omite del muestreo: una propiedad ausente no cumple lo esperado (M1 /
VA-02). Los toggles OOXML (`w:b`) no usan el centinela porque Word los
considera apagados por defecto y el resolvedor devuelve `"0"`."""


def _resolve_attr_key(atributo: str) -> str:
    """Convierte '@w:val' en '{namespace}val' para lxml .get()."""
    name = atributo[1:]
    if ":" in name:
        prefix, local = name.split(":", 1)
        if prefix in PREFIX_NS:
            return "{" + PREFIX_NS[prefix] + "}" + local
    return name


class ConfigurationError(DSLValidationError):
    """Error de configuración de un analizador DSL.

    Se lanza al compilar una regla con parámetros inválidos (p. ej.
    `lista_obligatoria` sin ítems o `paginacion` sin suficientes xpaths).
    Es un error del motor, no del documento: no debe aparecer como fallo
    del estudiante en el reporte.

    Hereda de `DSLValidationError` (y no directamente de `ValueError`) para
    que la API lo traduzca a un 500 de configuración y no al 422 que culpa
    al archivo del estudiante: `api.validar` captura `DSLValidationError`
    antes del `except ValueError` genérico.
    """


class Analizador(ABC):
    """Interfaz común de todos los analizadores del DSL.

    Cada analizador se construye a partir de la configuración declarada
    en una sección del YAML (p. ej. `analizador_xml`, `patron_texto`) y
    ejecuta `analizar(extracted)` para producir (pasó, detalle).
    """

    def __init__(self, config: dict):
        if config is not None and not isinstance(config, dict):
            raise ConfigurationError(
                "configuración de analizador inválida: se esperaba un diccionario "
                f"y se recibió {type(config).__name__}"
            )
        self.config = config or {}
        # Nodo objetivo (párrafo/subnodo) que determinó la última ejecución.
        # Permite que el motor enriquezca `location` con "página N" (ítem 1).
        self.ultimo_nodo: object | None = None
        # Valor legible por maquina de la ultima ejecucion, cuando el
        # analizador produce uno. `analizar()` devuelve texto pensado para
        # personas, asi que no sirve para decidir condiciones `aplicar_si`.
        # Los analizadores de deteccion lo rellenan; los demas lo dejan None.
        self.valor: str | None = None
        # Datos capturados para la ficha de depósito (diseño 17). Cada item es
        # `{"campo": str, "valor": str | list[str], "nodo": nodo | None}`; el
        # compilador resuelve la página con `extracted.pagina_de(nodo)`. Solo
        # `AnalizadorExtraccion` y los analizadores con `extraccion` anidada lo
        # rellenan.
        self.ficha: list[dict] = []
        # Marca que el analizador determinó que la regla NO APLICA a este
        # documento (p. ej. `n_a_si_sin_nodos` o `n_a_si_ausente`). El
        # compilador la usa para devolver `aplicable=False` en vez de un
        # "cumple" engañoso (AUD-07).
        self.no_aplica = False

    @abstractmethod
    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]: ...

    # -- utilidades compartidas -------------------------------------------
    def _nodos(self, extracted: ExtractedDocx, parte: str, contexto: str):
        # Consulta XPath con cache (F4): mismo (parte, contexto, xpath) se
        # evalúa una sola vez por documento.
        nodos = extracted.xpath(parte, self.config.get("xpath", ""), contexto)
        self.ultimo_nodo = nodos[0] if nodos else None
        return nodos


class AnalizadorXML(Analizador):
    """Verifica atributos o presencia de nodos vía XPath.

    Se usa para los DSL `atributo_xml` y `presencia_xml`.
    """

    # En secciones landscape Word rota el par de márgenes opuestos
    # (bottom<->left y top<->right) para que el empaste siga en el mismo
    # borde físico. Al comparar un margen en una sección landscape se usa el
    # valor del atributo rotado (handover issue #2).
    _ROTACION_MARGEN = {
        "@w:top": "@w:right",
        "@w:right": "@w:top",
        "@w:bottom": "@w:left",
        "@w:left": "@w:bottom",
    }

    # El papel A4 se compara por sus lados físico (21 x 29.7 cm), no por la
    # orientación: en landscape Word guarda `w:w=16838` y `w:h=11906`. Se
    # normaliza con el lado corto y el largo, sin depender de `w:orient`
    # (los conversores desde PDF suelen omitirlo).
    _ATRIBUTOS_PAPEL = ("@w:w", "@w:h")

    def _valor_margen(self, extracted, node, atributo, key):
        """Valor de `atributo` normalizado para la orientación de la sección."""
        if atributo in self._ROTACION_MARGEN and extracted.es_seccion_landscape(node):
            key = _resolve_attr_key(self._ROTACION_MARGEN[atributo])
        return node.get(key)

    def _valor_atributo(self, extracted, node, atributo, key):
        """Valor leído con la normalización que corresponda al nodo."""
        if node.tag == W + "pgSz":
            return self._valor_papel(node, atributo, key)
        return self._valor_margen(extracted, node, atributo, key)

    def _valor_papel(self, node, atributo, key):
        """Lado corto/largo de `w:pgSz`, sin importar la orientación.

        `@w:w` compara siempre el lado corto (11906 twips) y `@w:h` el lado
        largo (16838). Así una sección A4 horizontal legítima pasa igual que
        una vertical, y una sección con papel Letter sigue fallando en
        cualquier orientación.
        """
        if atributo not in self._ATRIBUTOS_PAPEL or node.tag != W + "pgSz":
            return node.get(key)
        ancho = node.get(W + "w")
        alto = node.get(W + "h")
        if ancho is None or alto is None:
            return node.get(key)
        try:
            corto, largo = sorted((int(ancho), int(alto)))
        except ValueError:
            return node.get(key)
        return str(corto if atributo == "@w:w" else largo)

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        comp = self.config.get("comparacion", "exists")
        self.no_aplica = False

        try:
            nodes = self._nodos(extracted, parte, contexto)
        except ValueError:
            # La parte no existe (p. ej. tesis sin header*.xml): si la regla
            # declara `n_a_si_ausente`, el incumplimiento no aplica (n/a).
            if self.config.get("n_a_si_ausente"):
                self.no_aplica = True
                return True, f"no aplica (parte '{parte}' ausente)"
            raise

        # Presencia simple
        if comp in ("exists", "not_exists"):
            if comp == "exists":
                return len(nodes) > 0, detalle_xml_presencia(comp, len(nodes), [])
            # `not_exists` incumplido: los nodos encontrados son los
            # culpables. Se señala el primero (para la ubicación de la regla)
            # y el detalle los nombra por posición.
            if nodes:
                self.ultimo_nodo = nodes[0]
            incumplidos = [(i, extracted.pagina_de(n)) for i, n in enumerate(nodes, 1)]
            return (
                not nodes,
                detalle_xml_presencia(comp, len(nodes), incumplidos),
            )

        # Sin nodos no hay atributo que comparar. `n_a_si_sin_nodos` permite
        # declarar que la regla no aplica (p. ej. una línea de carátula que
        # solo existe en cierto tipo de título), en vez de fallar con
        # `@w:val=[] esperado=...` (AUD-07).
        if not nodes and self.config.get("n_a_si_sin_nodos"):
            self.no_aplica = True
            return True, "no aplica (sin nodos)"

        # Atributo
        atributo = self.config.get("atributo")
        esperado = self.config.get("esperado")
        if atributo is None:
            return False, "falta 'atributo' para comparación de atributo"
        key = _resolve_attr_key(atributo)
        # pares conserva la posición (1-based) de cada nodo en el resultado
        # del xpath: al fallar es lo que permite señalar QUÉ valor incumple,
        # con su página, en vez de mostrar solo los primeros 3 (que suelen
        # ser los conformes y esconden al culpable — handover issue #7 /
        # AUD-03).
        pares = [
            (i, n, self._valor_atributo(extracted, n, atributo, key))
            for i, n in enumerate(nodes, 1)
        ]
        vals = [v for _, _, v in pares if v is not None]
        self.valor = vals[0] if vals else None
        tolerancia = self.config.get("tolerancia")

        if comp not in ("eq", "all_eq", "contains"):
            return False, f"comparación '{comp}' no soportada"
        # La comparación (veredicto + lista de incumplimientos) la resuelve
        # el módulo compartido: así el detalle no puede contradecir al
        # semáforo (una regla que falla siempre tiene un culpable nombrado).
        con_pagina = [(i, v, extracted.pagina_de(n)) for i, n, v in pares]
        ok, incumplimientos = evaluar_atributo(self.config, con_pagina)
        if incumplimientos:
            # La ubicación de la regla debe apuntar al primer nodo CULPABLE
            # (AUD-03), no al primero que devolvió el xpath.
            posiciones = {i for i, _, _ in incumplimientos}
            culpables = [n for i, n, _ in pares if i in posiciones]
            if culpables:
                self.ultimo_nodo = culpables[0]
        detalle = detalle_xml_atributo(self.config, vals, incumplimientos, esperado, tolerancia)
        return ok, detalle


class AnalizadorFormato(Analizador):
    """Resuelve el formato efectivo de los runs o párrafos sujetos a la regla.

    La sección `formato_efectivo` selecciona primero los párrafos con
    `parrafo_xpath` (respetando `parte`/`contexto`) y después resuelve, para
    cada sujeto, el valor efectivo de `propiedad` con
    `ExtractedDocx.formato_efectivo`: formato directo → estilo de carácter →
    cadena `basedOn` del estilo de párrafo → `docDefaults` (M1 / VA-01,
    VA-02).

    - `sujeto: run` (por defecto) evalúa **todos los runs con texto** de cada
      párrafo, incluidos los que viven dentro de un hipervínculo. Un run sin
      texto no aporta un valor y no se usa para eximir al párrafo.
    - `sujeto: parrafo` evalúa el párrafo (propiedades de `w:pPr`, como
      `w:jc` o `w:spacing`).

    Una propiedad que no aparece en ninguna capa se compara como
    `AUSENTE`, de modo que cuenta como incumplimiento. La comparación
    recomendada es `all_eq`: `eq` solo miraría el primer sujeto y repetiría
    el defecto de VA-01.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        sujeto = self.config.get("sujeto", "run")
        parrafo_xpath = self.config.get("parrafo_xpath")
        propiedad = self.config.get("propiedad")
        self.no_aplica = False

        if not parrafo_xpath or not isinstance(parrafo_xpath, str):
            raise ConfigurationError("formato_efectivo: falta 'parrafo_xpath'")
        if not propiedad or not isinstance(propiedad, str):
            raise ConfigurationError("formato_efectivo: falta 'propiedad'")
        if sujeto not in ("run", "parrafo"):
            raise ConfigurationError(
                f"formato_efectivo: 'sujeto' debe ser 'run' o 'parrafo' (se recibió {sujeto!r})"
            )

        try:
            parrafos = extracted.xpath(parte, parrafo_xpath, contexto)
        except ValueError:
            if self.config.get("n_a_si_ausente"):
                self.no_aplica = True
                return True, f"no aplica (parte '{parte}' ausente)"
            raise

        if not parrafos:
            if self.config.get("n_a_si_sin_nodos"):
                self.no_aplica = True
                return True, "no aplica (sin nodos)"
            return False, f"sin valores que comparar: {parrafo_xpath}"

        sujetos = list(parrafos)
        if sujeto == "run":
            sujetos = []
            for parrafo in parrafos:
                for run in parrafo.xpath(".//w:r", namespaces=NS):
                    if any((t.text or "").strip() for t in run.iter(W + "t")):
                        sujetos.append(run)
            if not sujetos:
                # El párrafo existe pero no tiene texto: no hay formato que
                # demostrar. No se da por bueno (sería eximir en silencio).
                return False, "sin runs con texto que evaluar"

        valores: list[tuple[int, object, int | None, object]] = []
        for pos, nodo in enumerate(sujetos, 1):
            try:
                valor = extracted.formato_efectivo(nodo, propiedad)
            except CicloEstilosError as e:
                # Un ciclo impide conocer el formato efectivo: se reporta
                # como incumplimiento en vez de tumbar la validación.
                self.ultimo_nodo = nodo
                return False, f"{propiedad}: {e}"
            valores.append(
                (pos, AUSENTE if valor is None else valor, extracted.pagina_de(nodo), nodo)
            )

        con_pagina = [(pos, valor, pagina) for pos, valor, pagina, _ in valores]
        ok, incumplimientos = evaluar_atributo(self.config, con_pagina)
        if incumplimientos:
            posiciones = {pos for pos, _, _ in incumplimientos}
            culpables = [n for pos, _, _, n in valores if pos in posiciones]
            if culpables:
                self.ultimo_nodo = culpables[0]

        esperado = self.config.get("esperado")
        tolerancia = self.config.get("tolerancia")
        # Config sintética para el formateador compartido: `xpath` decide la
        # unidad (w:sz → puntos, w:ind → cm) y `atributo` es la etiqueta.
        detalle_config = {
            "xpath": propiedad.split("/@", 1)[0],
            "atributo": propiedad,
            "esperado": esperado,
            "tolerancia": tolerancia,
        }
        detalle = detalle_xml_atributo(
            detalle_config,
            [valor for _, valor, _, _ in valores],
            incumplimientos,
            esperado,
            tolerancia,
        )
        return ok, detalle


class AnalizadorRegex(Analizador):
    """Aplica una expresión regular al contenido textual de nodos.

    `coincidencia`: `todos` (todos los nodos deben matchear, por defecto),
    `alguno` (al menos uno), `ninguno` (ninguno).

    `unidad`: `run` (por defecto) mide cada `w:t` por separado, como el
    motor legacy; `nodo` reúne con `text_of()` todo el texto del nodo
    seleccionado. Se usa cuando la propiedad es del bloque completo (p. ej.
    que el nombre del autor tenga mayúsculas y minúsculas) y Word lo parte
    en varios runs.
    """

    _UNIDADES = ("run", "nodo")

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        patron = self.config.get("patron", "")
        coincidencia = self.config.get("coincidencia", "todos")
        ignore_case = self.config.get("ignore_case", False)
        unidad = self.config.get("unidad", "run")
        if unidad not in self._UNIDADES:
            raise ConfigurationError(
                f"patron_texto: 'unidad' inválida '{unidad}' (admitidas: {self._UNIDADES})"
            )

        nodes = self._nodos(extracted, parte, contexto)
        if unidad == "nodo":
            # Un párrafo puede traer runs vacíos: no cuenta como texto, pero
            # tampoco exime a los demás nodos seleccionados.
            completos = [text_of(n) for n in nodes]
            textos = [texto for texto in completos if texto]
        else:
            textos = [t.text for n in nodes for t in n.iter(W + "t") if t.text]
        if not textos:
            return False, "sin nodos w:t que evaluar"

        flags = re.IGNORECASE if ignore_case else 0
        rx = re.compile(patron, flags)

        def _matchea(s: str) -> bool:
            c = self.config.get("comparacion", "regex")
            if c == "fullmatch":
                # Sin strip para preservar el comportamiento del motor legacy
                # (checks.run_check usa `patron.fullmatch` sobre el w:t tal cual).
                return bool(rx.fullmatch(s))
            return bool(rx.search(s))

        if coincidencia == "todos":
            incumplen = [(i, t) for i, t in enumerate(textos, 1) if not _matchea(t)]
            return not incumplen, detalle_texto_regex(textos, incumplen)
        if coincidencia == "alguno":
            ok = any(_matchea(t) for t in textos)
            return ok, f"textos={len(textos)} alguno_matchea={ok}"
        if coincidencia == "ninguno":
            ok = not any(_matchea(t) for t in textos)
            return ok, f"textos={len(textos)} ninguno_matchea={ok}"

        return False, f"coincidencia '{coincidencia}' no soportada"


class AnalizadorLista(Analizador):
    """Verifica que el texto de los nodos pertenezca a una lista permitida."""

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        lista = self.config.get("lista", [])
        ignore_case = self.config.get("ignore_case", False)

        nodes = self._nodos(extracted, parte, contexto)
        textos = [text_of(n).strip() for n in nodes if text_of(n).strip()]
        if not textos:
            return False, "sin nodos de texto que evaluar"

        def _norm(s: str) -> str:
            s = re.sub(r"\s+", " ", s).strip()
            return s.lower() if ignore_case else s

        valores = [_norm(t) for t in textos]
        permitidos = [_norm(x) for x in lista]
        incumplen = [(i, v) for i, v in enumerate(valores, 1) if v not in permitidos]
        return not incumplen, detalle_texto_lista(valores, incumplen)


class AnalizadorConteoNodos(Analizador):
    """Cuenta nodos (XPath), párrafos o entradas de una sección.

    Es el contador genérico para `conteo_nodos` (F3). Si la config lleva
    `seccion`, cuenta por defecto los PÁRRAFOS no vacíos de esa sección
    vía el tokenizer en lugar de XPath. Con `unidad: entrada` cuenta solo
    las entradas con patrón autor-año (NM-05): una continuación sin año
    no suma y el texto ajeno se ignora. No verifica APA ni la relación
    cita-referencia (REQ-50).
    """

    # Entrada bibliográfica reconocible por su patrón autor-año. Se exige
    # que el año entre paréntesis siga a una o varias palabras que empiezan
    # con mayúscula, para que la prosa con un año ("La revisión (2020) …")
    # no se cuente como referencia. Es una heurística de CONTEO, no un
    # validador de formato APA: se documenta como límite en la matriz REQ.
    _RE_ENTRADA = re.compile(
        r"^\s*(?:[A-ZÁÉÍÓÚÑ][\wáéíóúñÁÉÍÓÚÑ'’\-]*\.?[,\s]*){1,6}"
        r"\(\s*(?:1[6-9]|20)\d{2}[a-z]?\s*\)"
    )
    _UNIDADES = ("parrafo", "entrada")

    def _etiqueta(self) -> str:
        return self.config.get("label", "nodos")

    def _cuenta(self, extracted: ExtractedDocx) -> int:
        unidad = self.config.get("unidad", "parrafo")
        if unidad not in self._UNIDADES:
            raise ConfigurationError(
                f"conteo_nodos: 'unidad' inválida '{unidad}' (admitidas: {self._UNIDADES})"
            )
        sec = self.config.get("seccion")
        if sec:
            corte = seccion(tokenizar(extracted), sec["inicio"], sec.get("fin"))
            parrafos = [t.texto for t in corte if t.tipo == PARRAFO and t.texto.strip()]
            if unidad == "entrada":
                return sum(1 for p in parrafos if self._RE_ENTRADA.match(p))
            return len(parrafos)
        nodos = self._nodos(
            extracted,
            self.config.get("parte", "document"),
            self.config.get("contexto", "todos"),
        )
        return len(nodos)

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        minimo = self.config.get("cantidad_minima", 1)
        maximo = self.config.get("cantidad_maxima")
        multiples = self.config.get("cantidades_multiples")
        n = self._cuenta(extracted)
        etq = self._etiqueta()
        if multiples:
            # Se cumple si la cantidad alcanza CUALQUIER mínimo declarado
            # (p. ej. mínimo según tipo de investigación: [20, 30, 20]).
            ok = any(n >= m for m in multiples)
            return ok, f"{etq}={n} minimos={multiples}"
        rango = f"minimo={minimo}"
        if maximo is not None:
            rango += f" maximo={maximo}"
        if n < minimo:
            return False, f"{etq}={n} {rango}"
        if maximo is not None and n > maximo:
            return False, f"{etq}={n} {rango}"
        return True, f"{etq}={n} {rango}"


class AnalizadorImagen(AnalizadorConteoNodos):
    """Verifica la presencia, la cantidad y el tamaño de imágenes embebidas.

    Sin `ancho_cm`/`alto_cm` conserva la semántica del legacy
    `imagen_presencia` (checks.run_check): detalle `imagenes=N minimo=M`.
    Con ambos campos mide el `wp:extent` del dibujo que contiene cada blip
    (M7/VA-15): el ancho es `cx` y el alto `cy`, en EMU (360000 por cm).
    `contexto: caratula` limita la búsqueda a la primera sección, así que
    una imagen del cuerpo o del encabezado no satisface la carátula.
    """

    EMU_POR_CM = 360000

    def _etiqueta(self) -> str:
        return "imagenes"

    def _dimensiones(self, nodo) -> tuple[float, float] | None:
        contenedores = nodo.xpath("ancestor::wp:inline[1] | ancestor::wp:anchor[1]", namespaces=NS)
        if not contenedores:
            return None
        extent = contenedores[0].find(f"{{{NS['wp']}}}extent")
        if extent is None:
            return None
        try:
            cx = int(extent.get("cx", ""))
            cy = int(extent.get("cy", ""))
        except TypeError, ValueError:
            return None
        return cx / self.EMU_POR_CM, cy / self.EMU_POR_CM

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        ancho = self.config.get("ancho_cm")
        alto = self.config.get("alto_cm")
        if ancho is None and alto is None:
            return super().analizar(extracted)
        if ancho is None or alto is None:
            raise ConfigurationError("imagen: 'ancho_cm' y 'alto_cm' deben declararse juntos")

        ancho_esperado = float(ancho)
        alto_esperado = float(alto)
        tolerancia = float(self.config.get("tolerancia_cm", 0.1))
        minimo = self.config.get("cantidad_minima", 1)
        nodos = self._nodos(
            extracted,
            self.config.get("parte", "document"),
            self.config.get("contexto", "todos"),
        )
        if len(nodos) < minimo:
            return False, f"imagenes={len(nodos)} minimo={minimo}"
        maximo = self.config.get("cantidad_maxima")
        if maximo is not None and len(nodos) > maximo:
            return False, f"imagenes={len(nodos)} maximo={maximo}"

        medidas = [self._dimensiones(n) for n in nodos]
        esperado = f"{ancho_esperado:.2f}x{alto_esperado:.2f}±{tolerancia:.2f}cm"
        if any(m is None for m in medidas):
            return False, f"imagenes={len(nodos)} tamanos=sin_dimensiones esperado={esperado}"

        validas = [m for m in medidas if m is not None]
        tamanos = ", ".join(f"{w:.2f}x{h:.2f}" for w, h in validas)
        malas = [
            (w, h)
            for w, h in validas
            if abs(w - ancho_esperado) > tolerancia or abs(h - alto_esperado) > tolerancia
        ]
        detalle = f"imagenes={len(nodos)} tamanos={tamanos}cm esperado={esperado}"
        if malas:
            return False, f"{detalle} incumplen={len(malas)}"
        return True, detalle


class AnalizadorCantidadPatron(Analizador):
    r"""Cuenta palabras, matches de regex o entradas en una sección/texto.

    Sección DSL `patron_cantidad` (F3). `operacion`:
      count_words   — palabras (`\w+`) del texto contado
      count_matches — matches de `patron`
      count_entries — entradas separadas por ',' o ';' del texto tras
                      el primer ':' de CADA párrafo (p. ej. "Palabras
                      clave: a, b, c").
    El texto contado proviene de una `seccion`, de una lista `secciones`
    (cada una se cuenta por separado) o de nodos XPath. `excluir` descarta
    párrafos completos antes de contar (p. ej. la línea de palabras clave
    para que no infle la prosa del Resumen); `filtro` se queda solo con los
    párrafos que matchean (p. ej. la propia línea de palabras clave).
    """

    def _compilar(self, valor: str | None) -> re.Pattern | None:
        if not valor:
            return None
        flags = re.IGNORECASE if self.config.get("ignore_case", True) else 0
        return re.compile(valor, flags)

    def _piezas_seccion(self, extracted: ExtractedDocx, sec: dict) -> list[str]:
        corte = seccion(
            tokenizar(extracted),
            sec["inicio"],
            sec.get("fin"),
            hasta_final=bool(sec.get("hasta_final")),
        )
        piezas = [t.texto for t in corte if t.tipo == PARRAFO and t.texto.strip()]
        excluir = self._compilar(self.config.get("excluir"))
        if excluir:
            piezas = [p for p in piezas if not excluir.search(p)]
        filtro = self._compilar(sec.get("filtro") or self.config.get("filtro"))
        if filtro:
            piezas = [p for p in piezas if filtro.search(p)]
        return piezas

    def _piezas(self, extracted: ExtractedDocx) -> list[str]:
        sec = self.config.get("seccion")
        xpath_cfg = self.config.get("xpath")
        if sec:
            return self._piezas_seccion(extracted, sec)
        if xpath_cfg:
            nodos = self._nodos(
                extracted,
                self.config.get("parte", "document"),
                self.config.get("contexto", "todos"),
            )
            piezas = [text_of(n).strip() for n in nodos if text_of(n).strip()]
            excluir = self._compilar(self.config.get("excluir"))
            if excluir:
                piezas = [p for p in piezas if not excluir.search(p)]
            filtro = self._compilar(self.config.get("filtro"))
            if filtro:
                piezas = [p for p in piezas if filtro.search(p)]
            return piezas
        return []

    def _secciones(self) -> list[dict]:
        secciones = self.config.get("secciones")
        if secciones is None:
            return []
        if not isinstance(secciones, list) or not secciones:
            raise ConfigurationError("patron_cantidad: 'secciones' debe ser una lista no vacía")
        for sec in secciones:
            if not isinstance(sec, dict) or not sec.get("inicio"):
                raise ConfigurationError(
                    "patron_cantidad: cada elemento de 'secciones' debe ser un mapa con 'inicio'"
                )
        return secciones

    @staticmethod
    def _entradas(texto: str) -> int:
        """Entradas de UN párrafo tras su primer ':' (coma o punto y coma)."""
        cuerpo = texto.split(":", 1)[1] if ":" in texto else texto
        return len([x for x in re.split(r"[,;]", cuerpo) if x.strip()])

    def _contar(self, piezas: list[str], operacion: str) -> int:
        texto = " ".join(piezas)
        if operacion == "count_words":
            return len(re.findall(r"\w+", texto))
        if operacion == "count_matches":
            patron = self.config.get("patron", "")
            flags = re.IGNORECASE if self.config.get("ignore_case", False) else 0
            return len(re.findall(patron, texto, flags))
        return sum(self._entradas(p) for p in piezas)

    @staticmethod
    def _rango(minimo: int, maximo: int | None) -> str:
        rango = f"minimo={minimo}"
        if maximo is not None:
            rango += f" maximo={maximo}"
        return rango

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "count_words")
        if operacion not in ("count_words", "count_matches", "count_entries"):
            return False, f"operación '{operacion}' no soportada"
        minimo = self.config.get("cantidad_minima", 1)
        maximo = self.config.get("cantidad_maxima")
        rango = self._rango(minimo, maximo)

        secciones = self.config.get("secciones")
        if secciones is not None:
            partes = []
            fallo = False
            for sec in self._secciones():
                n = self._contar(self._piezas_seccion(extracted, sec), operacion)
                nombre = sec.get("nombre") or sec["inicio"]
                partes.append(f"{nombre}={n}")
                if n < minimo or (maximo is not None and n > maximo):
                    fallo = True
            detalle = " ".join(partes)
            return not fallo, f"{detalle} {rango}"

        n = self._contar(self._piezas(extracted), operacion)
        if operacion == "count_words":
            detalle = f"palabras={n}"
        elif operacion == "count_matches":
            detalle = f"matches={n}"
        else:
            detalle = f"entradas={n}"
        return minimo <= n and (maximo is None or n <= maximo), f"{detalle} {rango}"


class AnalizadorListaObligatoria(Analizador):
    """Verifica que cada ítem de `items` aparezca en la sección/texto.

    Sección DSL `lista_obligatoria` (F3) para anexos mínimos: substring
    normalizado (colapso de whitespace y, por defecto, ignore_case).
    """

    def __init__(self, config: dict):
        super().__init__(config)
        items = self.config.get("items")
        if not isinstance(items, list) or not items:
            raise ConfigurationError("lista_obligatoria: 'items' debe ser una lista no vacía")

    def _texto(self, extracted: ExtractedDocx) -> str:
        sec = self.config.get("seccion")
        if sec:
            corte = seccion(
                tokenizar(extracted),
                sec["inicio"],
                sec.get("fin"),
                hasta_final=bool(sec.get("hasta_final")),
            )
            return " ".join(
                t.texto for t in corte if t.tipo in (PARRAFO, TITULO) and t.texto.strip()
            )
        nodos = self._nodos(
            extracted,
            self.config.get("parte", "document"),
            self.config.get("contexto", "todos"),
        )
        return " ".join(text_of(n) for n in nodos)

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        items = self.config.get("items", [])
        texto = self._texto(extracted)
        ignore = self.config.get("ignore_case", True)

        def _norm(s: str) -> str:
            s = re.sub(r"\s+", " ", s).strip()
            return s.lower() if ignore else s

        texto_norm = _norm(texto)
        faltan = [it for it in items if _norm(it) not in texto_norm]
        encontrados = len(items) - len(faltan)
        if not faltan:
            return True, f"items_obligatorios={len(items)} encontrados={encontrados} completo"
        return False, (f"items_obligatorios={len(items)} encontrados={encontrados} faltan={faltan}")


class AnalizadorPaginacion(Analizador):
    """Verifica que los párrafos objetivo estén en páginas físicas distintas.

    Sección DSL `paginacion` (F2 ítem 1). La paginación se calcula en el
    extractor procesando, en orden de documento, los saltos explícitos
    (`w:br w:type="page"`, `w:pageBreakBefore`, `w:sectPr` no continuo) y la
    caché de render de Word (`w:lastRenderedPageBreak`). Cada párrafo
    objetivo (p. ej., un índice de contenidos/tablas/figuras) debe caer en
    una página física distinta para que la regla pase.

    Uso:
        paginacion:
          xpaths:
            - //w:body//w:p[contains(...)]
            - //w:body//w:p[contains(...)]
          comparacion: paginas_distintas

    No necesita verificar la separación cuando no es aplicable: si NINGUNA
    o alguna de las secciones objetivo no es identificable (p. ej. la
    plantilla usa un "Índice" genérico dentro de sdtContent que el xpath no
    localiza, o falta el índice de tablas), la regla pasa como n/a y no
    produce un falso positivo: solo juzga la paginación de las secciones
    que existen. La sección de "presencia" la cubren otras reglas.

    En ambos casos la regla se marca **NO APLICABLE** (`no_aplica=True`,
    `aplicable=False`, `found="no aplica a este documento"`), no "cumple":
    el compilador decide la aplicabilidad con esa bandera (revisión PR
    #102).

    M3/VA-04: si la página de algún objetivo es desconocida (el XML no trae
    marcadores ni caché de render), la regla pasa como n/a en vez de
    inventar una página y fallar por `paginas_repetidas`. Si la página solo
    está estimada (caché de render de Word), el detalle lo declara.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        xpaths = self.config.get("xpaths")
        if not isinstance(xpaths, list) or len(xpaths) < 2:
            raise ConfigurationError(
                "paginacion: 'xpaths' debe ser una lista con al menos 2 elementos"
            )

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        # El reset es obligatorio: la instancia se compila una vez y la API
        # la reutiliza para cada documento, así que un `no_aplica=True` de un
        # documento anterior se heredaría al siguiente (revisión PR #102).
        self.no_aplica = False
        xpaths = self.config.get("xpaths")
        if not isinstance(xpaths, list) or len(xpaths) < 2:
            return False, "paginacion requiere xpaths (>=2)"

        ubicaciones = []
        sin_coincidencia = []
        no_verificables = []
        for xpath in xpaths:
            nodos = extracted.xpath("document", xpath, "todos")
            if not nodos:
                sin_coincidencia.append(xpath)
                continue
            para = nodos[0]
            self.ultimo_nodo = para
            pagina = extracted.pagina_de(para)
            if pagina is None:
                return False, f"pagina_no_disponible={xpath}"
            certeza = extracted.certeza_pagina_de(para)
            if certeza == PAGINA_DESCONOCIDA:
                no_verificables.append(xpath)
            ubicaciones.append((pagina, certeza, para))

        # No todas las secciones objetivo son identificables (p. ej. la
        # plantilla usa un "Índice" genérico dentro de sdtContent, o falta el
        # índice de tablas): esta regla juzga solo la PAGINACIÓN, no la
        # presencia de secciones, así que pasa como n/a y no genera un falso
        # positivo (ver revisión técnica PR #28).
        if sin_coincidencia:
            self.no_aplica = True
            return True, "indices_no_verificables (n/a)"

        # Sin marcadores no se puede afirmar ni la separación ni la
        # repetición: inventar "página 1" para todos producía un
        # `paginas_repetidas` falso (M3/VA-04).
        if no_verificables:
            self.no_aplica = True
            return True, (
                "paginas_no_verificables (n/a): el documento no trae "
                "marcadores de salto ni caché de render"
            )

        paginas = [p for p, _, _ in ubicaciones]
        ok = len(set(paginas)) == len(paginas)
        estimadas = any(certeza == PAGINA_ESTIMADA for _, certeza, _ in ubicaciones)
        etiqueta = " (estimadas)" if estimadas else ""
        detalle = "; ".join(
            f"{i + 1}: página {p}" + (" (estimada)" if c == PAGINA_ESTIMADA else "")
            for i, (p, c, _) in enumerate(ubicaciones)
        )
        if ok:
            return True, f"paginas_distintas={paginas}{etiqueta}"
        return False, f"paginas_repetidas={paginas}{etiqueta}; {detalle}"


class AnalizadorHipervinculo(Analizador):
    """Detecta hipervínculos (w:hyperlink) cuyo texto coincida con un patrón.

    Sección DSL `hipervinculo_texto` (F3), p. ej. ORCID:
    `https://orcid.org/XXXXXXXXXXXXXXXX` (16 dígitos).

    Con la sub-configuración `validar_orcid` (M8/VA-16) además:

    - `checksum`: valida el dígito de control ISO 7064 MOD 11-2 (admite X).
    - `destino`: exige que el `Target` de la relación sea el perfil del
      mismo identificador visible (texto correcto con destino falso falla).
    - `por_persona`: cuenta los autores y el asesor de la carátula y exige
      un ORCID debajo de cada uno. Si la carátula no se reconoce, se queda
      con la comprobación global de cantidad.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        parte = self.config.get("parte", "document")
        contexto = self.config.get("contexto", "todos")
        patron = self.config.get("patron", "")
        ignore_case = self.config.get("ignore_case", True)
        minimo = self.config.get("cantidad_minima", 1)
        maximo = self.config.get("cantidad_maxima")

        nodos = self._nodos(extracted, parte, contexto)
        rx = re.compile(patron, re.IGNORECASE if ignore_case else 0)
        opciones = self.config.get("validar_orcid")

        # El manual pide el código entre paréntesis, no la URL completa. Con
        # `validar_orcid` son candidatos TODOS los hipervínculos cuyo texto
        # contenga un ORCID: limitarse al `patron` dejaba sin validar el
        # destino y el checksum en esa forma (falso verde, revisión #115).
        # Se conserva el orden de documento y no se duplican nodos.
        candidatos = {id(n): n for n in nodos if rx.search(text_of(n))}
        if isinstance(opciones, dict):
            for nodo in nodos:
                if orcid.extraer(text_of(nodo)) is not None:
                    candidatos[id(nodo)] = nodo
        coinciden = list(candidatos.values())
        n = len(coinciden)

        personas = 0
        sin_estructura = False
        problemas: list[str] = []
        if isinstance(opciones, dict):
            invalidos: list[str] = []
            for nodo in coinciden:
                identificador = orcid.extraer(text_of(nodo))
                if identificador is None:
                    invalidos.append("sin identificador")
                    continue
                if opciones.get("checksum", True) and not orcid.checksum_valido(identificador):
                    invalidos.append(f"{identificador} checksum")
                if opciones.get("destino", True) and not orcid.destino_corresponde(
                    extracted.destino_relacion(nodo.get(_R_ID)), identificador
                ):
                    invalidos.append(f"{identificador} destino")
            if invalidos:
                problemas.append(f"invalidos={detalle_lista_acotada(invalidos)}")
            if opciones.get("por_persona"):
                personas, faltan = self._personas_sin_orcid(extracted)
                sin_estructura = personas == 0
                if faltan:
                    problemas.append(f"sin_orcid={detalle_lista_acotada(faltan)}")

        detalle = f"hipervinculos={n} minimo={minimo}"
        if personas:
            detalle += f" personas={personas}"
        elif sin_estructura:
            detalle += " personas=0 (n/a)"
        if problemas:
            detalle += " " + " ".join(problemas)

        ok = n >= minimo
        if maximo is not None and n > maximo:
            ok = False
        return ok and not problemas, detalle

    @staticmethod
    def _personas_sin_orcid(extracted: ExtractedDocx) -> tuple[int, list[str]]:
        """Personas de la carátula y las que no tienen un ORCID debajo."""
        parrafos = [
            (text_of(p), orcid.tiene_orcid_en_parrafo(p))
            for p in extracted.document.xpath("//w:body/w:p", namespaces=NS)
            if extracted.is_caratula(p)
        ]
        return orcid.revisar_caratula(parrafos)


class AnalizadorNotaPie(Analizador):
    """Valida la consistencia de la numeración de las notas al pie (ítem 3).

    Sección DSL `nota_pie`, `operacion: numeracion_consistente`: los ids de
    `w:footnoteReference` en el cuerpo deben ser consecutivos (1..N, sin
    saltos, sin repetir) y, si la parte `word/footnotes.xml` existe, cada id
    referenciado debe estar definido ahí. Un documento SIN notas al pie pasa
    (n/a documentado), porque la ausencia no es un desvío.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "numeracion_consistente")
        if operacion != "numeracion_consistente":
            return False, f"operación '{operacion}' no soportada"

        # Buscar nodos de referencia (no solo ids) para poder localizar la página.
        refs = extracted.xpath("document", "//w:footnoteReference", "todos")
        if not refs:
            return True, "sin_notas_al_pie (n/a)"
        ids = [int(r.get(W + "id")) for r in refs if r.get(W + "id")]

        # El primer nodo de referencia sirve como punto de localización.
        self.ultimo_nodo = refs[0]

        if len(ids) != len(set(ids)):
            return False, f"notas_ids={sorted(ids)} duplicadas=True"

        ord = sorted(ids)
        consecutivas = ord == list(range(1, len(ord) + 1))
        definidas = True
        faltantes: list[int] = []
        fn = extracted.footnotes
        if fn is not None:
            disponibles = {int(e.get(W + "id")) for e in fn.iter(W + "footnote") if e.get(W + "id")}
            faltantes = [i for i in ord if i not in disponibles]
            definidas = not faltantes

        ok = consecutivas and definidas
        detalle = f"notas_ids={ord} consecutivas={consecutivas}"
        if faltantes:
            detalle += f" sin_definir={faltantes}"
        return ok, detalle


# ---------------------------------------------------------------------------
# Índice / tabla de contenidos (ítems 11 y 12 del PLAN_BACKLOG_FUTURO).
# ---------------------------------------------------------------------------

# Título que abre la región del índice de contenidos. Cubre "ÍNDICE" (plantilla
# y factory) y "INDICE DE CONTENIDOS" (factory). IGNORECASE vía `re` en el
# analizador. El texto se compara SIN acentos (re.IGNORECASE no iguala "Í" con
# "I"), así que el patrón es ASCII; la lógica de región elimina tildes primero.
REFERENCIA_INDICE = r"^indice(\s+de\s+contenidos)?$"

# Mapa para quitar tildes al normalizar (matching tolerante en el ítem 11).
_MAP_ACENTOS = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")


def _sin_acentos(s: str) -> str:
    """Elimina tildes de un texto (para matching ASCII de regiones)."""
    return s.translate(_MAP_ACENTOS)


def _normalizar_base_indice(texto: str) -> str:
    s = texto.strip()
    s = re.sub(r"^\s*(?:[IVXLC]+\s*\.|(?:\d+)+(?:\.\d+)*\s*\.?\s*)", "", s)
    s = re.sub(r"[()\[\],;:¿?¡!.]", " ", s)
    s = s.translate(_MAP_ACENTOS)
    return re.sub(r"\s+", " ", s).upper().strip()


def _norm_titulo_cuerpo(texto: str) -> str:
    """Título del cuerpo: sin numeración, pero SIN recortar sufijo romano.

    Los títulos de sección (p.ej. "General") no llevan número de página, así
    que no deben perder su última letra por el heurístico de páginas romanas.
    """
    return _normalizar_base_indice(texto)


def _norm_indice(texto: str) -> str:
    """Texto de una entrada de índice normalizado para MATCHING (ítem 11).

    Quita el prefijo de numeración (romano "I." o decimal "1.1."), el número
    de página al final (arábigo "10" o romano "ii"), separadores sueltos,
    tildes y colapsa el whitespace.

    La página se recorta aunque venga PEGADA al título (`1.2.1.General17`,
    `Dedicatoriaii`): en los índices reales de Word el tabulador que separa
    título y página no llega a `text_of`, y exigir whitespace dejaba 21
    entradas sin sección (AUD-01). El título del CUERPO usa
    `_norm_titulo_cuerpo`, que no recorta sufijo romano, así que este
    heurístico no puede volver a borrar la `l` de "General".
    """
    s = texto.strip()
    s = re.sub(r"^\s*(?:[IVXLC]+\s*\.|(?:\d+)+(?:\.\d+)*\s*\.?\s*)", "", s)
    s = re.sub(r"[()\[\],;:¿?¡!.]", " ", s)
    s = s.translate(_MAP_ACENTOS)
    s = re.sub(r"\s+", " ", s).strip().upper()
    # Página romana y arábiga, separadas o pegadas. El romano va primero:
    # si se quitara el arábigo antes, `1.2.1.General17` quedaría `GENERAL` y
    # el recorte romano volvería a comerse la `l` (el bug original).
    s = re.sub(r"\s*[IVXLC]{1,5}\s*$", "", s)
    s = re.sub(r"\s*\d+\s*$", "", s)
    return s.strip()


def _sigpalabra(s: str) -> str:
    """Primera palabra con >=4 caracteres de un texto normalizado (o vacío).

    Respaldo de `indice_apunta_secciones` (AUD-06): la comprobación principal
    es la igualdad del título normalizado; este heurístico solo se usa cuando
    ese título tiene menos de 4 caracteres y no alcanza para exigir igualdad.
    El umbral descarta tokens de numeración o romanos ("I", "1.2", "A") como
    señal de contenido. Si no hay ninguna palabra de 4+ caracteres, se
    devuelve "" y el chequeo omite la entrada: no hay señal suficiente para
    verificar que apunte a una sección real.
    """
    for tk in s.split():
        if len(tk) >= 4:
            return tk
    return ""


def _texto_con_tabs(nodo) -> str:
    """Texto de un párrafo preservando `w:tab` como espacio.

    `text_of()` solo concatena `w:t`, así que en un índice de Word el
    tabulador que separa título y página desaparece y ambos quedan pegados
    (`1.2.1.General17`). Para normalizar entradas del índice necesitamos ese
    separador (AUD-01); los saltos de línea también se tratan como espacio.
    """
    partes: list[str] = []
    for hijo in nodo.iter():
        if hijo.tag == W + "t":
            partes.append(hijo.text or "")
        elif hijo.tag in (W + "tab", W + "br", W + "cr"):
            partes.append(" ")
    return "".join(partes)


def _entradas_indice(extracted: ExtractedDocx, regex_indice: str = REFERENCIA_INDICE) -> list[dict]:
    """Entradas del índice de contenidos en orden de documento.

    Regiones: párrafos NO-título que siguen a un título que matchea
    `regex_indice` (solo estilos de encabezado), hasta el siguiente título
    de cualquier nivel. Se acumulan TODAS las regiones que matcheen (la
    plantilla usa un único "Índice"; el factory "ÍNDICE" + "INDICE DE
    CONTENIDOS"). Cada entrada lleva su nodo `w:p` (para `ultimo_nodo`).
    """
    body = extracted.document.find(W + "body")
    if body is None:
        return []
    rx = re.compile(regex_indice, re.IGNORECASE)
    entradas: list[dict] = []
    en_region = False
    for p in body.findall(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        estilo = st.get(W + "val") if st is not None else ""
        texto = _texto_con_tabs(p).strip()
        if es_heading(estilo):
            en_region = bool(rx.search(_sin_acentos(texto)))
            continue
        if en_region and texto:
            entradas.append({"texto": texto, "nivel": 1, "nodo": p})
    return entradas


def _títulos_cuerpo(extracted: ExtractedDocx) -> set[str]:
    """Títulos del cuerpo normalizados (solo estilos de encabezado)."""
    body = extracted.document.find(W + "body")
    if body is None:
        return set()
    titulos: set[str] = set()
    for p in body.findall(W + "p"):
        st = p.find(f"{W}pPr/{W}pStyle")
        estilo = st.get(W + "val") if st is not None else ""
        if es_heading(estilo):
            texto = text_of(p).strip()
            if texto:
                titulos.add(_norm_titulo_cuerpo(texto))
    return titulos


def _parse_numero_indice(texto: str) -> tuple | None:
    """Número de una entrada del índice: ("romano", n) o ("decimal", (k, ...))."""
    m = re.match(r"^\s*([IVXLC]+)[\.\s]+(.+)$", texto)
    if m:
        letras = m.group(1).upper()
        valores = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
        total = 0
        for i, c in enumerate(letras):
            v = valores[c]
            if i + 1 < len(letras) and valores[letras[i + 1]] > v:
                total -= v
            else:
                total += v
        return ("romano", total)
    m = re.match(r"^\s*(\d+(?:\.\d+)+)\s*\.?\s*(.+)$", texto)
    if m:
        return ("decimal", tuple(int(x) for x in m.group(1).split(".")))
    return None


class AnalizadorTocApunta(Analizador):
    """Verifica que el índice apunte a secciones reales del documento (ítem 11).

    Sección DSL `toc_apunta`, `operacion: entradas_corresponden`: cada
    entrada de la región del índice de contenidos debe coincidir —tras
    normalizar numeración, página, tildes y separadores— con ALGÚN título
    del cuerpo (igualdad, no subcadena; AUD-06). Cuando el título
    normalizado tiene menos de 4 caracteres no hay señal fiable y se usa
    `_sigpalabra` como respaldo (auto-pase). Un documento sin región de
    índice pasa (n/a documentado).

    Fiel al manual (párr. 194): "Lista estructurada de los segmentos que
    integran la investigación, según orden de presentación". NO prohíbe
    números de página (el índice de tablas los exige).
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "entradas_corresponden")
        if operacion != "entradas_corresponden":
            return False, f"operación '{operacion}' no soportada"

        entradas = _entradas_indice(extracted, self.config.get("regex_indice", REFERENCIA_INDICE))
        if not entradas:
            return True, "sin_indice (n/a)"

        titulos = _títulos_cuerpo(extracted)
        faltan: list[str] = []
        self.ultimo_nodo = None
        for e in entradas:
            norm = _norm_indice(e["texto"])
            # AUD-06: igualdad del título normalizado, no subcadena. El match
            # por subcadena ocultaba una sección faltante cuando su palabra
            # aparecía dentro de otro título ("OBJETIVOS" dentro de
            # "OBJETIVOS ESPECÍFICOS"). `_sigpalabra` queda como respaldo solo
            # cuando el título normalizado es demasiado corto (<4 caracteres)
            # para ser una señal fiable; ahí se conserva el auto-pase.
            if norm in titulos:
                continue
            if len(norm) < 4:
                sig = _sigpalabra(norm)
                if not sig or any(sig in t for t in titulos):
                    continue
            if self.ultimo_nodo is None:
                self.ultimo_nodo = e["nodo"]
            faltan.append(e["texto"][:60])

        if faltan:
            return False, f"entrada_sin_seccion={faltan[:6]}"
        return True, "entradas_corresponden"


class AnalizadorTocNumeracion(Analizador):
    """Valida la jerarquía de numeración del índice (ítem 12).

    Sección DSL `toc_numeracion`, `operacion: jerarquia_consistente`:

    - Capítulos en romano (I, II, ...) consecutivos, sin saltos.
    - Subsecciones decimales (1.1, 1.1.1, ...) bajo el capítulo actual y en
      orden preorder estricto (un padre precede a sus hijos; 1.1 < 1.1.1 <
      1.1.2 < 1.2 < 1.3 ...).
    - La primera subsección de cada capítulo es K.1.

    NO exige contigüidad de subsecciones hermanas (1.1 → 1.3 es aceptable)
    para evitar falsos positivos cuando una sección "no aplica" y se omite;
    solo orden y pertenencia al capítulo. Un documento sin región de índice
    pasa (n/a documentado).
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        operacion = self.config.get("operacion", "jerarquia_consistente")
        if operacion != "jerarquia_consistente":
            return False, f"operación '{operacion}' no soportada"

        entradas = _entradas_indice(extracted, self.config.get("regex_indice", REFERENCIA_INDICE))
        if not entradas:
            return True, "sin_indice (n/a)"

        caps: list[int] = []
        prev: tuple | None = None
        primera = True
        fallos: list[str] = []
        self.ultimo_nodo = None
        for e in entradas:
            num = _parse_numero_indice(e["texto"])
            if num is None:
                continue
            tipo, valor = num
            if tipo == "romano":
                if caps and valor != caps[-1] + 1:
                    fallos.append(f"salto_capitulo={valor}")
                caps.append(valor)
                prev = None
                primera = True
                continue
            # decimal
            if not caps:
                fallos.append("subseccion_sin_capitulo")
            elif valor[0] != caps[-1]:
                fallos.append(f"capitulo_descolgado={e['texto'][:60]}")
            elif primera:
                if len(valor) >= 2 and valor[1] != 1:
                    fallos.append(f"primera_subseccion_no_K1={e['texto'][:60]}")
                primera = False
                prev = valor
            else:
                if prev is not None and not (prev < valor):
                    fallos.append(f"fuera_de_orden={e['texto'][:60]}")
                prev = valor

        if fallos:
            if self.ultimo_nodo is None:
                self.ultimo_nodo = entradas[0]["nodo"]
            return False, detalle_jerarquia(fallos)
        return True, "jerarquia_ok"


# ---------------------------------------------------------------------------
# deteccion_tipo: qué tipo de documento es (Semana 6, paso 2)
# ---------------------------------------------------------------------------

NIVEL_DECLARADO = "declarado"
NIVEL_INFERIDO = "inferido"
NIVEL_NO_DETERMINADO = "sin_determinar"

# Valores que publica en el contexto cuando no se puede afirmar un tipo.
TIPO_SIN_DETERMINAR = "sin_determinar"
TIPO_CONTRADICTORIO = "contradictorio"

# Casillas del Anexo 10 que sabemos leer de forma determinista. Un documento
# puede marcarlas como texto plano o como símbolo Wingdings (`w:sym`), que es
# como las dibuja Word; se cubren las dos formas.
_CASILLA_MARCADA_TXT = re.compile(r"[☒☑✔■]|\[\s*(?:[xX✓])\s*\]|\(\s*[xX]\s*\)")
_CASILLA_VACIA_TXT = re.compile(r"[☐□◻]|\[\s*\]|\(\s*\)")
# Wingdings: F0FE/F0FC/F0A3 marcadas; F0A8/F0B0 son la casilla vacía.
_SYM_MARCADA = {"F0FE", "F0FC", "F0A3"}
_SYM_VACIA = {"F0A8", "F0B0"}


def _norm_deteccion(s: str) -> str:
    """Normaliza para comparar firmas: mayúsculas, sin tildes, sin
    indentación y con espacios colapsados."""
    return re.sub(r"\s+", " ", _sin_acentos(s).upper()).strip()


def _estado_casilla(p) -> tuple[bool, bool]:
    """(marcada, hay_casilla) para un párrafo `w:p`.

    Una casilla sin marcar hace que el párrafo NO sea una declaración, aunque
    tenga una etiqueta de tipo al lado: es el caso "desmarcado", que es el
    error más fácil de cometer al leer.
    """
    texto = text_of(p)
    for sym in p.iter(f"{W}sym"):
        char = (sym.get(W + "char") or "").upper()
        if char in _SYM_VACIA:
            return False, True
        if char in _SYM_MARCADA:
            return True, True
    if _CASILLA_VACIA_TXT.search(texto):
        return False, True
    if _CASILLA_MARCADA_TXT.search(texto):
        return True, True
    return False, False


# Namespace de Word 2010 en adelante (`w14`): lleva el estado de las casillas
# de content-control. El namespace no está en `extractor.NS` porque aquí solo
# se lee el estado de un checkbox del Anexo 10.
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"


def _en_fila(p):
    """Ancestro `w:tr` (fila de tabla) del párrafo, o `None` si no vive en
    una tabla. Los párrafos de una celda están anidados (body > tbl > tr > tc
    > p), por eso se sube por los padres."""
    nodo = p.getparent()
    while nodo is not None and nodo.tag != W + "tr":
        nodo = nodo.getparent()
    return nodo


def _estado_casilla_contenido(p) -> tuple[bool, bool]:
    """(marcada, hay_casilla) de una casilla de content-control.

    Word dibuja la casilla como símbolo (`w:sym`) o como texto plano, que
    cubre `_estado_casilla`; pero si el autor la inserta como control de
    contenido, el `w14:checkbox` vive en `w:sdtPr`, un árbol hermano de
    `w:sdtContent` (que es el que contiene al párrafo). Hay que subir hasta
    el ancestro `w:sdt` para leer el estado.
    """
    nodo = p.getparent()
    while nodo is not None and nodo.tag != W + "sdt":
        nodo = nodo.getparent()
    if nodo is None:
        return False, False
    # `find` no baja a los nietos: el w14:checkbox vive dentro de w:sdtPr.
    checked = nodo.find(f"{W}sdtPr/{W14}checkbox/{W14}checked")
    if checked is None:
        return False, False
    val = (checked.get(W14 + "val") or "").strip().lower()
    return val in ("1", "true", "on", "yes", ""), True


def _casilla_de(p) -> tuple[bool, bool]:
    """(marcada, hay_casilla) de un párrafo de declaración.

    Mira la casilla propia (símbolo o texto), la del content-control `w:sdt`
    que lo envuelve y la de los párrafos hermanos de su misma fila de tabla:
    en el Anexo 10 la casilla y su etiqueta pueden vivir en celdas distintas.
    """
    marcada, hay_casilla = _estado_casilla(p)
    if hay_casilla:
        return marcada, True
    marcada, hay_casilla = _estado_casilla_contenido(p)
    if hay_casilla:
        return marcada, True
    tr = _en_fila(p)
    if tr is not None:
        for celda in tr.iter(W + "p"):
            if celda is p:
                continue
            m, h = _estado_casilla(celda)
            if h:
                return m, True
            m, h = _estado_casilla_contenido(celda)
            if h:
                return m, True
    return False, False


class DeteccionTipo(Analizador):
    """Determina el tipo de documento de forma determinista.

    Sección DSL `deteccion_tipo`. Tres niveles, en orden de preferencia
    (decisión 2 del diseño):

    1. **Declarado** — casilla marcada del Anexo 10, con la etiqueta del tipo
       que el autor eligió. Es una declaración del autor, no una inferencia.
    2. **Inferido** — se cuentan las firmas estructurales de cada tipo y gana
       el primero que alcance su `minimo`. El orden de `firmas` es el de
       especificidad (decisión 2: el informe gana al proyecto). Las firmas se
       cotejan solo contra párrafos con estilo de TÍTULO (igual que el DFA de
       la regla de estructura): la prosa es ruido y no debe contar como
       evidencia estructural.
    3. **Sin determinar** — ninguna firma alcanzó su umbral.

    Si hay nivel 1 y nivel 2 y no coinciden, se publica
    `TIPO_CONTRADICTORIO`: es preferible decir que hay una contradicción
    visible a elegir en silencio. Lo mismo ocurre si el propio Anexo 10 trae
    marcadas casillas de dos tipos distintos (M4/VA-05): repetir el mismo tipo
    no cambia la decisión.

    El valor publicado (`Analizador.valor`) es el identificador canónico del
    tipo, que es lo que consume `aplicar_si` en las reglas de estructura. El
    nivel y la evidencia quedan además en `self.nivel` y `self.evidencia`,
    para que el reporte pueda explicarle al estudiante por qué se eligió ese
    tipo sin tener que parsear el texto del detalle.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        # Nivel que decidió la detección (declarado / inferido / sin_determinar).
        self.nivel: str = NIVEL_NO_DETERMINADO
        # Evidencia concreta: las etiquetas del Anexo 10 leídas, o las firmas
        # que alcanzaron el umbral.
        self.evidencia: list[str] = []

    def _resolver(self, nivel: str, tipo: str | None, detalle: str) -> tuple[bool, str]:
        self.nivel = nivel
        self.valor = tipo if tipo is not None else TIPO_SIN_DETERMINAR
        return tipo is not None, detalle

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        body = extracted.document.find(W + "body")
        if body is None:
            self.nivel = NIVEL_NO_DETERMINADO
            self.valor = TIPO_SIN_DETERMINAR
            return False, "sin_determinado (documento sin cuerpo)"

        # Nivel 1 (declaración): la casilla marcada puede vivir en cualquier
        # párrafo del cuerpo, incluidos los de una tabla (`w:tbl`) o de un
        # bloque de contenido (`w:sdt`), así que se recorren todos los
        # descendientes y no solo los hijos directos del body.
        todos = list(body.iter(W + "p"))
        declaraciones = self._tipo_declarado(todos)

        # M4/VA-05: se recogen TODAS las casillas marcadas, no solo la
        # primera. Dos tipos distintos son una contradicción del propio
        # Anexo 10 y no se puede elegir uno en silencio; repetir el mismo
        # tipo (o marcar dos de sus etiquetas) no cambia la decisión.
        etiquetas_por_tipo: dict[str, str] = {}
        for tipo, etiqueta in declaraciones:
            actual = etiquetas_por_tipo.get(tipo)
            if actual is None or self._etiqueta_preferida(etiqueta, actual):
                etiquetas_por_tipo[tipo] = etiqueta
        tipos_declarados = sorted(etiquetas_por_tipo)

        if len(tipos_declarados) > 1:
            self.nivel = NIVEL_NO_DETERMINADO
            self.evidencia = [etiquetas_por_tipo[tipo] for tipo in tipos_declarados]
            self.valor = TIPO_CONTRADICTORIO
            detalle = "contradictorio: " + ", ".join(
                f"declarado={tipo} ('{etiquetas_por_tipo[tipo]}')" for tipo in tipos_declarados
            )
            return False, detalle

        declaracion = tipos_declarados[0] if tipos_declarados else None
        etiqueta = etiquetas_por_tipo[declaracion] if declaracion is not None else ""

        # Nivel 2 (inferencia): las firmas se cotejan SOLO contra párrafos
        # con estilo de título (decisión 2 del diseño, revisión del PR). La
        # prosa es mucho más ruidosa que la estructura: con prosa, la línea
        # "Línea de investigación:" de la carátula le regalaba la evidencia a
        # `proyecto_cuantitativo` en cualquier tesis y bastaba un párrafo
        # suelto ("recursos y materiales") para virar la clasificación.
        title_texts = [t.texto for t in solo(tokenizar(extracted), [TITULO])]
        inferido, evidencia = self._tipo_inferido(title_texts)

        if declaracion and inferido and declaracion != inferido:
            self.nivel = NIVEL_NO_DETERMINADO
            self.evidencia = [etiqueta, *evidencia]
            self.valor = TIPO_CONTRADICTORIO
            return False, (
                f"contradictorio: declarado={declaracion} ('{etiqueta}') "
                f"inferido={inferido} ({', '.join(evidencia)})"
            )

        if declaracion:
            self.evidencia = [etiqueta]
            return self._resolver(
                NIVEL_DECLARADO, declaracion, f"declarado={declaracion} ('{etiqueta}')"
            )

        if inferido:
            self.evidencia = evidencia
            quoted = ", ".join(f'"{e}"' for e in evidencia)
            return self._resolver(NIVEL_INFERIDO, inferido, f"inferido={inferido} ({quoted})")

        self.evidencia = []
        return self._resolver(
            NIVEL_NO_DETERMINADO, None, "sin_determinado (ninguna firma alcanzó su mínimo)"
        )

    # -- nivel 1: declaración del Anexo 10 --------------------------------
    def _tipo_declarado(self, parrafos) -> list[tuple[str, str]]:
        """Todas las casillas marcadas junto a su etiqueta, no solo la primera.

        La casilla y la etiqueta deben estar relacionadas: en el MISMO párrafo
        o, si el Anexo 10 es una tabla, en la MISMA fila — Word suele poner la
        casilla en una celda y su etiqueta en otra. La casilla se lee como
        símbolo, texto plano o content-control `w14:checkbox`.

        Si en un contexto casan varias etiquetas, gana la MÁS LARGA. El
        cotejo es por subcadena y unas etiquetas contienen a otras: "INFORME
        DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO" contiene "PROYECTO DE
        INVESTIGACIÓN CUANTITATIVO", así que las dos casan en el mismo
        párrafo. Con el orden del diccionario el resultado dependía de dónde
        estuviera escrita cada clave en el YAML, que es una fuente de fallo
        silencioso. Con la más larga gana, el texto del Anexo 10 basta para
        decidir y reordenar el YAML no cambia nada.

        Devuelve una lista ordenada de pares `(tipo, etiqueta)`. El orden y la
        deduplicación son deliberados: la misma casilla se puede leer desde el
        párrafo de la casilla y desde el de su etiqueta, y la decisión no debe
        depender del orden en que el documento liste las casillas (M4/VA-05).
        """
        etiquetas = self.config.get("declaracion", {}).get("etiquetas", {})
        if not etiquetas:
            return []
        declaraciones: set[tuple[str, str]] = set()
        for p in parrafos:
            marcada, hay_casilla = _casilla_de(p)
            if not hay_casilla or not marcada:
                continue
            # La etiqueta se busca en el párrafo de la casilla y, si vive en
            # una tabla, también en los párrafos hermanos de su misma fila.
            textos = [text_of(p)]
            tr = _en_fila(p)
            if tr is not None:
                textos.extend(text_of(c) for c in tr.iter(W + "p") if c is not p)
            texto = _norm_deteccion(" ".join(textos))
            candidatos: list[tuple[int, str, str]] = []
            for tipo, alias in etiquetas.items():
                for etiqueta in [tipo, *alias]:
                    clave = _norm_deteccion(etiqueta)
                    if clave and clave in texto:
                        candidatos.append((len(clave), tipo, etiqueta))
            if candidatos:
                # Más larga primero. El nombre del tipo solo desempata, para
                # que un empate no dependa del orden del diccionario.
                candidatos.sort(key=lambda c: (-c[0], c[1]))
                _, tipo, etiqueta = candidatos[0]
                declaraciones.add((tipo, etiqueta))
        return sorted(declaraciones)

    @staticmethod
    def _etiqueta_preferida(nueva: str, actual: str) -> bool:
        """¿La etiqueta nueva representa mejor al tipo que la actual?

        Manda la más larga (es la más específica) y, a igual longitud, la
        menor en orden alfabético. Así dos etiquetas del mismo tipo no hacen
        que la evidencia dependa del orden de las casillas.
        """
        if len(nueva) != len(actual):
            return len(nueva) > len(actual)
        return nueva < actual

    # -- nivel 2: firmas estructurales ------------------------------------
    def _tipo_inferido(self, textos) -> tuple[str | None, list[str]]:
        """Tipo que alcanza su `minimo` de firmas entre los títulos.

        `textos` son los textos planos de los párrafos con estilo de título;
        el cotejo es por subcadena y normalización, para que la numeración
        ("2.1."), la sangría y las tildes no rompan el emparejamiento.
        """
        textos = [_norm_deteccion(t) for t in textos]
        for firma in self.config.get("firmas", []):
            minimo = firma.get("minimo", 1)
            encontradas = [
                ev
                for ev in firma.get("evidencia", [])
                if any(_norm_deteccion(ev) in t for t in textos)
            ]
            if len(encontradas) >= minimo:
                return firma.get("tipo"), encontradas
        return None, []


class AnalizadorExtraccion(Analizador):
    """Captura el texto de los nodos que su XPath/sección localiza (diseño 17).

    Es un analizador de **lectura**, no de validación: siempre pasa, nunca
    produce fallos, nunca toca el semáforo. Su único fin es poblar `ficha`
    con `{"campo", "valor", "nodo"}` para que el motor arme la ficha de
    depósito (contrato del handover `HANDOVER_MOTOR_FICHA_DEPOSITO.md`).

    Config (sección DSL `extraccion`):
      campo:          clave acordada con la API (p. ej. `dc.title`).
      xpath:          XPath que localiza el nodo o nodos a capturar.
      parte:          `document` (default).
      contexto:       `todos` (default), `caratula`, `cuerpo`, ...
      seccion:        alternativa al xpath: `{inicio, fin}` de títulos; captura
                      el texto de los párrafos de esa sección (tokenizer).
      modo:           `texto` (default, un valor: texto del primer nodo) o
                      `lista` (varios valores: texto de cada nodo, sin vacíos).
      separador:      si viene, parte el texto de cada nodo por ese separador y
                      concatena los trozos (p. ej. autores "A, B y C" → lista).
       etiqueta:       si viene, captura solo lo que sigue a la primera aparición
                       de `etiqueta` + ":" (p. ej. "Palabras clave: a, b" → "a, b").
       patron:         regex; si viene, captura `group(1)` (o el match completo
                       si no hay grupo) del texto resultante (p. ej. el año).
       quitar_prefijo: regex que se elimina del inicio del texto (etiquetas como
                       "Asesor(a): ").
       quitar_sufijo:  regex que se elimina del final del texto (p. ej. ", Trujillo
                       2026").
       seleccion:      `primero`, `ultimo` o `primero_no_vacio`: con más de un
                       match, elige la pieza #1, la última (p. ej. para el año
                       vs título) o la primera cuyo texto limpio no quede vacío
                       (asesor con la etiqueta en un párrafo aparte). Aplica
                       DESPUÉS de `filtro`, NO tras `etiqueta`/`patron`.
    """

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        campo = self.config.get("campo", "")
        if not campo:
            return True, "extraccion sin campo"

        piezas = self._piezas(extracted)
        if not piezas:
            return True, f"extraccion {campo}: sin valor"

        modo = self.config.get("modo", "texto")
        valor: str | list[str]
        if modo == "lista":
            valor = self._valores_lista(piezas)
        elif self.config.get("unir"):
            # Texto íntegro de una sección de varios párrafos (p. ej. Resumen).
            valor = " ".join(self._limpiar(p) for p in piezas if self._limpiar(p))
        else:
            valor = self._limpiar(piezas[0])

        self.ficha.append({"campo": campo, "valor": valor, "nodo": piezas[0][1]})
        return True, f"extraccion {campo}: {self._resumen(valor)}"

    def _piezas(self, extracted: ExtractedDocx) -> list[tuple[str, object]]:
        """Devuelve `(texto, nodo)` de cada párrafo objetivo.

        Con `seccion`, el flujo de tokens de esa sección; si no, los nodos del
        XPath. El nodo es lo que `pagina_de` usa para resolver la página.
        `filtro` (regex) acota los párrafos por su texto (p. ej. la línea de
        "Palabras clave" dentro del Resumen).
        """
        sec = self.config.get("seccion")
        piezas: list[tuple[str, object]] = []
        if sec:
            corte = seccion(tokenizar(extracted), sec["inicio"], sec.get("fin"))
            piezas = [
                (t.texto.strip(), None) for t in corte if t.tipo == PARRAFO and t.texto.strip()
            ]
        else:
            nodos = self._nodos(
                extracted,
                self.config.get("parte", "document"),
                self.config.get("contexto", "todos"),
            )
            piezas = [(text_of(n).strip(), n) for n in nodos if text_of(n).strip()]
        filtro = self.config.get("filtro")
        if filtro:
            rx = re.compile(filtro, re.IGNORECASE if self.config.get("ignore_case", True) else 0)
            piezas = [p for p in piezas if rx.search(p[0])]
        # `seleccion` elige qué pieza usar cuando hay más de una (p. ej. el año
        # es el último match, el título el primero). Se aplica DESPUÉS de
        # `filtro`, así que filtra primero y luego elige.
        seleccion = self.config.get("seleccion")
        if seleccion == "ultimo" and piezas:
            piezas = piezas[-1:]
        elif seleccion == "primero" and piezas:
            piezas = piezas[:1]
        elif seleccion == "primero_no_vacio" and piezas:
            # El asesor puede venir como «ASESOR(A):» en un párrafo y el
            # nombre en el siguiente, o ambos en el mismo párrafo. Se queda
            # con la primera pieza que, ya limpiada, no quede vacía (AUD-25).
            elegida = next((p for p in piezas if self._limpiar(p)), None)
            piezas = [elegida] if elegida is not None else piezas[:1]
        # Con `seccion` los tokens no traen su nodo; para poder publicar la
        # página se resuelve el `w:p` por texto exacto (mapa por texto).
        if sec and piezas:
            mapa = self._mapa_nodos(extracted)
            piezas = [(txt, mapa.get(txt)) for txt, _ in piezas]
        return piezas

    @staticmethod
    def _mapa_nodos(extracted: ExtractedDocx) -> dict[str, object]:
        """Mapa texto-normalizado → primer `w:p` del cuerpo con ese texto."""
        mapa: dict[str, object] = {}
        try:
            nodos = extracted.xpath("document", "//w:body//w:p", "todos")
        except ValueError:
            return mapa
        for n in nodos:
            clave = re.sub(r"\s+", " ", text_of(n)).strip()
            if clave and clave not in mapa:
                mapa[clave] = n
        return mapa

    def _limpiar(self, pieza: tuple[str, object]) -> str:
        texto = pieza[0]
        etiqueta = self.config.get("etiqueta")
        if etiqueta:
            m = re.search(re.escape(etiqueta) + r"\s*:\s*(.*)", texto, re.IGNORECASE | re.DOTALL)
            if m:
                texto = m.group(1).strip()
        prefijo = self.config.get("quitar_prefijo")
        if prefijo:
            texto = re.sub(prefijo, "", texto, count=1, flags=re.IGNORECASE).strip()
        sufijo = self.config.get("quitar_sufijo")
        if sufijo:
            texto = re.sub(sufijo, "", texto, count=1, flags=re.IGNORECASE).strip()
        patron = self.config.get("patron")
        if patron:
            m = re.search(patron, texto)
            if m:
                texto = (m.group(1) if m.groups() else m.group(0)).strip()
        return texto

    def _valores_lista(self, piezas: list[tuple[str, object]]) -> list[str]:
        separador = self.config.get("separador")
        valores: list[str] = []
        for pieza in piezas:
            texto = self._limpiar(pieza)
            if not texto:
                continue
            if separador:
                valores.extend(p.strip() for p in re.split(separador, texto) if p.strip())
            else:
                valores.append(texto)
        return valores

    @staticmethod
    def _resumen(valor) -> str:
        if isinstance(valor, list):
            return f"{len(valor)} valor(es)"
        return str(valor)[:40]
