#!/usr/bin/env python3
"""Migra `unt_format_rules_schema.yaml` (formato legacy) al formato DSL.

Convierte las reglas con `mecanismo_verificable` del formato `rules` +
`mecanismo_verificable.checks` al formato declarativo `reglas` con
secciones de analizadores/autómatas (`atributo_xml`, `patron_texto`,
`automata_secuencia`, ...). Fase F1 del PLAN_DSL.

Las reglas SIN mecanismo (semánticas, no verificables por estructura de
archivo) NO migran: quedan en el YAML legacy y el motor las omite.

Mapeo de tipos de check legacy -> sección DSL:
    xml_atributo      -> atributo_xml   (AnalizadorXML)
    xml_presencia     -> presencia_xml  (AnalizadorXML)
    texto_regex       -> patron_texto   (AnalizadorRegex, comparacion fullmatch)
    texto_en_lista    -> lista_texto    (AnalizadorLista)
    imagen_presencia  -> imagen         (AnalizadorImagen)
    secuencia_titulos -> automata_secuencia (AutomataSecuencia/DFA)

Para `secuencia_titulos`, los estados del DFA se generan desde
`valor_esperado` y el matcher del DSL preserva la semántica legacy
(startswith + prefijo + token significativo) — ver compilador.py.

Salida: `reglas_unt.yaml` (32 reglas). La API sigue cargando el YAML
legacy (`unt_format_rules_schema.yaml`); este archivo es el objetivo de
la F1 y alimenta su test de paridad.

Uso:
    python scripts/migrar_legacy_a_dsl.py [--salida reglas_unt.yaml]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

RAIZ = Path(__file__).resolve().parent.parent
LEGACY_YAML = RAIZ / "unt_format_rules_schema.yaml"

# Sección DSL por tipo de check legacy.
CHECK_A_SECCION = {
    "xml_atributo": "atributo_xml",
    "xml_presencia": "presencia_xml",
    "texto_regex": "patron_texto",
    "texto_en_lista": "lista_texto",
    "imagen_presencia": "imagen",
    "secuencia_titulos": "automata_secuencia",
}

# Tipo (etiqueta descriptiva) de la regla DSL desde el primer check.
PRIMER_TIPO = {
    "xml_atributo": "atributo_xml",
    "xml_presencia": "presencia_xml",
    "texto_regex": "patron_texto",
    "texto_en_lista": "lista_texto",
    "imagen_presencia": "imagen",
    "secuencia_titulos": "secuencia",
}


def _normalizar_item(s: str) -> str:
    """Normalización idéntica a `checks._check_secuencia`.norm."""
    return re.sub(r"\s+", " ", s.upper().replace("(OPCIONAL)", " ").strip(" ."))


def _slug(s: str) -> str:
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"),
                 ("ú", "u"), ("ñ", "n")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "item"


def _estados_secuencia(valor_esperado: List[str]) -> List[Dict[str, Any]]:
    """Genera los estados del DFA desde la lista de títulos del manual.

    Cada estado preserva el ítem original (`original`) para que el
    reporte de faltantes reproduzca el texto del valor_esperado tal cual.
    La carátula se nombres "caratula" para activar la detección por
    párrafo de portada del DSL.
    """
    estados: List[Dict[str, Any]] = []
    for item in valor_esperado:
        nombre = _slug(item)
        if nombre.startswith("caratul"):
            nombre = "caratula"
        estado: Dict[str, Any] = {
            "nombre": nombre,
            "patron": _normalizar_item(item),
            "original": item,
        }
        if "(OPCIONAL)" in item.upper():
            estado["opcional"] = True
        estados.append(estado)
    return estados


def _cfg_atributo(check: dict) -> dict:
    return {
        "parte": check.get("parte", "document"),
        "contexto": check.get("contexto", "todos"),
        "xpath": check["xpath"],
        "atributo": check["atributo"],
        "comparacion": check.get("comparacion", "eq"),
        "esperado": check.get("esperado"),
    }


def _cfg_presencia(check: dict) -> dict:
    return {
        "parte": check.get("parte", "document"),
        "contexto": check.get("contexto", "todos"),
        "xpath": check["xpath"],
        "comparacion": check.get("comparacion", "exists"),
    }


def _cfg_regex(check: dict) -> dict:
    return {
        "parte": check.get("parte", "document"),
        "contexto": check.get("contexto", "todos"),
        "xpath": check["xpath"],
        "patron": check["patron"],
        # El motor legacy aplicaba patron.fullmatch sobre cada w:t.
        "comparacion": "fullmatch",
        "coincidencia": "todos",
    }


def _cfg_lista(check: dict) -> dict:
    return {
        "parte": check.get("parte", "document"),
        "contexto": check.get("contexto", "todos"),
        "xpath": check["xpath"],
        "lista": check.get("lista", []),
        "ignore_case": check.get("ignore_case", False),
    }


def _cfg_imagen(check: dict) -> dict:
    cfg = {
        "parte": check.get("parte", "document"),
        "xpath": check["xpath"],
    }
    if check.get("formato"):
        cfg["formato"] = check["formato"]
    if check.get("cantidad_minima") is not None:
        cfg["cantidad_minima"] = check["cantidad_minima"]
    return cfg


def _cfg_secuencia(rule: dict) -> dict:
    return {
        "normalizacion": ["mayusculas", "ignorar_indent"],
        "reconocimiento": "greedy",
        "estados": _estados_secuencia(rule.get("valor_esperado", [])),
    }


_FABRICANTES = {
    "xml_atributo": _cfg_atributo,
    "xml_presencia": _cfg_presencia,
    "texto_regex": _cfg_regex,
    "texto_en_lista": _cfg_lista,
    "imagen_presencia": _cfg_imagen,
    "secuencia_titulos": _cfg_secuencia,
}


def _migrar_rule(rule: dict) -> dict:
    checks = rule["mecanismo_verificable"]["checks"]
    grupos: Dict[str, List[dict]] = {}
    for check in checks:
        tipo = check["tipo"]
        if tipo == "secuencia_titulos":
            # Los estados del DFA se generan desde el valor_esperado de la
            # regla (no del check), por eso se pasa `rule`, no `check`.
            formulario = _cfg_secuencia(rule)
        else:
            formulario = _FABRICANTES[tipo](check)
        seccion = CHECK_A_SECCION[tipo]
        grupos.setdefault(seccion, []).append(formulario)

    dsl_rule: Dict[str, Any] = {
        "id": rule["id"],
        "tipo": PRIMER_TIPO.get(checks[0]["tipo"], "estructura"),
        "descripcion": rule.get("descripcion", ""),
        "valor_esperado": rule.get("valor_esperado"),
        "severidad": rule.get("severidad", "error"),
    }
    for k in ("ubicacion", "fuente", "cita"):
        if rule.get(k):
            dsl_rule[k] = rule[k]

    for seccion, cfgs in grupos.items():
        # Una sola comprobación -> dict; varias del mismo tipo -> lista.
        dsl_rule[seccion] = cfgs[0] if len(cfgs) == 1 else cfgs

    return dsl_rule


def migrar(rules_data: dict) -> dict:
    """Convierte el YAML legacy (clave `rules`) al formato DSL (`reglas`)."""
    reglas = []
    sin_mecanismo = 0
    for rule in rules_data.get("rules", []):
        mecanismo = rule.get("mecanismo_verificable")
        if not mecanismo:
            sin_mecanismo += 1
            continue
        reglas.append(_migrar_rule(rule))

    return {
        "version": rules_data.get("version", "desconocido"),
        "namespaces": {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
            "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
        },
        "reglas": reglas,
        "_migracion": {
            "fuente": "unt_format_rules_schema.yaml",
            "total_reglas": len(reglas),
            "sin_mecanismo_omitidas": sin_mecanismo,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra el YAML legacy al formato DSL.")
    parser.add_argument("--salida", default=str(RAIZ / "reglas_unt.yaml"))
    args = parser.parse_args()

    with open(LEGACY_YAML, encoding="utf-8") as f:
        legacy = yaml.safe_load(f)

    dsl = migrar(legacy)
    salida = Path(args.salida)
    salida.write_text(
        "# ============================================================\n"
        "# REGLAS UNT EN FORMATO DSL — GENERADO POR scripts/migrar_legacy_a_dsl.py\n"
        "# ------------------------------------------------------------\n"
        "# Migración de `unt_format_rules_schema.yaml` (formato legacy) al\n"
        "# formato declarativo (Fase F1 del PLAN_DSL). Desde la F5 la API\n"
        "# (`api.py`) carga ESTE archivo y las reglas F3 mecanizadas a mano.\n"
        "# Se usa para el test de paridad legacy-vs-DSL y como base de las\n"
        "# fases siguientes (unificación de YAML, F3).\n"
        "# ============================================================\n\n",
        encoding="utf-8",
    )
    with salida.open("a", encoding="utf-8") as f:
        yaml.dump(
            dsl,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=100,
        )

    print(f"Migradas {len(dsl['reglas'])} reglas a {salida}")
    print(f"(omitidas {dsl['_migracion']['sin_mecanismo_omitidas']} reglas sin mecanismo)")


if __name__ == "__main__":
    main()