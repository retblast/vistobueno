"""Aceptación de M1: formato efectivo de runs y párrafos (VA-01/VA-02).

El motor legacy leía solo el primer run del párrafo (`w:r[1]`) y solo el
formato directo. Estos tests fijan el comportamiento nuevo:

- se evalúan **todos** los runs con texto, incluidos los hipervínculos, y
  un run vacío no exime al párrafo;
- el valor efectivo se resuelve con la precedencia de Word: directo →
  estilo de carácter → cadena `basedOn` del estilo de párrafo →
  `docDefaults`;
- una propiedad que no aparece en ninguna capa se reporta como `(ausente)`
  y cuenta como incumplimiento;
- un ciclo de estilos o un `styles.xml` mal formado no tumban la
  validación: la regla afectada falla y el resto del documento se evalúa.

Los límites (temas, numeración, formato condicional, estilos de tabla y
cambios con seguimiento) están documentados en `ResolvedorFormato`; no se
promete soporte completo por leer `basedOn`.

Uso:
    pytest tests/test_formato_efectivo.py -v
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from docx_factory import compilar_docx, configuracion_base

from validator.engine import load_rules, validate_docx
from validator.extractor import NS

RAIZ = Path(__file__).resolve().parent.parent
RULES = load_rules(str(RAIZ / "reglas_unt.yaml"))


def _regla(path: str, rule_id: str, reglas: dict = RULES):
    """Resultado de una regla concreta (o None si no se evaluó)."""
    for resultado in validate_docx(path, reglas):
        if resultado.rule_id == rule_id:
            return resultado
    return None


def _validar(cfg: dict, rule_id: str, reglas: dict = RULES):
    path = compilar_docx(cfg)
    try:
        return _regla(path, rule_id, reglas)
    finally:
        os.unlink(path)


def _estilos(estilos: dict) -> dict:
    """Configura `word/styles.xml` con los estilos indicados."""
    return {"estilos": estilos}


# ---------------------------------------------------------------------------
# Runs: se evalúan todos los que tienen texto
# ---------------------------------------------------------------------------


def test_run_vacio_no_exime_al_segundo_run():
    """Un `w:r` vacío al inicio no evita evaluar el run que sí tiene texto.

    Era el defecto de VA-01: `w:r[1]` seleccionaba el run vacío y el run
    incorrecto pasaba inadvertido.
    """
    cfg = configuracion_base()
    cfg["cuerpo_run_vacio"] = True
    cfg["cuerpo_runs_extra"] = [
        {
            "texto": "Texto adicional.",
            "rpr": '<w:rFonts w:ascii="Arial"/><w:sz w:val="72"/>',
        }
    ]
    fuente = _validar(cfg, "fuente_principal")
    assert fuente is not None
    assert not fuente.passed, "el run con Arial debe hacer fallar la regla"
    assert "Arial" in fuente.found, fuente.found
    assert "6 valores evaluados" in fuente.found, fuente.found

    tamano = _validar(cfg, "tamano_cuerpo")
    assert tamano is not None
    assert not tamano.passed, "el segundo run con 36 pt debe detectarse"
    assert "36 pt" in tamano.found, tamano.found


def test_hipervinculo_se_evalua_como_un_run_normal():
    """El texto dentro de `w:hyperlink` también es texto del cuerpo."""
    cfg = configuracion_base()
    cfg["cuerpo_hipervinculo"] = {
        "texto": "https://example.org/",
        "rpr": '<w:rFonts w:ascii="Arial"/><w:sz w:val="30"/>',
    }
    regla = _validar(cfg, "fuente_principal")
    assert regla is not None
    assert not regla.passed, "el run del hipervínculo debe evaluarse"
    assert "Arial" in regla.found, regla.found


def test_hipervinculo_con_formato_correcto_cumple():
    """Un hipervínculo con el formato esperado no se marca como ausente."""
    cfg = configuracion_base()
    cfg["cuerpo_hipervinculo"] = {}
    regla = _validar(cfg, "fuente_principal")
    assert regla is not None
    assert regla.passed, regla.found


# ---------------------------------------------------------------------------
# Herencia: estilo de párrafo, estilo de carácter, basedOn y docDefaults
# ---------------------------------------------------------------------------


def test_formato_heredado_del_estilo_de_parrafo_cumple():
    """El formato del estilo de párrafo es el formato efectivo del run."""
    cfg = configuracion_base()
    cfg["cuerpo_sin_formato"] = True
    cfg["cuerpo_estilo"] = "CuerpoUN"
    cfg["styles"] = _estilos(
        {
            "CuerpoUN": {
                "type": "paragraph",
                "rpr": (
                    '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                    '<w:sz w:val="24"/>'
                ),
                "ppr": '<w:spacing w:line="360" w:lineRule="auto"/><w:jc w:val="both"/>',
            }
        }
    )
    for rule_id in ("fuente_principal", "tamano_cuerpo", "interlineado", "alineacion_cuerpo"):
        regla = _validar(cfg, rule_id)
        assert regla is not None, f"{rule_id} no se evaluó"
        assert regla.passed, f"{rule_id}: {regla.found}"


def test_estilo_de_parrafo_incorrecto_falla():
    """Si el estilo declara otro formato, la regla no puede darlo por bueno."""
    cfg = configuracion_base()
    cfg["cuerpo_sin_formato"] = True
    cfg["cuerpo_estilo"] = "CuerpoUN"
    cfg["styles"] = _estilos(
        {
            "CuerpoUN": {
                "type": "paragraph",
                "rpr": '<w:rFonts w:ascii="Arial"/><w:sz w:val="30"/>',
                "ppr": '<w:spacing w:line="240" w:lineRule="auto"/><w:jc w:val="left"/>',
            }
        }
    )
    fuente = _validar(cfg, "fuente_principal")
    assert fuente is not None and not fuente.passed
    assert "Arial" in fuente.found, fuente.found

    alineacion = _validar(cfg, "alineacion_cuerpo")
    assert alineacion is not None and not alineacion.passed
    assert "left" in alineacion.found, alineacion.found


def test_estilo_de_caracter_aporta_el_formato_del_run():
    """`w:rStyle` se resuelve antes que el estilo de párrafo."""
    cfg = configuracion_base()
    cfg["cuerpo_estilo_caracter"] = "CaracterUN"
    cfg["styles"] = _estilos(
        {
            "CaracterUN": {
                "type": "character",
                "rpr": '<w:rFonts w:ascii="Times New Roman"/><w:sz w:val="24"/>',
            }
        }
    )
    for rule_id in ("fuente_principal", "tamano_cuerpo"):
        regla = _validar(cfg, rule_id)
        assert regla is not None, f"{rule_id} no se evaluó"
        assert regla.passed, f"{rule_id}: {regla.found}"


def test_formato_directo_prevalece_sobre_el_estilo():
    """Un `w:rPr` directo con Arial gana aunque el estilo sea correcto."""
    cfg = configuracion_base()
    cfg["cuerpo_estilo"] = "CuerpoUN"
    cfg["styles"] = _estilos(
        {
            "CuerpoUN": {
                "type": "paragraph",
                "rpr": '<w:rFonts w:ascii="Times New Roman"/><w:sz w:val="24"/>',
            }
        }
    )
    cfg["cuerpo_runs_extra"] = [
        {
            "texto": "Texto con formato directo.",
            "rpr": '<w:rFonts w:ascii="Arial"/><w:sz w:val="24"/>',
        }
    ]
    regla = _validar(cfg, "fuente_principal")
    assert regla is not None
    assert not regla.passed, "el formato directo debe ganar sobre el estilo"
    assert "Arial" in regla.found, regla.found


def test_cadena_based_on_hereda_el_formato():
    """El estilo de párrafo hereda las propiedades de su `basedOn`."""
    cfg = configuracion_base()
    cfg["cuerpo_sin_formato"] = True
    cfg["cuerpo_estilo"] = "CuerpoUN"
    cfg["styles"] = _estilos(
        {
            "BaseUN": {
                "type": "paragraph",
                "rpr": '<w:rFonts w:ascii="Times New Roman"/><w:sz w:val="24"/>',
            },
            "CuerpoUN": {"type": "paragraph", "basedOn": "BaseUN"},
        }
    )
    for rule_id in ("fuente_principal", "tamano_cuerpo"):
        regla = _validar(cfg, rule_id)
        assert regla is not None, f"{rule_id} no se evaluó"
        assert regla.passed, f"{rule_id}: {regla.found}"


def test_ciclo_de_estilos_se_reporta_sin_tumbar_la_validacion():
    """Un ciclo `basedOn` es un incumplimiento, no una excepción del motor."""
    cfg = configuracion_base()
    cfg["cuerpo_sin_formato"] = True
    cfg["cuerpo_estilo"] = "A"
    cfg["styles"] = _estilos(
        {
            "A": {"type": "paragraph", "basedOn": "B"},
            "B": {"type": "paragraph", "basedOn": "A"},
        }
    )
    regla = _validar(cfg, "fuente_principal")
    assert regla is not None
    assert not regla.passed
    assert "ciclo de estilos" in regla.found, regla.found
    assert "A -> B -> A" in regla.found, regla.found


# ---------------------------------------------------------------------------
# Propiedad ausente y styles.xml no disponible
# ---------------------------------------------------------------------------


def test_propiedad_ausente_cuenta_como_incumplimiento():
    """Sin formato directo ni heredado, la propiedad se reporta ausente."""
    cfg = configuracion_base()
    cfg["cuerpo_sin_formato"] = True
    for rule_id in ("fuente_principal", "tamano_cuerpo", "interlineado"):
        regla = _validar(cfg, rule_id)
        assert regla is not None, f"{rule_id} no se evaluó"
        assert not regla.passed, f"{rule_id} no puede darse por bueno"
        assert "(ausente)" in regla.found, regla.found


def test_styles_xml_mal_formado_se_trata_como_ausente():
    """Un `styles.xml` truncado no tumba la validación (M1a/M1)."""
    cfg = configuracion_base()
    cfg["cuerpo_sin_formato"] = True
    cfg["styles_xml_malo"] = True
    regla = _validar(cfg, "fuente_principal")
    assert regla is not None, "la validación completa debe seguir funcionando"
    assert not regla.passed
    assert "(ausente)" in regla.found, regla.found


# ---------------------------------------------------------------------------
# Títulos: la exclusión es un alcance declarado, no una exención implícita
# ---------------------------------------------------------------------------


def _docx_con_titulo_en_arial() -> str:
    """DOCX del factory con un Título1 del cuerpo en Arial."""
    origen = compilar_docx(configuracion_base())
    destino = f"{origen}.titulo"
    with zipfile.ZipFile(origen) as z:
        nombres = z.namelist()
        datos = {n: z.read(n) for n in nombres}
    xml = datos["word/document.xml"].decode("utf-8")
    viejo = '<w:r><w:t xml:space="preserve">1.3. EL PROBLEMA</w:t></w:r>'
    nuevo = (
        '<w:r><w:rPr><w:rFonts w:ascii="Arial"/><w:sz w:val="30"/></w:rPr>'
        '<w:t xml:space="preserve">1.3. EL PROBLEMA</w:t></w:r>'
    )
    assert viejo in xml, "no se encontró el título del cuerpo en el fixture"
    datos["word/document.xml"] = xml.replace(viejo, nuevo, 1).encode("utf-8")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in nombres:
            z.writestr(nombre, datos[nombre])
    os.unlink(origen)
    return destino


def test_contexto_cuerpo_excluye_los_titulos_declarados():
    """El alcance de `contexto: cuerpo` deja fuera los títulos (documentado)."""
    path = _docx_con_titulo_en_arial()
    try:
        regla = _regla(path, "fuente_principal")
    finally:
        os.unlink(path)
    assert regla is not None
    assert regla.passed, (
        f"el título con Arial no debe evaluarse en el cuerpo; su alcance es otro: {regla.found}"
    )


def test_un_titulo_no_se_exime_si_la_regla_lo_selecciona():
    """El analizador no ignora los headings por sí mismo: solo el XPath decide."""
    path = _docx_con_titulo_en_arial()
    reglas = {
        "namespaces": NS,
        "reglas": [
            {
                "id": "titulo_fuente",
                "tipo": "formato_efectivo",
                "descripcion": "Fuente de los títulos del cuerpo",
                "valor_esperado": "Times New Roman",
                "severidad": "error",
                "ubicacion": "Cuerpo",
                "fuente": "MANUAL.docx",
                "cita": '"Times New Roman: 12 puntos"',
                "formato_efectivo": {
                    "parte": "document",
                    "contexto": "todos",
                    "sujeto": "run",
                    "parrafo_xpath": "//w:body//w:p[w:pPr/w:pStyle[@w:val='Ttulo1']]",
                    "propiedad": "w:rFonts/@w:ascii",
                    "comparacion": "all_eq",
                    "esperado": "Times New Roman",
                },
            }
        ],
    }
    try:
        regla = _regla(path, "titulo_fuente", reglas)
    finally:
        os.unlink(path)
    assert regla is not None
    assert not regla.passed, "un Título1 con Arial no puede darse por bueno"
    assert "Arial" in regla.found, regla.found
