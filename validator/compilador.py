"""Compilador del DSL declarativo de reglas.

Convierte el YAML de reglas (formato DSL) en una colección de
`Analizador` ejecutables y los corre contra un `ExtractedDocx` para
producir `List[RuleResult]` — el mismo contrato que el motor legacy.

Formato DSL (la regla puede declarar cualquiera de estas secciones, y
**todas** deben cumplirse para que la regla pase; si una sección se
declara como **lista**, cada elemento es una comprobación distinta que
también debe cumplirse):

    atributo_xml / presencia_xml -> AnalizadorXML
    patron_texto                -> AnalizadorRegex
    lista_texto                 -> AnalizadorLista
    imagen                      -> AnalizadorImagen
    automata_secuencia          -> AutomataSecuencia (DFA)
    gramatica_estructura        -> GramaticaEstructura (BNF)
    automata_pila               -> AutomataPila (PDA, push/pop)
    patron_cantidad             -> AnalizadorCantidadPatron (conteo)
    conteo_nodos                -> AnalizadorConteoNodos (min/máx)
    lista_obligatoria           -> AnalizadorListaObligatoria (anexos)
    hipervinculo_texto          -> AnalizadorHipervinculo (ORCID)
    paginacion                  -> AnalizadorPaginacion (párrafo↔página física)
    nota_pie                    -> AnalizadorNotaPie (numeración de notas al pie)
    toc_apunta                  -> AnalizadorTocApunta (índice apunta a secciones reales)
    toc_numeracion              -> AnalizadorTocNumeracion (jerarquía de numeración)

La regla también conserva metadatos (descripcion, severidad, etc.) que
se propagan al `RuleResult` resultante.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypedDict

from .analizadores import (
    TIPO_CONTRADICTORIO,
    TIPO_SIN_DETERMINAR,
    Analizador,
    AnalizadorCantidadPatron,
    AnalizadorConteoNodos,
    AnalizadorHipervinculo,
    AnalizadorImagen,
    AnalizadorLista,
    AnalizadorListaObligatoria,
    AnalizadorNotaPie,
    AnalizadorPaginacion,
    AnalizadorRegex,
    AnalizadorTocApunta,
    AnalizadorTocNumeracion,
    AnalizadorXML,
    DeteccionTipo,
)
from .automata import DFA, PDA, GramaticaEstructura, Transicion, TransicionPDA
from .dsl_check import linter_o_alzar
from .extractor import NS, ExtractedDocx, text_of
from .models import RuleResult, Severity
from .tokenizer import TITULO, solo, tokenizar

# Secciones del DSL que indican que una regla es verificable.
SECCIONES_ANALIZADOR = (
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


# ---------------------------------------------------------------------------
# AutomataSecuencia con interfaz Analizador (se usa a través del DSL)
# ---------------------------------------------------------------------------


def _sig_token(s: str) -> str:
    """Token "significativo" del motor legacy (checks._check_secuencia).

    Primer token de la cadena con al menos 4 caracteres alfanuméricos
    (sin puntuación). Si ninguno lo tiene, usa el primer token normalizado.
    Permite tolerar variantes de redacción ("2.1 Variable(s)..." encaja con
    "Variable(s) y operacionalización" porque el token significativo coincide).
    """
    for tk in s.split():
        tk = re.sub(r"[^A-ZÁÉÍÓÚÑ0-9]+", "", tk)
        if len(tk) >= 4:
            return tk
    return re.sub(r"[^A-ZÁÉÍÓÚÑ0-9]+", "", s.split()[0]) if s.split() else ""


def _matchea_legacy(token: str, patron: re.Pattern, prefijos: bool) -> bool:
    """Matching idéntico al legacy `checks._check_secuencia`.

    Sustituye la semántica genérica del DFA (search + prefijo) por la del
    motor legacy: startswith, prefijo del heading, o igualdad del token
    significativo. Garantiza que el DSL acepte exactamente lo que aceptaba
    `secuencia_titulos` (paridad de comportamiento en la F1 de migración).
    """
    p = patron.pattern
    if token.startswith(p) or p.startswith(token[: min(len(token), 25)]):
        return True
    st = _sig_token(p)
    tt = _sig_token(token)
    if st and tt and st == tt:
        return True
    return False


def _normalizar_texto(s: str, normalizacion: list[str]) -> str:
    """Normaliza el texto de un token igual que `AutomataSecuencia`."""
    if "mayusculas" in normalizacion:
        s = s.upper()
    if "ignorar_indent" in normalizacion:
        s = s.strip()
    s = re.sub(r"\s+", " ", s.replace("(OPCIONAL)", " ").strip(" ."))
    return s


def _flujo_texto(
    extracted: ExtractedDocx, normalizacion: list[str], tipo_flujo: str, tipos
) -> list[str]:
    """Proyección de texto (normalizada) del flujo tokenizado.

    `tipo_flujo: titulos` (default) usa SOLO los títulos — reproduce la
    proyección histórica `_headings()` (paridad). `tipo_flujo: documento`
    usa el flujo completo filtrado por `tipos` (TITULO, PARRAFO, TABLA,
    IMAGEN, SALTO_SECCION).
    """
    tipos_flujo = tipos if tipo_flujo == "documento" else ["TITULO"]
    return [
        _normalizar_texto(t.texto, normalizacion) for t in solo(tokenizar(extracted), tipos_flujo)
    ]


class AutomataSecuencia(Analizador):
    """Reconoce una secuencia de títulos usando un DFA.

    Construye el autómata a partir de `automata_secuencia.estados`,
    `inicial` y `aceptacion`. Cada estado es un patrón (regex sobre el
    heading normalizado) que, al ser reconocido, transita al siguiente.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.nivel_titulo: list[int] = config.get("nivel_titulo", [1, 2, 3])
        self.normalizacion: list[str] = config.get("normalizacion", [])
        self.reconocimiento: str = config.get("reconocimiento", "greedy")
        self.tipo_flujo: str = config.get("tipo_flujo", "titulos")
        self.tipos: list[str] = config.get("tipos", ["TITULO"])
        # Traza (F4): estados recorridos por el último análisis.
        self.ultima_ruta: list[str] = []

    def _build_dfa(self, estados_cfg: list) -> DFA:
        estados: list[str] = []
        transiciones: list[Transicion] = []
        aceptacion: list[str] = []

        # Estado previo obligatorio — los opcionales se omiten por completo
        # (comportamiento del motor legacy: los "(OPCIONAL)" simplemente no
        # se exigen). El ítem inicial del DFA es "__inicio__".
        origen = "__inicio__"
        for e in estados_cfg:
            if e.get("opcional"):
                continue
            estados.append(e["nombre"])
            transiciones.append(
                Transicion(
                    desde=origen,
                    hacia=e["nombre"],
                    patron=e.get("patron", e["nombre"]),
                    consumir=True,
                )
            )
            origen = e["nombre"]

        # Aceptación SOLO en el último estado obligatorio: llegar a él
        # implica que todos los anteriores fueron reconocidos en orden.
        aceptacion = [origen] if estados else []

        return DFA(
            estados=estados,
            transiciones=transiciones,
            inicial="__inicio__",
            aceptacion=aceptacion,
            reconocimiento_backtracking=self.reconocimiento == "backtracking",
            matche=_matchea_legacy,
        )

    def _headings(self, extracted: ExtractedDocx) -> list[str]:
        """Títulos en orden de documento.

        Misma semántica que el legacy `checks._check_secuencia` (pStyle con
        "eading"/"tulo"), pero consume el flujo del tokenizer (F2) en lugar
        de recorrer el XML directamente.
        """
        return [t.texto for t in solo(tokenizar(extracted), [TITULO])]

    def _normalizar(self, s: str) -> str:
        if "mayusculas" in self.normalizacion:
            s = s.upper()
        if "ignorar_indent" in self.normalizacion:
            s = s.strip()
        s = re.sub(r"\s+", " ", s.replace("(OPCIONAL)", " ").strip(" ."))
        return s

    def _caratula_ok(self, extracted: ExtractedDocx) -> bool:
        """La carátula se satisface con el primer párrafo que contenga
        'universidad' (no usa estilo de encabezado)."""
        doc = extracted.document
        for p in doc.xpath("//w:body/w:p", namespaces=NS):
            t = text_of(p).strip()
            if t:
                return "universidad" in t.lower()
        return False

    def _faltantes_legacy(
        self, estados_cfg: list, headings: list[str], cover_ok: bool
    ) -> list[str]:
        """Lista de ítems del esquema que faltan, con la MISMA semántica que
        `checks._check_secuencia` del motor legacy.

        El DFA solo reporta las transiciones alcanzables desde el estado en
        que se atascó; legacy, en cambio, sigue intentando matchear los ítems
        posteriores y solo anota los que no aparecen. Para que el `found` del
        reporte sea idéntico, al fallar se reproduce aquí el recorrido legacy.
        """
        cover_nombres = {"carátula", "caratula"}
        faltantes: list[str] = []
        pos = 0
        for e in estados_cfg:
            if e.get("opcional"):
                continue
            if e.get("nombre", "").lower() in cover_nombres and cover_ok:
                continue
            patron = re.compile(re.sub(r"\s+", " ", e.get("patron", e["nombre"]).strip()))
            found = None
            for k in range(pos, len(headings)):
                if _matchea_legacy(headings[k], patron, True):
                    found = k
                    break
            if found is None:
                faltantes.append(e.get("original", patron.pattern))
            else:
                pos = found + 1
        return faltantes

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        estados_cfg = self.config.get("estados", [])
        if not estados_cfg:
            return False, "sin estados definidos en automata_secuencia"

        # La carátula se satisface con el primer párrafo del documento que
        # mencione "universidad" (cover_ok del motor legacy). Si NO hay
        # portada detectada, el estado carátula se mantiene como ítem
        # obligatorio de la secuencia (mismo comportamiento que legacy).
        cover_nombres = {"carátula", "caratula"}
        if any(e.get("nombre", "").lower() in cover_nombres for e in estados_cfg):
            cover_ok = self._caratula_ok(extracted)
            if cover_ok:
                estados_activos = [
                    e for e in estados_cfg if e.get("nombre", "").lower() not in cover_nombres
                ]
            else:
                estados_activos = estados_cfg
        else:
            cover_ok = False
            estados_activos = estados_cfg

        dfa = self._build_dfa(estados_activos)

        if self.tipo_flujo == "documento":
            headings = _flujo_texto(extracted, self.normalizacion, self.tipo_flujo, self.tipos)
        else:
            headings = [self._normalizar(t) for t in self._headings(extracted) if t]
        aceptado, _ = dfa.reconocer(headings)
        self.ultima_ruta = dfa.ruta_estados

        if aceptado:
            return True, f"headings={len(headings)} faltantes=[]"
        faltantes = self._faltantes_legacy(estados_cfg, headings, cover_ok)
        return False, f"headings={len(headings)} faltantes={faltantes[:6]}"


