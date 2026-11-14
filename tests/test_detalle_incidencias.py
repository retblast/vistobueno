"""Detalle completo de los incumplimientos de una regla (AUD-03).

El bug reportado por el equipo: el backend mandaba todos los errores, pero
el frontend mostraba solo las primeras 3 líneas de cada error. El
truncamiento estaba en el backend: el detalle de una regla se armaba con
los 3 primeros valores (`vals[:3]`, `incumplen[:3]`), así que una regla que
fallaba en todas las líneas —por ejemplo la sangría— llegaba al frontend
con 3 líneas de error de las N que había.

Estos tests fijan el comportamiento nuevo:
- se listan TODOS los incumplimientos, con su posición y su página;
- si superan el tope, se dice cuántos más hay (nunca hay pérdida
  silenciosa de información);
- el motor legacy y el DSL producen exactamente el mismo texto.
"""

import os
import re
import zipfile
from pathlib import Path

import yaml
from docx_factory import compilar_docx, configuracion_base

from validator.detalle import MAX_INCUMPLIMIENTOS
from validator.engine import validate_docx

RAIZ = Path(__file__).resolve().parent.parent
DSL_YAML = RAIZ / "reglas_unt.yaml"
LEGACY_YAML = RAIZ / "unt_format_rules_schema.yaml"


def _docx_con_sangria_incorrecta(cuantos: int, salto_de_pagina: bool = False) -> str:
    """DOCX del factory con `cuantos` párrafos del cuerpo con sangría 0.

    Los párrafos se insertan justo después del heading INTRODUCCIÓN, que es
    donde arranca el rango que el motor considera "cuerpo". Con
    `salto_de_pagina` se mete un salto antes, para que los párrafos que
    incumplen queden en otra página que los que sí cumplen.
    """
    cfg = configuracion_base()
    origen = compilar_docx(cfg)
    destino = f"{origen}.mut"
    with zipfile.ZipFile(origen) as z:
        nombres = z.namelist()
        datos = {n: z.read(n) for n in nombres}
    xml = datos["word/document.xml"].decode("utf-8")
    # Los párrafos que incumplen van DESPUÉS de los que sí cumplen (así el
    # primer nodo del xpath es conforme y se puede comprobar que la
    # ubicación apunta al culpable, no al primero).
    conformes = [m.start() for m in re.finditer(r'<w:ind w:firstLine="720"/>', xml)]
    assert conformes, "no hay párrafos de cuerpo con sangría conforme"
    corte = xml.index("</w:p>", conformes[-1]) + len("</w:p>")
    salto = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>' if salto_de_pagina else ""
    extra = salto + "".join(
        f'<w:p><w:pPr><w:ind w:firstLine="0"/></w:pPr>'
        f"<w:r><w:t>Párrafo {i} con sangría incorrecta</w:t></w:r></w:p>"
        for i in range(cuantos)
    )
    xml = xml[:corte] + extra + xml[corte:]
    datos["word/document.xml"] = xml.encode("utf-8")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for n in nombres:
            z.writestr(n, datos[n])
    os.unlink(origen)
    return destino


def _regla(docx_path: str, rule_id: str, reglas: dict):
    for r in validate_docx(docx_path, reglas):
        if r.rule_id == rule_id:
            return r
    return None


