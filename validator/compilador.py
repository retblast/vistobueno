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

La regla también conserva metadatos (descripcion, severidad, etc.) que
se propagan al `RuleResult` resultante.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .analizadores import (
    Analizador,
    AnalizadorCantidadPatron,
    AnalizadorConteoNodos,
    AnalizadorHipervinculo,
    AnalizadorImagen,
    AnalizadorLista,
    AnalizadorListaObligatoria,
    AnalizadorRegex,
    AnalizadorXML,
)
from .automata import DFA, GramaticaEstructura, PDA, Transicion, TransicionPDA
from .dsl_check import linter_o_alzar
from .extractor import ExtractedDocx, NS, text_of
from .tokenizer import TITULO, solo, textos, tokenizar
from .models import RuleResult, Severity

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


def _normalizar_texto(s: str, normalizacion: List[str]) -> str:
    """Normaliza el texto de un token igual que `AutomataSecuencia`."""
    if "mayusculas" in normalizacion:
        s = s.upper()
    if "ignorar_indent" in normalizacion:
        s = s.strip()
    s = re.sub(r"\s+", " ", s.replace("(OPCIONAL)", " ").strip(" ."))
    return s


def _flujo_texto(
    extracted: ExtractedDocx, normalizacion: List[str], tipo_flujo: str, tipos
) -> List[str]:
    """Proyección de texto (normalizada) del flujo tokenizado.

    `tipo_flujo: titulos` (default) usa SOLO los títulos — reproduce la
    proyección histórica `_headings()` (paridad). `tipo_flujo: documento`
    usa el flujo completo filtrado por `tipos` (TITULO, PARRAFO, TABLA,
    IMAGEN, SALTO_SECCION).
    """
    tipos_flujo = tipos if tipo_flujo == "documento" else ["TITULO"]
    return [
        _normalizar_texto(t.texto, normalizacion)
        for t in solo(tokenizar(extracted), tipos_flujo)
    ]


class AutomataSecuencia(Analizador):
    """Reconoce una secuencia de títulos usando un DFA.

    Construye el autómata a partir de `automata_secuencia.estados`,
    `inicial` y `aceptacion`. Cada estado es un patrón (regex sobre el
    heading normalizado) que, al ser reconocido, transita al siguiente.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.nivel_titulo: List[int] = config.get("nivel_titulo", [1, 2, 3])
        self.normalizacion: List[str] = config.get("normalizacion", [])
        self.reconocimiento: str = config.get("reconocimiento", "greedy")
        self.tipo_flujo: str = config.get("tipo_flujo", "titulos")
        self.tipos: List[str] = config.get("tipos", ["TITULO"])
        # Traza (F4): estados recorridos por el último análisis.
        self.ultima_ruta: List[str] = []

    def _build_dfa(self, estados_cfg: list) -> DFA:
        estados: List[str] = []
        transiciones: List[Transicion] = []
        aceptacion: List[str] = []

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

    def _headings(self, extracted: ExtractedDocx) -> List[str]:
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
        self, estados_cfg: list, headings: List[str], cover_ok: bool
    ) -> List[str]:
        """Lista de ítems del esquema que faltan, con la MISMA semántica que
        `checks._check_secuencia` del motor legacy.

        El DFA solo reporta las transiciones alcanzables desde el estado en
        que se atascó; legacy, en cambio, sigue intentando matchear los ítems
        posteriores y solo anota los que no aparecen. Para que el `found` del
        reporte sea idéntico, al fallar se reproduce aquí el recorrido legacy.
        """
        cover_nombres = {"carátula", "caratula"}
        faltantes: List[str] = []
        pos = 0
        for e in estados_cfg:
            if e.get("opcional"):
                continue
            if e.get("nombre", "").lower() in cover_nombres and cover_ok:
                continue
            patron = re.compile(
                re.sub(r"\s+", " ", e.get("patron", e["nombre"]).strip())
            )
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

    def analizar(self, extracted: ExtractedDocx) -> Tuple[bool, str]:
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
                    e for e in estados_cfg
                    if not (e.get("nombre", "").lower() in cover_nombres)
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

    def analizar(self, extracted: ExtractedDocx) -> Tuple[bool, str]:
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
            flujo = _flujo_texto(extracted, normalizacion, cfg["tipo_flujo"], cfg.get("tipos", ["TITULO"]))
            aceptado, faltantes = gramatica.analizar(flujo)
            detalle = f"tokens={len(flujo)} gramática_ok" if aceptado else f"tokens={len(flujo)} faltantes={faltantes[:6]}"
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
        self.tipos: List[str] = config.get("tipos", ["TITULO"])
        self.normalizacion: List[str] = config.get("normalizacion", [])
        self.reconocimiento: str = config.get("reconocimiento", "greedy")
        # Traza (F4): estados recorridos por el último análisis.
        self.ultima_ruta: List[str] = []

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

    def analizar(self, extracted: ExtractedDocx) -> Tuple[bool, str]:
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
_FABRICAS = {
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
}


@dataclass
class ReglaCompilada:
    """Una regla DSL compilada: sus analizadores + metadatos."""

    rule: dict
    analizadores: List[Analizador] = field(default_factory=list)

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

    def ejecutar(self, extracted: ExtractedDocx) -> RuleResult:
        fallos: List[str] = []
        for an in self.analizadores:
            try:
                ok, detalle = an.analizar(extracted)
            except Exception as e:  # noqa:BLE001
                ok, detalle = False, f"error ejecutando analizador: {type(e).__name__}: {e}"
            if not ok:
                fallos.append(self._detalle_con_traza(detalle, an))

        esperados = self.rule.get("valor_esperado", "")
        if isinstance(esperados, list):
            esperados = "; ".join(map(str, esperados))
        return RuleResult(
            rule_id=self.rule["id"],
            passed=not fallos,
            severity=Severity(self.rule.get("severidad", "error")),
            message=self.rule.get("descripcion", self.rule["id"]),
            expected=str(esperados),
            found="; ".join(fallos) if fallos else "cumple",
            location=self.rule.get("ubicacion"),
            fuente=self.rule.get("fuente", ""),
            cita=self.rule.get("cita", ""),
        )


class CompilerDSL:
    """Compila el YAML DSL en un conjunto de `ReglaCompilada`."""

    def compilar(self, rules_data: dict, linter: bool = True) -> List[ReglaCompilada]:
        if linter:
            # Error de configuración (regex, comparacion, autómatas) se
            # detecta AL CARGAR, no al validar contra un documento (F4).
            linter_o_alzar(rules_data)
        reglas: List[ReglaCompilada] = []
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
            reglas.append(ReglaCompilada(rule=rule, analizadores=analizadores))
        return reglas

    def ejecutar(self, rules_data: dict, extracted: ExtractedDocx) -> List[RuleResult]:
        return [r.ejecutar(extracted) for r in self.compilar(rules_data)]