class GramaticaEstructuraAnalizador(Analizador):
    """Envuelve `GramaticaEstructura` como un Analizador del DSL."""

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        cfg = self.config
        gramatica = GramaticaEstructura(
            reglas_sintacticas=cfg.get("reglas_sintacticas", []),
            terminales=cfg.get("terminales", []),
            no_terminales=cfg.get("no_terminales", []),
            inicio=cfg.get("inicio", ""),
        )

        if cfg.get("tipo_flujo"):
            # La gramática consume el flujo tokenizado (F2): proyecta el
            # texto de los tipos seleccionados y deja que `analizar` lo
            # normalice (mayúsculas) como hace hoy con los headings.
            normalizacion = cfg.get("normalizacion", [])
            flujo = _flujo_texto(
                extracted, normalizacion, cfg["tipo_flujo"], cfg.get("tipos", ["TITULO"])
            )
            aceptado, faltantes = gramatica.analizar(flujo)
            detalle = (
                f"tokens={len(flujo)} gramática_ok"
                if aceptado
                else f"tokens={len(flujo)} faltantes={faltantes[:6]}"
            )
            return aceptado, detalle

        headings = [t.texto for t in solo(tokenizar(extracted), [TITULO])]
        aceptado, faltantes = gramatica.analizar(headings)
        if aceptado:
            return True, f"headings={len(headings)} gramática_ok"
        return False, f"headings={len(headings)} faltantes={faltantes[:6]}"