def _cargar(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_una_regla_eq_que_falla_nombra_al_culpable():
    """Una comparación `eq` que falla NO puede decir "0 incumplen".

    El conteo sale de la misma comparación que produce el veredicto: una
    regla en rojo con "0 incumplen" le dice al estudiante que no hay nada
    que corregir (revisión del PR #78).
    """
    cfg = configuracion_base()
    cfg["pg"]["w"] = 12240  # Letter en vez de A4
    path = compilar_docx(cfg)
    try:
        r = _regla(path, "papel_tamano", _cargar(DSL_YAML))
        assert r is not None, "la regla papel_tamano no se evaluó"
        assert not r.passed, "el papel Letter debe fallar la regla"
        assert "0 incumplen" not in r.found, r.found
        # M2: se revisan todas las secciones, no solo la primera; el factory
        # declara dos (portada y cuerpo) y ambas quedan en Letter.
        assert "2 incumplen" in r.found, r.found
        assert "#1=" in r.found, r.found
        assert "#2=" in r.found, r.found
        assert "21.59 cm" in r.found, r.found
        assert "esperado=21.00 cm" in r.found, r.found
    finally:
        os.unlink(path)


def test_una_regla_sin_valores_no_dice_cero_incumplimientos():
    """Si no se leyó ningún valor, el detalle lo dice (no "0 incumplen")."""
    cfg = configuracion_base()
    cfg["portada"]["autores_label"]["texto"] = "Nómina: "  # sin "Autor..."
    path = compilar_docx(cfg)
    try:
        r = _regla(path, "caratula_autores_tamano", _cargar(DSL_YAML))
        assert r is not None, "la regla caratula_autores_tamano no se evaluó"
        assert not r.passed, "sin el párrafo de autores la regla debe fallar"
        assert "0 incumplen" not in r.found, r.found
        assert "sin valores que comparar" in r.found, r.found
    finally:
        os.unlink(path)


def test_detalle_lista_todos_los_incumplimientos():
    """Con 8 párrafos que incumplen la sangría, el detalle lista los 8.

    Antes el detalle se armaba con `incumplen[:3]`: el frontend recibía (y
    mostraba) solo 3 líneas de error de las 8 que había.
    """
    path = _docx_con_sangria_incorrecta(8)
    try:
        r = _regla(path, "sangria_parrafo", _cargar(DSL_YAML))
        assert r is not None, "la regla sangria_parrafo no se evaluó"
        assert not r.passed, "el documento con sangría 0 debe fallar la regla"
        assert "8 incumplen" in r.found, r.found
        posiciones = re.findall(r"#(\d+)=", r.found)
        assert len(posiciones) == 8, r.found
        assert posiciones == [str(p) for p in range(int(posiciones[0]), int(posiciones[0]) + 8)]
    finally:
        os.unlink(path)


def test_detalle_incluye_la_pagina_del_culpable():
    """Cada incumplimiento dice en qué página está (AUD-03)."""
    path = _docx_con_sangria_incorrecta(8)
    try:
        r = _regla(path, "sangria_parrafo", _cargar(DSL_YAML))
        assert r is not None
        assert "(pág." in r.found, r.found
    finally:
        os.unlink(path)


def test_detalle_avisa_cuando_supera_el_tope():
    """Si hay más incumplimientos que el tope, el detalle dice cuántos más."""
    extra = 2
    path = _docx_con_sangria_incorrecta(MAX_INCUMPLIMIENTOS + extra)
    try:
        r = _regla(path, "sangria_parrafo", _cargar(DSL_YAML))
        assert r is not None
        assert f"(+{extra} más)" in r.found, r.found
        assert len(re.findall(r"#\d+=", r.found)) == MAX_INCUMPLIMIENTOS, r.found
    finally:
        os.unlink(path)


def test_detalle_legacy_y_dsl_son_identicos():
    """Los dos motores producen el mismo texto (paridad literal)."""
    path = _docx_con_sangria_incorrecta(8)
    try:
        legacy = _regla(path, "sangria_parrafo", _cargar(LEGACY_YAML))
        dsl = _regla(path, "sangria_parrafo", _cargar(DSL_YAML))
        assert legacy is not None and dsl is not None
        assert legacy.found == dsl.found
    finally:
        os.unlink(path)


def test_ubicacion_apunta_al_primer_nodo_culpable():
    """La ubicación de la regla señala el primer nodo que incumple (AUD-03).

    Con un salto de página delante de los párrafos que incumplen, la página
    de la ubicación tiene que ser la del primer INCUMPLIMIENTO, no la del
    primer nodo que devolvió el xpath (que sí cumple).
    """
    path = _docx_con_sangria_incorrecta(8, salto_de_pagina=True)
    try:
        r = _regla(path, "sangria_parrafo", _cargar(DSL_YAML))
        assert r is not None and not r.passed
        pagina_ubicacion = re.search(r"página (\d+)", r.location or "")
        assert pagina_ubicacion, f"la ubicación no trae página: {r.location!r}"
        primer_culpable = re.search(r"#\d+=[^;]*?\(pág\. (\d+)\)", r.found)
        assert primer_culpable, r.found
        assert pagina_ubicacion.group(1) == primer_culpable.group(1), (
            f"la ubicación apunta a la página {pagina_ubicacion.group(1)} "
            f"pero el primer incumplimiento está en la {primer_culpable.group(1)}"
        )
    finally:
        os.unlink(path)


def test_detalle_de_lista_texto_lista_el_faltante():
    """Una lista de valores permitidos también dice QUÉ falta y dónde."""
    cfg = configuracion_base()
    cfg["portada"]["linea"]["texto"] = "Linea de investigacion que no esta aprobada"
    path = compilar_docx(cfg)
    try:
        r = _regla(path, "caratula_linea_investigacion", _cargar(DSL_YAML))
        assert r is not None, "la regla caratula_linea_investigacion no se evaluó"
        assert not r.passed, "una línea no aprobada debe fallar la regla"
        assert "en_lista_faltan" in r.found, r.found
        assert "linea de investigacion que no esta aprobada" in r.found, r.found
    finally:
        os.unlink(path)


def test_detalle_de_patron_texto_lista_los_textos():
    """Un patrón de texto también lista los textos que no cumplen."""
    cfg = configuracion_base()
    cfg["portada"]["univ"]["texto"] = "Universidad Nacional de Trujillo"
    path = compilar_docx(cfg)
    try:
        r = _regla(path, "caratula_universidad_negrita_mayusculas", _cargar(DSL_YAML))
        assert r is not None, "la regla caratula_universidad_negrita_mayusculas no se evaluó"
        assert not r.passed, "un nombre con minúsculas debe fallar la regla"
        assert "incumplen" in r.found, r.found
        assert "Universidad Nacional de Trujillo" in r.found, r.found
    finally:
        os.unlink(path)