class AutomataPila(Analizador):
    """Reconoce estructuras ANIDADAS con un autómata de pila (PDA).

    Config DSL (sección `automata_pila`):
      tipo_flujo:   titulos | documento   (default titulos)
      tipos:        tipos de token del flujo documento (default TITULO)
      normalizacion: [mayusculas, ignorar_indent]
      inicial / aceptacion: estados del PDA
      transiciones: [desde, hacia, patron, consumir, push, pop]

    La pila valida ANIDACIÓN (capítulos → secciones) que un DFA no puede:
    `push` abre un nivel, `pop` lo cierra exigiendo el símbolo correcto.
    La aceptación requiere estado final Y pila vacía (estructura cerrada).
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.tipo_flujo: str = config.get("tipo_flujo", "titulos")
        self.tipos: list[str] = config.get("tipos", ["TITULO"])
        self.normalizacion: list[str] = config.get("normalizacion", [])
        self.reconocimiento: str = config.get("reconocimiento", "greedy")
        # Traza (F4): estados recorridos por el último análisis.
        self.ultima_ruta: list[str] = []

    def _build_pda(self) -> PDA:
        transiciones = [
            TransicionPDA(
                desde=t["desde"],
                hacia=t["hacia"],
                patron=t["patron"],
                consumir=t.get("consumir", True),
                push=t.get("push"),
                pop=t.get("pop"),
            )
            for t in self.config.get("transiciones", [])
        ]
        return PDA(
            estados=[t["desde"] for t in self.config.get("transiciones", [])],
            transiciones=transiciones,
            inicial=self.config.get("inicial", "__inicio__"),
            aceptacion=self.config.get("aceptacion", []),
        )

    def _normalizar(self, s: str) -> str:
        return _normalizar_texto(s, self.normalizacion)

    def analizar(self, extracted: ExtractedDocx) -> tuple[bool, str]:
        if not self.config.get("transiciones"):
            return False, "sin transiciones en automata_pila"

        pda = self._build_pda()
        flujo = _flujo_texto(extracted, self.normalizacion, self.tipo_flujo, self.tipos)
        aceptado, faltantes = pda.reconocer(flujo)
        self.ultima_ruta = pda.ruta_estados

        if aceptado:
            return True, f"tokens={len(flujo)} pila_ok"
        return False, f"tokens={len(flujo)} faltantes={faltantes[:6]}"


# ---------------------------------------------------------------------------
# Compilador
# ---------------------------------------------------------------------------

# Mapeo de sección del DSL -> fábrica de Analizador.
# Anotado como Callable para que mypy sepa que fabrica instancias concretas
# (Analizador es abstracto y no se puede instanciar directamente).
_FABRICAS: dict[str, Callable[[dict], Analizador]] = {
    "atributo_xml": AnalizadorXML,
    "presencia_xml": AnalizadorXML,
    "patron_texto": AnalizadorRegex,
    "lista_texto": AnalizadorLista,
    "imagen": AnalizadorImagen,
    "automata_secuencia": AutomataSecuencia,
    "gramatica_estructura": GramaticaEstructuraAnalizador,
    "automata_pila": AutomataPila,
    "patron_cantidad": AnalizadorCantidadPatron,
    "conteo_nodos": AnalizadorConteoNodos,
    "lista_obligatoria": AnalizadorListaObligatoria,
    "hipervinculo_texto": AnalizadorHipervinculo,
    "paginacion": AnalizadorPaginacion,
    "nota_pie": AnalizadorNotaPie,
    "toc_apunta": AnalizadorTocApunta,
    "toc_numeracion": AnalizadorTocNumeracion,
    "deteccion_tipo": DeteccionTipo,
}


def _expone_de(rule: dict) -> str | None:
    """Clave que una regla publica en el contexto.

    Se puede declarar en dos sitios equivalentes: a nivel de la regla, o
    dentro de la sección del analizador que produce el valor (`deteccion_tipo`
    lo hace así, porque la clave describe a ese analizador y no a la regla
    entera). La sección tiene prioridad si aparecen ambas.
    """
    for seccion in SECCIONES_ANALIZADOR:
        cfg = rule.get(seccion)
        if isinstance(cfg, dict) and isinstance(cfg.get("expone"), str):
            return cfg["expone"]
    expone = rule.get("expone")
    return expone if isinstance(expone, str) else None


def _coincide(valor_contexto: object, valor_esperado: object) -> bool:
    """Compara un valor del contexto contra lo que pide una condición.

    Escalar: igualdad exacta. Lista: "cualquiera de estos" (se compara el
    contexto contra cada elemento, sin exigir que la lista esté ordenada ni
    que no tenga repetidos). Una lista vacía no casa con nada: se trata como
    una condición que nunca se cumple, no como una que siempre se cumple.
    """
    if isinstance(valor_esperado, list):
        return any(valor_contexto == candidato for candidato in valor_esperado)
    return valor_contexto == valor_esperado


@dataclass
class ReglaCompilada:
    """Una regla DSL compilada: sus analizadores + metadatos."""

    rule: dict
    analizadores: list[Analizador] = field(default_factory=list)
    # Clave que la regla publica en el contexto del documento (fase 1).
    # `None` si la regla no participa de la detección.
    expone: str | None = None
    # Mapa `clave -> valor` que debe cumplirse para que la regla aplique
    # (fase 2). `None` si la regla es incondicional.
    aplicar_si: dict | None = None

    def aplica_en(self, contexto: dict) -> bool:
        """¿Se cumple la condición `aplicar_si` con el contexto dado?

        Una regla incondicional siempre aplica. Las condiciones son
        conjuntas: todas las claves deben coincidir. Una clave ausente del
        contexto hace que la regla NO aplique (se trata como "sin valor
        conocido", no como "vale cualquier cosa").

        Un valor escalar exige igualdad exacta. Un valor lista significa
        "cualquiera de estos": así una regla puede admitir varios tipos y,
        sobre todo, declarar explícitamente qué hace con un tipo que no se
        pudo determinar en vez de quedar en silencio.
        """
        if self.aplicar_si is None:
            return True
        return all(
            _coincide(contexto.get(clave), valor) for clave, valor in self.aplicar_si.items()
        )

    def valor_para_contexto(self) -> str:
        """Valor que la regla publica en el contexto tras ejecutarse.

        Se toma del primer analizador que haya producido un valor legible por
        máquina (`Analizador.valor`). No se usa `resultado.found`: ese texto
        está escrito para que lo lea una persona, no para comparar. Si ningún
        analizador produce valor, la clave se publica vacía.
        """
        for analizador in self.analizadores:
            valor = getattr(analizador, "valor", None)
            if valor is not None:
                return str(valor)
        return ""

    def no_aplicable(self) -> RuleResult:
        """Resultado de una regla que no le toca a este documento.

        `passed=True` a propósito: una regla no aplicable no ha fallado, y
        no debe poder bloquear la entrega. `aplicable=False` es lo que la
        marca como omitida del reporte.
        """
        esperados = self.rule.get("valor_esperado", "")
        if isinstance(esperados, list):
            esperados = "; ".join(map(str, esperados))
        return RuleResult(
            rule_id=self.rule["id"],
            passed=True,
            severity=Severity(self.rule.get("severidad", "error")),
            message=self.rule.get("descripcion", self.rule["id"]),
            expected=str(esperados),
            found="no aplica a este documento",
            aplicable=False,
            location=self.rule.get("ubicacion") or None,
            fuente=self.rule.get("fuente", ""),
            cita=self.rule.get("cita", ""),
        )

    @staticmethod
    def _detalle_con_traza(detalle: str, analizador: Analizador) -> str:
        """Anexa la traza de estados del autómata (F5).

        Los analizadores de autómatas (`AutomataSecuencia`, `AutomataPila`)
        dejan en `ultima_ruta` la secuencia de estados recorrida por el
        último `reconocer()`. Solo se anexa al detalle cuando la regla FALLA,
        para que el usuario sepa dónde se desvió el documento.
        """
        ruta = getattr(analizador, "ultima_ruta", None)
        if ruta:
            return f"{detalle} ruta={' -> '.join(ruta)}"
        return detalle

    def _detalle_expositor(self, detalles: list[tuple[Analizador, str]]) -> str:
        """Texto a mostrar en `found` cuando la regla PASA y declara `expone`.

        Una regla que `expone` es informativa por definición: en vez del
        genérico "cumple", el reporte debe decir qué se encontró (el tipo de
        documento detectado, por ejemplo). Se usa el detalle del mismo
        analizador cuyo `valor` se publica en el contexto, para que el
        `found` y el valor consumido por `aplicar_si` no puedan divergir.

        Devuelve "" si la regla no expone nada, de modo que el llamador siga
        usando "cumple": el `valor` de un analizador común (p. ej. el valor
        real que lee `AnalizadorXML`) no debe alterar el `found` de las reglas
        que no publican nada en el contexto.
        """
        if not self.expone:
            return ""
        for an, detalle in detalles:
            if getattr(an, "valor", None) is not None:
                return detalle or str(an.valor)
        return ""

    def ejecutar(self, extracted: ExtractedDocx) -> RuleResult:
        fallos: list[str] = []
        pagina: int | None = None
        detalles: list[tuple[Analizador, str]] = []
        for an in self.analizadores:
            try:
                ok, detalle = an.analizar(extracted)
            except Exception as e:  # noqa:BLE001
                ok, detalle = False, f"error ejecutando analizador: {type(e).__name__}: {e}"
            detalles.append((an, detalle))
            if not ok:
                fallos.append(self._detalle_con_traza(detalle, an))
                # Enriquecer la ubicación con la página física real (ítem 1):
                # se usa el nodo objetivo del primer analizador que falló.
                if pagina is None and getattr(an, "ultimo_nodo", None) is not None:
                    pagina = extracted.pagina_de(an.ultimo_nodo)

        esperados = self.rule.get("valor_esperado", "")
        if isinstance(esperados, list):
            esperados = "; ".join(map(str, esperados))

        ubicacion = self.rule.get("ubicacion") or ""
        if fallos and pagina is not None and ubicacion:
            ubicacion = f"{ubicacion}; página {pagina}"

        return RuleResult(
            rule_id=self.rule["id"],
            passed=not fallos,
            severity=Severity(self.rule.get("severidad", "error")),
            message=self.rule.get("descripcion", self.rule["id"]),
            expected=str(esperados),
            found="; ".join(fallos) if fallos else (self._detalle_expositor(detalles) or "cumple"),
            location=ubicacion or None,
            fuente=self.rule.get("fuente", ""),
            cita=self.rule.get("cita", ""),
        )


# Los dos estados en que la detección NO pudo clasificar el documento. Son
# estados terminales: no son un tipo más, son la ausencia de uno. Cada uno
# lleva un error propio, accionable, en vez de validar el documento contra
# todos los esquemas posibles (decisión 6 del diseño,
# docs/diseno/15_tipo_documento_grupos.md).
#
#   - Con el paso 4, `sin_determinar` y `contradictorio` activaban las TRES
#     estructuras y el estudiante veía 2 errores de estructura que no podía
#     corregir sin adivinar el tipo. El problema real —"no sabemos qué tipo
#     es esto"— se escondía detrás de simétricos errores de secciones.
#   - Aquí las estructuras solo aplican a su tipo exacto, así que en estos dos
#     casos no se evalúa ninguna: sale 1 error que dice qué hacer.
#
# El `found` se completa con el detalle real de la detección (qué firmas se
# buscaron y no casaron, o qué declaración choca con qué firma), para que el
# estudiante vea la evidencia, no solo el veredicto.
# La severidad del centinela depende del estado:
#   - `sin_determinar` y `contradictorio` son estados terminales que impiden
#     validar la estructura → error bloquante.
#   - Los tipos de proyecto, informe y TSP todavía NO tienen una estructura
#     cargada (viven en `reglas_unt_pendientes.yaml`, que la API no carga).
#     El documento se valida con las reglas generales y queda avisado con un
#     warning: no se vende un "verde" que no validó el capítulo de
#     metodología, pero tampoco se bloquea a un estudiante que sí eligió bien.
class _SentinelSpec(TypedDict):
    rule_id: str
    message: str
    expected: str
    severity: Severity


_SENTINELAS: dict[str, _SentinelSpec] = {
    TIPO_SIN_DETERMINAR: {
        "rule_id": "tipo_documento_no_determinado",
        "message": (
            "No se pudo determinar el tipo de documento, así que no se validó "
            "la estructura del capítulo de metodología. Causa probable: el "
            "Anexo 10 no tiene ninguna casilla marcada y el documento no "
            "trae secciones que identifiquen su esquema."
        ),
        "expected": "un tipo de documento de entre los 8 esquemas de la UNT",
        "severity": Severity.ERROR,
    },
    TIPO_CONTRADICTORIO: {
        "rule_id": "tipo_documento_contradictorio",
        "message": (
            "El tipo de documento no es coherente: la declaración del Anexo 10 "
            "no coincide con el que se deduce de la estructura del documento. "
            "Corrige la casilla del Anexo 10 o corrige el capítulo de "
            "metodología, para que ambos digan lo mismo. Hasta entonces no se "
            "puede validar la estructura de ningún esquema."
        ),
        "expected": "declaración del Anexo 10 y estructura del documento del mismo tipo",
        "severity": Severity.ERROR,
    },
    "proyecto_cuantitativo": {
        "rule_id": "tipo_documento_sin_estructura",
        "message": (
            "El documento es un PROYECTO DE INVESTIGACIÓN CUANTITATIVO, cuyo "
            "esquema formal todavía no tiene validación estructural en el "
            "validador: solo se validan las reglas generales de formato."
        ),
        "expected": "estructura de proyecto cuantitativo",
        "severity": Severity.WARNING,
    },
    "proyecto_cualitativo": {
        "rule_id": "tipo_documento_sin_estructura",
        "message": (
            "El documento es un PROYECTO DE INVESTIGACIÓN CUALITATIVO, cuyo "
            "esquema formal todavía no tiene validación estructural en el "
            "validador: solo se validan las reglas generales de formato."
        ),
        "expected": "estructura de proyecto cualitativo",
        "severity": Severity.WARNING,
    },
    "informe_cuantitativo": {
        "rule_id": "tipo_documento_sin_estructura",
        "message": (
            "El documento es un INFORME DE PROYECTO CUANTITATIVO, cuyo "
            "esquema formal todavía no tiene validación estructural en el "
            "validador: solo se validan las reglas generales de formato."
        ),
        "expected": "estructura de informe cuantitativo",
        "severity": Severity.WARNING,
    },
    "informe_cualitativo": {
        "rule_id": "tipo_documento_sin_estructura",
        "message": (
            "El documento es un INFORME DE PROYECTO CUALITATIVO, cuyo esquema "
            "formal todavía no tiene validación estructural en el validador: "
            "solo se validan las reglas generales de formato."
        ),
        "expected": "estructura de informe cualitativo",
        "severity": Severity.WARNING,
    },
    "tsp": {
        "rule_id": "tipo_documento_sin_estructura",
        "message": (
            "El documento es un TRABAJO DE SUFICIENCIA PROFESIONAL, cuyo "
            "esquema formal todavía no tiene validación estructural en el "
            "validador: solo se validan las reglas generales de formato."
        ),
        "expected": "estructura de trabajo de suficiencia profesional",
        "severity": Severity.WARNING,
    },
}


def _con_sentinel(resultados: list[RuleResult | None], contexto: dict) -> list[RuleResult]:
    """Agrega el resultado centinela según el `tipo_documento` publicado.

    Va justo después de la regla de detección, que es donde el estudiante
    empieza a leer. El resto de reglas se conserva en el orden del YAML: este
    resultado no es una regla del YAML, es la traducción de un estado de la
    detección (error terminal o aviso de falta de validación estructural).
    """
    spec = _SENTINELAS.get(contexto.get("tipo_documento", ""))
    if spec is None:
        return [r for r in resultados if r is not None]

    # El detalle de la detección es la evidencia: sin él el estudiante sabe
    # que no se clasificó (o qué tipo salió), pero no por qué.
    detalle = ""
    for r in resultados:
        if r is not None and r.rule_id == "deteccion_tipo_documento":
            detalle = r.found
            break
    sentinela = RuleResult(
        rule_id=spec["rule_id"],
        passed=False,
        severity=spec["severity"],
        message=spec["message"],
        expected=spec["expected"],
        found=detalle or "sin detalle",
        # El estudiante no puede "corregir esto" sin el reglamento, así que
        # se le da la referencia que permite rastrear el origen.
        location="Capítulo II — esquemas formales por tipo de título (párr. 75-90)",
        fuente="MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx",
        cita="Cada título profesional exige un esquema formal distinto",
    )
    salida: list[RuleResult | None] = list(resultados)
    for i, r in enumerate(resultados):
        if r is not None and r.rule_id == "deteccion_tipo_documento":
            salida.insert(i + 1, sentinela)
            break
    return [r for r in salida if r is not None]


class CompilerDSL:
    """Compila el YAML DSL en un conjunto de `ReglaCompilada`."""

    def compilar(self, rules_data: dict, linter: bool = True) -> list[ReglaCompilada]:
        if linter:
            # Error de configuración (regex, comparacion, autómatas) se
            # detecta AL CARGAR, no al validar contra un documento (F4).
            linter_o_alzar(rules_data)
        reglas: list[ReglaCompilada] = []
        for rule in rules_data.get("reglas", []):
            analizadores = []
            # Se recorren las secciones en el orden en que aparecen en la
            # regla (no en orden fijo) para preservar el orden de checks del
            # formato legacy y producir detalles idénticos al unirse los fallos.
            for seccion in rule:
                if seccion not in SECCIONES_ANALIZADOR:
                    continue
                fabrica = _FABRICAS.get(seccion)
                if fabrica is None:
                    continue
                # Una sección puede declarar una sola comprobación (dict)
                # o varias del mismo tipo (lista) — se compilan como
                # analizadores independientes que TODOS deben cumplirse.
                configs = rule[seccion]
                if isinstance(configs, list):
                    for cfg in configs:
                        analizadores.append(fabrica(cfg))
                else:
                    analizadores.append(fabrica(configs))
            if not analizadores:
                # Regla declarada pero sin analizadores: no mecanizada.
                continue
            reglas.append(
                ReglaCompilada(
                    rule=rule,
                    analizadores=analizadores,
                    expone=_expone_de(rule),
                    aplicar_si=rule.get("aplicar_si"),
                )
            )
        return reglas

    def ejecutar(self, rules_data: dict, extracted: ExtractedDocx) -> list[RuleResult]:
        """Evalúa las reglas en dos fases y devuelve los resultados.

        **Fase 1** — reglas sin `aplicar_si`. Se ejecutan todas y las que
        declaran `expone` publican su valor en el contexto del documento.

        **Fase 2** — reglas con `aplicar_si`. Aplican solo si su condición se
        cumple contra el contexto; si no, se marcan como no aplicables.

        El orden de salida es el del YAML, no el de las fases: se preasignan
        los huecos y se rellenan por fase, de modo que el reporte no cambia
        de orden respecto de la evaluación de una sola pasada.
        """
        reglas = self.compilar(rules_data)
        contexto: dict[str, str] = {}
        resultados: list[RuleResult | None] = [None] * len(reglas)

        for i, r in enumerate(reglas):
            if r.aplicar_si is None:
                res = r.ejecutar(extracted)
                resultados[i] = res
                if r.expone:
                    contexto[r.expone] = r.valor_para_contexto()

        for i, r in enumerate(reglas):
            if r.aplicar_si is None:
                continue
            resultados[i] = r.ejecutar(extracted) if r.aplica_en(contexto) else r.no_aplicable()

        return _con_sentinel(resultados, contexto)
