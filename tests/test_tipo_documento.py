"""Tests del contexto entre reglas: `expone`, `aplicar_si` y evaluación en
dos fases (Semana 6, Paso 1 del `docs/PLAN_TIPO_DOCUMENTO.md`).

Cubre el andamiaje, no la detección de tipo: aquí no hay todavía analizador
`deteccion_tipo`, solo la maquinaria que permite que una regla publique una
clave en el contexto y que otra se condicione a ella.

Incluye una guarda de regresión: con el YAML real (`reglas_unt.yaml`) ninguna
regla debe resultar no aplicable, y el orden del reporte debe seguir siendo el
del YAML.

Uso:
    pytest tests/test_tipo_documento.py -v
"""

import sys
import tempfile
import zipfile
from pathlib import Path

import pytest
import yaml

from validator.compilador import CompilerDSL
from validator.dsl_check import DSLValidationError, linter
from validator.engine import build_report, load_rules, validate_docx

sys.path.insert(0, str(Path(__file__).parent))
from test_dsl import WNS, _make_docx, _para  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUTA_REGLAS = Path(__file__).resolve().parents[1] / "reglas_unt.yaml"

# Las 3 reglas de estructura, que son las unicas condicionadas al tipo.
ESTRUCTURA = {
    "estructura_tinv_cuantitativo",
    "estructura_tinv_cualitativo",
    "estructura_tinv_revision_literatura",
}

# Reglas condicionadas al tipo de documento (handover issue #5): además de
# los 3 esquemas de estructura, los mínimos de referencias/anexos por tipo y
# el texto de carátula del Proyecto. En un documento de otro tipo NO se
# evalúan (`aplicable=False`): reportarlas como fallidas sería exigirle al
# estudiante anexos de una tesis cualitativa en una cuantitativa.
TIPO_ESPECIFICAS = ESTRUCTURA | {
    "referencias_minimo_cuantitativo",
    "referencias_minimo_cualitativo",
    "referencias_minimo_revision",
    "anexos_minimos_cuantitativo",
    "anexos_minimos_cualitativo",
    "proyecto_caratula_texto",
}


def _regla_simple(rule_id, severidad="error", **extra):
    """Regla mínima con un solo analizador, la base para las pruebas de
    contexto."""
    regla = {
        "id": rule_id,
        "tipo": "atributo_xml",
        "severidad": severidad,
        "descripcion": f"descripcion de {rule_id}",
        "valor_esperado": "11906",
        "atributo_xml": {
            "parte": "document",
            "xpath": "//w:sectPr[1]/w:pgSz",
            "atributo": "@w:w",
            "comparacion": "eq",
            "esperado": "11906",
        },
    }
    regla.update(extra)
    return regla


def _detector(rule_id="detector", clave="tipo"):
    """Regla que publica una clave en el contexto.

    Se apoya en `AnalizadorXML`, que sí deja un valor legible por máquina
    (`Analizador.valor`): el ancho de página del DOCX de prueba. Así el
    andamiaje se ejercita de punta a punta con analizadores que ya existen,
    sin necesitar un analizador `deteccion_tipo` que aún no se ha escrito.
    """
    return _regla_simple(rule_id, expone=clave)


def _datos(*reglas):
    return {"namespaces": {"w": WNS}, "reglas": list(reglas)}


def _ids(resultados):
    return [r.rule_id for r in resultados]


# ---------------------------------------------------------------------------
# Linter: validacion de `expone` y `aplicar_si`
# ---------------------------------------------------------------------------


class TestAplicarSiConLista:
    """Un valor lista en `aplicar_si` significa "cualquiera de estos".

    Es lo que permite que una regla diga qué hace con un tipo que no se pudo
    determinar, en vez de quedar en silencio. Para las estructuras TINV:
    "tipo desconocido -> validar contra todos los esquemas".
    """

    @staticmethod
    def _regla_estructura(condicion):
        return _regla_simple("estructura", aplicar_si=condicion)

    @staticmethod
    def _datos(condicion):
        return _datos(_detector(), _regla_simple("estructura", aplicar_si=condicion))

    def test_lista_valida_no_reporta_hallazgos(self):
        assert linter(self._datos({"tipo": ["cuantitativo", "sin_determinar"]})) == []

    def test_lista_vacia_se_rechaza(self):
        """Una lista vacía no casaría con nada: dejaría la regla muerta."""
        assert linter(self._datos({"tipo": []}))

    def test_lista_con_no_escalares_se_rechaza(self):
        assert linter(self._datos({"tipo": [{"tipo": "cuantitativo"}]}))

    def test_valor_none_se_rechaza(self):
        assert linter(self._datos({"tipo": None}))

    @staticmethod
    def _compilada(condicion):
        return next(
            r
            for r in CompilerDSL().compilar(TestAplicarSiConLista._datos(condicion))
            if r.rule["id"] == "estructura"
        )

    def test_escalar_sigue_siendo_exigencia_exacta(self):
        regla = self._compilada({"tipo": "cuantitativo"})
        assert regla.aplica_en({"tipo": "cuantitativo"}) is True
        assert regla.aplica_en({"tipo": "cualitativo"}) is False
        assert regla.aplica_en({"tipo": "sin_determinar"}) is False

    def test_la_lista_casa_con_cualquiera_de_sus_valores(self):
        regla = self._compilada({"tipo": ["cuantitativo", "sin_determinar", "contradictorio"]})
        for valor in ("cuantitativo", "sin_determinar", "contradictorio"):
            assert regla.aplica_en({"tipo": valor}) is True, valor
        assert regla.aplica_en({"tipo": "cualitativo"}) is False

    def test_clave_ausente_no_hace_aplicar_la_regla(self):
        regla = self._compilada({"tipo": ["cuantitativo", "sin_determinar"]})
        assert regla.aplica_en({}) is False
        assert regla.aplica_en({"otro": "cuantitativo"}) is False

    def test_cada_estructura_solo_recibe_su_propio_tipo(self):
        """Invariante del paso 6: una estructura se valida solo cuando se sabe
        que el documento es de su tipo.

        Antes (paso 4) los tipos desconocidos activaban las tres estructuras, y
        el estudiante veía dos errores de secciones que no podía corregir sin
        adivinar el tipo. Ahora los estados sin determinar / contradictorio son
        un error centinela propio, y las estructuras quedan fuera."""
        reglas = load_rules(str(RUTA_REGLAS))["reglas"]
        for r in reglas:
            if r["id"] in ESTRUCTURA:
                valor = r["aplicar_si"]["tipo_documento"]
                assert isinstance(valor, str), r["id"]
                assert valor in {
                    "tinv_cuantitativo",
                    "tinv_cualitativo",
                    "tinv_revision_literatura",
                }, r["id"]


class TestLinterContexto:
    def test_aplicar_si_valido_no_reporta_hallazgos(self):
        datos = _datos(
            _regla_simple("detector", expone="tipo"),
            _regla_simple("estructura", aplicar_si={"tipo": "cuantitativo"}),
        )
        assert linter(datos) == []

    def test_aplicar_si_a_clave_inexistente_es_error(self):
        """Una condicion que nadie puede satisfacer dejaria la regla siempre
        inactiva: es un fallo silencioso, tiene que ser error de carga."""
        datos = _datos(_regla_simple("estructura", aplicar_si={"tipo": "cuantitativo"}))
        hallazgos = linter(datos)
        assert len(hallazgos) == 1
        assert "aplicar_si" in hallazgos[0]
        assert "no la expone ninguna regla" in hallazgos[0]

    @pytest.mark.parametrize("invalido", [{}, [], "cuantitativo", None, ""])
    def test_aplicar_si_no_es_mapa_no_vacio(self, invalido):
        datos = _datos(
            _regla_simple("detector", expone="tipo"),
            _regla_simple("estructura"),
        )
        datos["reglas"][1]["aplicar_si"] = invalido
        assert any("aplicar_si" in h for h in linter(datos))

    def test_expone_duplicado_es_error(self):
        datos = _datos(
            _regla_simple("detector_a", expone="tipo"),
            _regla_simple("detector_b", expone="tipo"),
        )
        hallazgos = linter(datos)
        assert any("ya la expone" in h for h in hallazgos)

    def test_expone_y_aplicar_si_en_la_misma_regla_es_error(self):
        datos = _datos(
            _regla_simple("detector", expone="tipo"),
            _regla_simple("weird", expone="otro", aplicar_si={"tipo": "x"}),
        )
        assert any("expone y aplicar_si" in h for h in linter(datos))

    def test_expone_sin_analizador_es_error(self):
        """Sin seccion de analizador la regla se descarta al compilar, asi que
        nunca publicaria su clave y dejaria huerfana cualquier condicion."""
        datos = _datos(
            {"id": "fantasma", "expone": "tipo", "descripcion": "sin analizador"},
            _regla_simple("estructura", aplicar_si={"tipo": "cuantitativo"}),
        )
        assert any("nunca publica su clave" in h for h in linter(datos))

    def test_expone_no_textual_es_error(self):
        datos = _datos(_regla_simple("detector", expone=42))
        assert any("expone: debe ser un texto" in h for h in linter(datos))

    def test_linter_o_alzar_falla_al_cargar(self):
        datos = _datos(_regla_simple("estructura", aplicar_si={"tipo": "cuantitativo"}))
        with pytest.raises(DSLValidationError, match="aplicar_si"):
            CompilerDSL().compilar(datos)

    def test_condicion_puede_ir_antes_que_el_detector(self):
        """El orden en el YAML es irrelevante: la evaluación es en dos fases,
        así que una regla condicionada puede declararse antes que la que
        produce su clave."""
        datos = _datos(
            _regla_simple("estructura", aplicar_si={"tipo": "cuantitativo"}),
            _detector(),
        )
        assert linter(datos) == []

    def test_yaml_real_sigue_pasando_el_linter(self):
        assert linter(load_rules(str(RUTA_REGLAS))) == []


# ---------------------------------------------------------------------------
# Evaluacion en dos fases
# ---------------------------------------------------------------------------


class TestDosFases:
    """El detector de prueba publica '11906' (ancho de página A4), que es el
    valor contra el que se condicionan las reglas."""

    ANCHO = "11906"

    def test_aplicar_si_cumplido_se_evalua(self):
        datos = _datos(_detector(), _regla_simple("estructura", aplicar_si={"tipo": self.ANCHO}))
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        por_id = {r.rule_id: r for r in res}
        assert por_id["estructura"].aplicable is True
        assert por_id["estructura"].passed is True

    def test_aplicar_si_no_cumplido_queda_no_aplicable(self):
        datos = _datos(_detector(), _regla_simple("estructura", aplicar_si={"tipo": "OTRO"}))
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        por_id = {r.rule_id: r for r in res}
        assert por_id["estructura"].aplicable is False
        assert "no aplica" in por_id["estructura"].found

    def test_clave_ausente_del_contexto_no_aplica(self):
        """Ausencia de clave es 'valor desconocido', no 'vale cualquier cosa'.

        Se prueba sobre `aplica_en` directamente: con el linter en pie, toda
        clave usada en `aplicar_si` está expuesta por alguna regla, así que
        el caso es defensivo y no se puede llegar por el motor.
        """
        from validator.compilador import ReglaCompilada

        regla = ReglaCompilada(rule={"id": "x"}, aplicar_si={"tipo": "A4"})
        assert regla.aplica_en({"tipo": "A4"}) is True
        assert regla.aplica_en({"otro": "A4"}) is False
        assert regla.aplica_en({}) is False
        assert ReglaCompilada(rule={"id": "x"}, aplicar_si=None).aplica_en({}) is True

    def test_condiciones_conjuntas(self):
        """Varias claves en `aplicar_si` deben cumplirse todas."""
        datos = _datos(
            _detector("d1", clave="tipo"),
            _detector("d2", clave="programa"),
            _regla_simple("estructura", aplicar_si={"tipo": self.ANCHO, "programa": "OTRO"}),
        )
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert {r.rule_id: r for r in res}["estructura"].aplicable is False

    def test_regla_incondicional_siempre_aplica(self):
        datos = _datos(_regla_simple("sencilla"))
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert res[0].aplicable is True

    def test_no_aplicable_no_bloquea_el_semaforo(self):
        """Una regla inactiva no ha fallado, así que no puede poner el
        semáforo en rojo aunque su severidad sea `error`."""
        datos = _datos(_detector(), _regla_simple("estructura", aplicar_si={"tipo": "OTRO"}))
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert build_report(res)["semaforo"] == "verde"

    def test_el_resumen_cuenta_evaluadas_y_omitidas(self):
        """El resumen tiene que distinguir lo que se miró de lo que no.

        Una regla no aplicable no se evaluó: listarla como cumplida haría
        creer al estudiante que pasó. Se cuenta aparte."""
        datos = _datos(
            _detector(),
            _regla_simple("se_evalua"),
            _regla_simple("no_se_evalua", aplicar_si={"tipo": "OTRO"}),
        )
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        resumen = build_report(res)["resumen"]
        assert resumen["total"] == 3
        assert resumen["total_evaluadas"] == 2
        assert resumen["reglas_no_aplicables"] == 1

    def test_una_regla_no_aplicable_no_aparece_en_resultados(self):
        datos = _datos(
            _detector(),
            _regla_simple("se_evalua"),
            _regla_simple("no_se_evalua", aplicar_si={"tipo": "OTRO"}),
        )
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        ids = [r["rule_id"] for r in build_report(res)["resultados"]]
        assert "no_se_evalua" not in ids
        assert "se_evalua" in ids

    def test_el_filtro_de_severidad_no_oculta_los_conteos(self):
        """Filtrar la vista no puede cambiar lo que se evaluó: los conteos
        describen el documento, no lo que se pidió mostrar."""
        datos = _datos(
            _detector(),
            _regla_simple("se_evalua"),
            _regla_simple("no_se_evalua", aplicar_si={"tipo": "OTRO"}),
        )
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        resumen = build_report(res, ["warning"])["resumen"]
        assert resumen["total_evaluadas"] == 2
        assert resumen["reglas_no_aplicables"] == 1

    def test_el_documento_bueno_cuenta_42_de_48(self):
        """Guarda sobre el YAML real: el documento bueno es un plan
        cuantitativo, así que no se evalúan las 6 reglas de otros tipos (los
        2 esquemas alternativos, los mínimos de referencias/anexos de
        cualitativo y revisión, y la carátula del Proyecto)."""
        from docx_factory import compilar_docx, configuracion_base  # noqa: E402

        path = compilar_docx(configuracion_base())
        try:
            res = validate_docx(path, load_rules("reglas_unt.yaml"))
        finally:
            Path(path).unlink(missing_ok=True)
        rep = build_report(res)
        assert rep["resumen"]["total_evaluadas"] == 42
        assert rep["resumen"]["reglas_no_aplicables"] == 6
        assert len(rep["resultados"]) == 42
        assert rep["semaforo"] == "verde"

    def test_orden_del_yaml_se_conserva(self):
        """Las fases no deben reordenar el reporte: el orden de salida es el
        del YAML, no el de ejecución. Aquí las reglas condicionadas están
        ANTES que el detector que produce su clave, que es justo el caso donde
        un `return` por fase las desordenaría."""
        datos = _datos(
            _regla_simple("condicional_1", aplicar_si={"tipo": "X"}),
            _detector(),
            _regla_simple("incondicional"),
            _regla_simple("condicional_2", aplicar_si={"tipo": "Y"}),
        )
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert _ids(res) == ["condicional_1", "detector", "incondicional", "condicional_2"]

    def test_todas_las_reglas_conservan_su_resultado(self):
        """Ninguna regla se pierde: las no aplicables también se reportan,
        con `aplicable=False`, para que el resumen pueda contarlas."""
        datos = _datos(_detector(), _regla_simple("estructura", aplicar_si={"tipo": "OTRO"}))
        path = _make_docx(headings=["RESULTADOS"])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert len(res) == 2


# ---------------------------------------------------------------------------
# Guardas de regresion sobre el YAML real
# ---------------------------------------------------------------------------


class TestSinCambioDeComportamiento:
    """Con el YAML real, la regla nueva informa y las 3 estructuras se
    condicionan a ella sin romper nada más.

    Lo que este bloque fijaba en el paso 3 (48 reglas, todas aplicables) lo
    invalida el paso 4 a propósito: ahora 2 reglas son no aplicables en un
    documento cuantitativo. Lo que se conserva es la garantía de que el
    semáforo solo lo mueven las reglas que de verdad aplican.
    """

    @staticmethod
    def _ruta_plantilla():
        return (
            Path(__file__).resolve().parents[1]
            / "recursos"
            / "EDUCACION INICIAL-PLANTILLA INVESTIGACIÓN CUANTITATIVA.docx"
        )

    def test_solo_las_reglas_tipo_especificas_se_condicionan(self):
        reglas = load_rules(str(RUTA_REGLAS))["reglas"]
        condicionadas = {r["id"] for r in reglas if r.get("aplicar_si")}
        assert condicionadas == TIPO_ESPECIFICAS

    def test_ninguna_regla_condicionada_tambien_expone(self):
        """Condicionarse a un valor que uno mismo produce no tiene sentido."""
        reglas = load_rules(str(RUTA_REGLAS))["reglas"]
        for r in reglas:
            if r.get("aplicar_si"):
                assert "expone" not in r and not any(s in r for s in ("deteccion_tipo",)), r["id"]

    def test_doc_bueno_solo_omite_las_reglas_de_otros_tipos(self):
        from docx_factory import compilar_docx, configuracion_base

        path = compilar_docx(configuracion_base())
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)
        assert len(res) == 48
        assert {r.rule_id for r in res if not r.aplicable} == TIPO_ESPECIFICAS - {
            "estructura_tinv_cuantitativo",
            "referencias_minimo_cuantitativo",
            "anexos_minimos_cuantitativo",
        }

    def test_plantilla_oficial_no_reporta_esquemas_imposibles(self):
        """Los errores imposibles de corregir desaparecieron: la plantilla es
        cuantitativa, así que los esquemas cualitativo y de revisión, sus
        mínimos y la carátula del Proyecto no le aplican. Quedan 2 errores
        reales (autores sin mayúsculas y palabras clave).

        `recursos/` está en `.gitignore`, así que en el build de Nix la
        plantilla no existe y el test se omite.
        """
        base = self._ruta_plantilla()
        if not base.exists():
            pytest.skip("las plantillas de recursos/ no están disponibles en este entorno")
        res = validate_docx(str(base), load_rules(str(RUTA_REGLAS)))
        assert len(res) == 48
        fallidos = {r.rule_id for r in res if not r.passed and r.severity.value == "error"}
        assert not fallidos & TIPO_ESPECIFICAS
        assert len(fallidos) == 2
        assert build_report(res)["semaforo"] == "rojo"


# ---------------------------------------------------------------------------
# El YAML de reglas pendientes (Fase B) debe cargar y lintear
# ---------------------------------------------------------------------------


# Que escribe el autor al marcar su casilla del Anexo 10, por tipo. Es el
# segundo vocabulario, el que el formulario imprime de verdad.
_ETIQUETA_PENDIENTE = {
    "proyecto_cuantitativo": "PROYECTO DE INVESTIGACIÓN CUANTITATIVO",
    "proyecto_cualitativo": "PROYECTO DE INVESTIGACIÓN CUALITATIVO",
    "informe_cuantitativo": "INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVA",
    "informe_cualitativo": "INFORME DE PROYECTO DE INVESTIGACIÓN CUALITATIVA",
    "tsp": "TRABAJO DE SUFICIENCIA PROFESIONAL",
}


class TestYamlPendienteOpcional:
    """`reglas_unt_pendientes.yaml` solo existe a partir del paso 8. Si ya
    esta, tiene que cargar y pasar el linter: implementadas pero no probadas
    contra documentos reales."""

    RUTA = Path(__file__).resolve().parents[1] / "reglas_unt_pendientes.yaml"

    def test_carga_y_lintea(self):
        if not self.RUTA.exists():
            pytest.skip("reglas_unt_pendientes.yaml todavia no existe (se crea en el paso 8)")
        datos = yaml.safe_load(self.RUTA.read_text(encoding="utf-8"))
        assert linter(datos) == []
        assert datos["reglas"], "el archivo debe declarar al menos una regla"

    TIPOS_PENDIENTES = {
        "proyecto_cuantitativo",
        "proyecto_cualitativo",
        "informe_cuantitativo",
        "informe_cualitativo",
        "tsp",
    }

    def test_cada_estructura_pendiente_es_exclusiva_de_su_tipo(self):
        """Cada `aplicar_si` tiene que aceptar SOLO su tipo exacto.

        Es lo que impide que a un proyecto cuantitativo le exijan la
        estructura del cualitativo. Los dos proyectos comparten casi todo el
        esqueleto, asi que un `aplicar_si` laxo pasaria desapercibido.
        """
        datos = yaml.safe_load(self.RUTA.read_text(encoding="utf-8"))
        seen: dict[str, str] = {}
        for regla in datos["reglas"]:
            cond = regla.get("aplicar_si")
            if not cond:
                continue
            assert set(cond) == {"tipo_documento"}, regla["id"]
            (tipo,) = cond.values()
            assert tipo not in seen, f"{tipo} lo piden dos reglas"
            seen[tipo] = regla["id"]
        assert set(seen) == self.TIPOS_PENDIENTES, sorted(seen)

    def test_el_archivo_pendiente_expone_tipo_documento(self):
        """Las condiciones apuntan a `tipo_documento`, asi que el archivo tiene
        que traer su propia regla discriminadora.

        No es redundancia gratuita: el linter resuelve `aplicar_si` contra las
        claves expuestas del MISMO archivo, no contra las de `reglas_unt.yaml`.
        Sin la copia, estas 5 reglas no lintearian.
        """
        datos = yaml.safe_load(self.RUTA.read_text(encoding="utf-8"))
        expuestas = [
            r["deteccion_tipo"]["expone"] for r in datos["reglas"] if "deteccion_tipo" in r
        ]
        assert expuestas == ["tipo_documento"]

    @pytest.mark.parametrize(
        "tipo",
        sorted(
            {
                "proyecto_cuantitativo",
                "proyecto_cualitativo",
                "informe_cuantitativo",
                "informe_cualitativo",
                "tsp",
            }
        ),
    )
    def test_cada_tipo_aplica_solo_estructura_suya(self, tipo):
        """Segunda verificacion del paso 8: al cargar el archivo aparte, un
        documento solo deja aplicar la estructura que le corresponde.

        No se comprueba que el DFA reconozca bien las secciones (eso necesita
        plantillas, que no hay). Se comprueba el `aplicar_si`: que los otros 4
        esquemas queden marcados como no aplicables. Si un esquema se colara
        sin condicionar, un proyecto cuantitario recibiria tambien las
        exigencias del cualitativo, que comparte casi todo el esqueleto.
        """
        reglas = load_rules(str(self.RUTA))
        path = _make_docx(
            headings=["INTRODUCCION", "MARCO TEORICO", "CONCLUSIONES"],
            cover=f"\u2612 {_ETIQUETA_PENDIENTE[tipo]}",
        )
        try:
            resultados = validate_docx(path, reglas)
        finally:
            Path(path).unlink(missing_ok=True)

        estructuras = {
            r.rule_id: r.aplicable for r in resultados if r.rule_id.startswith("estructura_")
        }
        assert set(estructuras) == {f"estructura_{t}" for t in _ETIQUETA_PENDIENTE}, estructuras
        for rule_id, aplicable in estructuras.items():
            esperado = rule_id == f"estructura_{tipo}"
            assert aplicable is esperado, (
                f"{tipo}: {rule_id} aplicable={aplicable}, se esperaba {esperado}"
            )

    def test_las_estructuras_pendientes_no_entran_en_produccion(self):
        """El archivo aparte existe justo para no medir un comportamiento que
        nadie verifico: no hay plantillas oficiales de estos 5 tipos. Si alguna
        se colara en `reglas_unt.yaml`, la suite pasaria a medirla."""
        produccion = (self.RUTA.parent / "reglas_unt.yaml").read_text(encoding="utf-8")
        for tipo in self.TIPOS_PENDIENTES:
            assert f"- id: estructura_{tipo}\n" not in produccion, tipo


# ---------------------------------------------------------------------------
# Paso 2: DeteccionTipo
# ---------------------------------------------------------------------------

from validator.analizadores import (  # noqa: E402
    NIVEL_DECLARADO,
    NIVEL_INFERIDO,
    NIVEL_NO_DETERMINADO,
    TIPO_CONTRADICTORIO,
    TIPO_SIN_DETERMINAR,
    DeteccionTipo,
)
from validator.extractor import extract  # noqa: E402

# Firmas tal como las fija docs/diseno/15_tipo_documento_grupos.md, en el
# orden de especificidad de la decisión 2 (el informe gana al proyecto).
FIRMAS = [
    {
        "tipo": "tsp",
        "evidencia": [
            "SECUENCIA DIDÁCTICA",
            "SUSTENTO PSICOPEDAGÓGICO",
            "SUSTENTO TEÓRICO CIENTÍFICO",
        ],
        "minimo": 2,
    },
    {
        "tipo": "informe_cualitativo",
        "evidencia": [
            "SITUACIÓN PROBLEMATIZADA",
            "PARTICIPANTES",
            "INSTRUMENTOS USADOS EN LA RECOLECCIÓN",
        ],
        "minimo": 2,
    },
    {
        "tipo": "informe_cuantitativo",
        "evidencia": [
            "SITUACIÓN PROBLEMATIZADA",
            "DISEÑO DE CONTRASTACIÓN",
            "OPERACIONALIZACIÓN DE LAS VARIABLES",
        ],
        "minimo": 2,
    },
    {
        "tipo": "proyecto_cuantitativo",
        "evidencia": ["PLAN DE INVESTIGACIÓN", "RECURSOS Y MATERIALES", "LÍNEA DE INVESTIGACIÓN"],
        "minimo": 2,
    },
    {
        "tipo": "proyecto_cualitativo",
        "evidencia": ["SELECCIÓN DE PARTICIPANTES", "ESCENARIO", "UNIDAD DE ANÁLISIS"],
        "minimo": 2,
    },
    {
        "tipo": "tinv_revision_literatura",
        "evidencia": ["ESTADO DEL ARTE", "TÉCNICAS DE PROCESAMIENTO DE DATOS"],
        "minimo": 1,
    },
    {
        "tipo": "tinv_cualitativo",
        "evidencia": ["DEFINICIÓN DE TÉRMINOS", "CATEGORIZACIÓN"],
        "minimo": 1,
    },
    {
        "tipo": "tinv_cuantitativo",
        "evidencia": ["VARIABLE", "POBLACIÓN Y MUESTRA", "INSTRUMENTO"],
        "minimo": 1,
    },
]

# Etiquetas del Anexo 10. Cada tipo tiene dos vocabularios distintos: el del
# titulo que se opto y el que imprime el formulario. No son intercambiables,
# asi que se listan los dos (espejo de reglas_unt.yaml).
ETIQUETAS = {
    "tsp": [
        "TRABAJO DE SUFICIENCIA PROFESIONAL",
        "TRABAJO DE SERVICIO",
        "SERVICIO SOCIAL",
    ],
    "informe_cualitativo": ["INFORME DE PROYECTO DE INVESTIGACIÓN CUALITATIVO"],
    "informe_cuantitativo": ["INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO"],
    "proyecto_cuantitativo": ["PROYECTO DE INVESTIGACIÓN CUANTITATIVO"],
    "proyecto_cualitativo": ["PROYECTO DE INVESTIGACIÓN CUALITATIVO"],
    "tinv_revision_literatura": [
        "TESIS PARA OBTENER EL GRADO DE BACHILLER EN INVESTIGACIÓN",
        "TRABAJO DE INVESTIGACIÓN DE REVISIÓN DE LA LITERATURA",
    ],
    "tinv_cualitativo": [
        "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUALITATIVA",
        "TRABAJO DE INVESTIGACIÓN CUALITATIVO",
    ],
    "tinv_cuantitativo": [
        "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUANTITATIVA",
        "TRABAJO DE INVESTIGACIÓN CUANTITATIVO",
    ],
}


def _cfg_deteccion(declaracion=None, firmas=None):
    cfg = {
        "expone": "tipo_documento",
        "firmas": FIRMAS if firmas is None else firmas,
        "minimo_global": 1,
    }
    if declaracion is not None:
        cfg["declaracion"] = declaracion
    return cfg


def _docx_de_parrafos(parrafos_xml: list[str], xmlns: str = "") -> str:
    """DOCX mínimo a partir de XML de párrafos crudo (para poder meter
    `w:sym`, que un builder de texto plano no sabe escribir).

    `xmlns` permite declarar prefijos extra (p. ej. `xmlns:w14=...` para los
    content-control del Anexo 10).
    """
    from test_dsl import CONTENT_TYPES, RELS

    body = "".join(parrafos_xml)
    doc = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WNS}" {xmlns}><w:body>{body}'
        f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
        f"</w:body></w:document>"
    )
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
    return path


def _detectar(parrafos_xml, declaracion=None, firmas=None, xmlns=""):
    """Ejecuta el analizador y devuelve (ok, nivel, valor, evidencia, detalle)."""
    path = _docx_de_parrafos(parrafos_xml, xmlns=xmlns)
    try:
        analizador = DeteccionTipo(_cfg_deteccion(declaracion, firmas))
        ok, detalle = analizador.analizar(extract(path))
        return ok, analizador.nivel, analizador.valor, analizador.evidencia, detalle
    finally:
        Path(path).unlink(missing_ok=True)


def _t(texto, estilo="Ttulo1"):
    return _para(texto, estilo)


def _con_sym(char, texto=""):
    """Casilla Wingdings. Word la escribe como un `w:sym` en el MISMO párrafo
    que su etiqueta, que es como se lee un formulario."""
    return (
        f'<w:p><w:r><w:sym w:font="Wingdings" w:char="{char}"/></w:r>'
        f'<w:r><w:t xml:space="preserve"> {texto}</w:t></w:r></w:p>'
    )


def _con_casilla(texto, marcada=True):
    return (
        f'<w:p><w:r><w:t xml:space="preserve">☒ {texto}</w:t></w:r></w:p>'
        if marcada
        else (f'<w:p><w:r><w:t xml:space="preserve">☐ {texto}</w:t></w:r></w:p>')
    )


class TestDeteccionNivelInferido:
    """Nivel 2: firmas estructurales. Un conjunto mínimo por tipo."""

    @pytest.mark.parametrize(
        ("tipo_esperado", "titulos"),
        [
            ("tsp", ["SECUENCIA DIDÁCTICA", "SUSTENTO PSICOPEDAGÓGICO"]),
            ("informe_cualitativo", ["SITUACIÓN PROBLEMATIZADA", "PARTICIPANTES"]),
            ("informe_cuantitativo", ["SITUACIÓN PROBLEMATIZADA", "DISEÑO DE CONTRASTACIÓN"]),
            ("proyecto_cuantitativo", ["PLAN DE INVESTIGACIÓN", "RECURSOS Y MATERIALES"]),
            ("proyecto_cualitativo", ["SELECCIÓN DE PARTICIPANTES", "UNIDAD DE ANÁLISIS"]),
            ("tinv_revision_literatura", ["ESTADO DEL ARTE"]),
            ("tinv_cualitativo", ["DEFINICIÓN DE TÉRMINOS"]),
            ("tinv_cuantitativo", ["POBLACIÓN Y MUESTRA"]),
        ],
    )
    def test_detecta_los_ocho_tipos(self, tipo_esperado, titulos):
        ok, nivel, valor, evidencia, detalle = _detectar([_t(t) for t in titulos])
        assert valor == tipo_esperado, detalle
        assert ok is True
        assert nivel == NIVEL_INFERIDO
        assert evidencia, "el nivel inferido debe decir qué firmas encontró"
        assert f"inferido={tipo_esperado}" in detalle

    def test_todos_los_tipos_del_diseno_son_detectables(self):
        """Los 8 identificadores canónicos del diseño tienen firma."""
        assert {f["tipo"] for f in FIRMAS} == set(ETIQUETAS)

    def test_informe_gana_al_proyecto(self):
        """Decisión 2: el informe es la versión revisada del proyecto, así que
        sus firmas son más específicas y se evalúan antes."""
        titulos = ["SITUACIÓN PROBLEMATIZADA", "DISEÑO DE CONTRASTACIÓN", "PLAN DE INVESTIGACIÓN"]
        _, _nivel, valor, _ev, _ = _detectar([_t(t) for t in titulos])
        assert valor == "informe_cuantitativo"

    def test_tsp_gana_a_informe(self):
        titulos = ["SECUENCIA DIDÁCTICA", "SUSTENTO PSICOPEDAGÓGICO", "SITUACIÓN PROBLEMATIZADA"]
        _, _nivel, valor, _ev, _ = _detectar([_t(t) for t in titulos])
        assert valor == "tsp"

    def test_normaliza_acentos_y_sangria(self):
        """Los títulos reales vienen con tildes, numeración y sangría: la
        comparación no debe depender de eso."""
        _, _nivel, valor, _ev, _ = _detectar(
            [_t("   2.1  Definición de Términos   ", "Ttulo2")], None
        )
        assert valor == "tinv_cualitativo"

    def test_firma_por_subcadena(self):
        """'VARIABLE' debe casar con 'VARIABLE(S) Y OPERACIONALIZACIÓN'."""
        _, _nivel, valor, _ev, _ = _detectar([_t("VARIABLE(S) Y OPERACIONALIZACIÓN")])
        assert valor == "tinv_cuantitativo"

    def test_minimo_no_alcanzado_no_dispara(self):
        """Una sola firma de un tipo que exige 2 no basta."""
        ok, _nivel, valor, _ev, detalle = _detectar([_t("PLAN DE INVESTIGACIÓN")])
        assert valor == TIPO_SIN_DETERMINAR
        assert ok is False
        assert "sin_determinado" in detalle

    def test_titulo_desconocido_queda_sin_determinar(self):
        ok, nivel, valor, evidencia, detalle = _detectar([_t("RESUMEN"), _t("INTRODUCCIÓN")])
        assert valor == TIPO_SIN_DETERMINAR
        assert nivel == NIVEL_NO_DETERMINADO
        assert evidencia == []
        assert ok is False
        assert "sin_determinado" in detalle

    def test_documento_vacio_queda_sin_determinar(self):
        ok, _nivel, valor, _ev, _ = _detectar([])
        assert valor == TIPO_SIN_DETERMINAR
        assert ok is False


class TestEtiquetaMasLargaGana:
    """El cotejo de etiquetas es por subcadena y unas contienen a otras.

    "INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO" contiene "PROYECTO DE
    INVESTIGACIÓN CUANTITATIVO", así que en un Anexo 10 marcado como informe
    las dos etiquetas casan. Gana la más larga, de modo que reordenar el
    diccionario del YAML no cambia el tipo detectado.
    """

    def _detectar(self, texto, etiquetas):
        # Solo el párrafo del Anexo 10: ninguna firma estructural alcanza su
        # mínimo, así que no hay inferencia y no se confounding con
        # contradicción. Lo que se prueba aquí es la lectura del nivel 1.
        return _detectar([_con_casilla(texto)], {"anexo": "Anexo 10", "etiquetas": etiquetas})

    def test_el_informe_gana_a_la_etiqueta_que_contiene(self):
        _, _, valor, evidencia, _ = self._detectar(
            "INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO", ETIQUETAS
        )
        assert valor == "informe_cuantitativo"
        assert evidencia == ["INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO"]

    def test_el_resultado_no_depende_del_orden_del_diccionario(self):
        """Regresión del fallo silencioso: antes ganaba la clave que estuviera
        antes en el YAML, y el YAML es texto que se reordona sin avisar."""
        texto = "INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO"
        for nombre, etiquetas in (
            ("informe antes", dict(ETIQUETAS)),
            ("proyecto antes", {k: v for k, v in reversed(list(ETIQUETAS.items()))}),
        ):
            _, _, valor, _, _ = self._detectar(texto, etiquetas)
            assert valor == "informe_cuantitativo", nombre

    def test_sin_la_palabra_informe_se_lee_como_proyecto(self):
        """La etiqueta corta sigue sirviendo cuando es la única que casa."""
        _, _, valor, evidencia, _ = self._detectar(
            "PROYECTO DE INVESTIGACIÓN CUANTITATIVO", ETIQUETAS
        )
        assert valor == "proyecto_cuantitativo"
        assert evidencia == ["PROYECTO DE INVESTIGACIÓN CUANTITATIVO"]

    def test_el_orden_invertido_no_altera_los_demas_tipos(self):
        _, _, valor, _, _ = self._detectar(
            "INFORME DE PROYECTO DE INVESTIGACIÓN CUALITATIVO", ETIQUETAS
        )
        assert valor == "informe_cualitativo"
        _, _, valor, _, _ = self._detectar(
            "INFORME DE PROYECTO DE INVESTIGACIÓN CUALITATIVO",
            {k: v for k, v in reversed(list(ETIQUETAS.items()))},
        )
        assert valor == "informe_cualitativo"

    def test_una_etiqueta_suelta_no_gana_por_orden(self):
        """Ninguna etiqueta del Anexo 10 es subcadena de otra de un tipo
        distinto salvo el par informe/proyecto. Este test falla si alguien
        añade una etiqueta anidada sin querer, que es la forma de rearmar el
        fallo que se acaba de corregir."""
        import unicodedata

        def norm(t):
            t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()
            return " ".join(t.split())

        anidadas = []
        for tipo, alias in ETIQUETAS.items():
            for a in alias:
                for otro_tipo, otro_alias in ETIQUETAS.items():
                    if otro_tipo == tipo:
                        continue
                    for b in otro_alias:
                        if norm(a) != norm(b) and norm(a) in norm(b):
                            anidadas.append((tipo, a, otro_tipo, b))
        # Solo se admite el par informe/proyecto, que es intencionado.
        assert {tuple(sorted((a, d))) for _, a, _, d in anidadas} == {
            (
                "INFORME DE PROYECTO DE INVESTIGACIÓN CUALITATIVO",
                "PROYECTO DE INVESTIGACIÓN CUALITATIVO",
            ),
            (
                "INFORME DE PROYECTO DE INVESTIGACIÓN CUANTITATIVO",
                "PROYECTO DE INVESTIGACIÓN CUANTITATIVO",
            ),
        }


class TestDeteccionNivelDeclarado:
    """Nivel 1: casilla marcada del Anexo 10."""

    def test_casilla_marcada_por_texto(self):
        parrafos = [
            _con_casilla("PROYECTO DE INVESTIGACIÓN CUANTITATIVO"),
            _t("PLAN DE INVESTIGACIÓN"),
            _t("RECURSOS Y MATERIALES"),
        ]
        ok, nivel, valor, evidencia, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "proyecto_cuantitativo"
        assert nivel == NIVEL_DECLARADO
        assert evidencia == ["PROYECTO DE INVESTIGACIÓN CUANTITATIVO"]
        assert "declarado=proyecto_cuantitativo" in detalle
        assert ok is True

    def test_casilla_marcada_wingdings(self):
        """Word dibuja las casillas como símbolo Wingdings, no como texto."""
        parrafos = [
            _con_sym(
                "F0FE",
                "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUANTITATIVA",
            ),
            _t("POBLACIÓN Y MUESTRA"),
        ]
        _, _nivel, valor, _ev, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "tinv_cuantitativo", detalle
        assert "declarado=" in detalle

    def test_casilla_vacia_wingdings_no_declara(self):
        """F0A8 es la casilla VACÍA: no puede leerse como declaración."""
        parrafos = [
            _con_sym(
                "F0A8",
                "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUANTITATIVA",
            ),
            _t("POBLACIÓN Y MUESTRA"),
        ]
        _, _nivel, valor, _ev, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "tinv_cuantitativo"
        assert "inferido=" in detalle

    def test_casilla_sin_marcar_no_declara(self):
        """El error más fácil de cometer al leer: una casilla vacía junto a una
        etiqueta NO es una declaración."""
        parrafos = [
            _con_casilla("PROYECTO DE INVESTIGACIÓN CUANTITATIVO", marcada=False),
            _t("PLAN DE INVESTIGACIÓN"),
            _t("RECURSOS Y MATERIALES"),
        ]
        _, _nivel, valor, _ev, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "proyecto_cuantitativo"
        assert "inferido=" in detalle, "debió caer al nivel 2, no declarar"

    def test_sin_declaracion_configurada_no_hay_nivel_1(self):
        _, _nivel, valor, _ev, detalle = _detectar(
            [_con_casilla("PROYECTO DE INVESTIGACIÓN CUANTITATIVO"), _t("POBLACIÓN Y MUESTRA")]
        )
        assert valor == "tinv_cuantitativo"
        assert "inferido=" in detalle

    def test_declarado_e_inferido_que_coinciden(self):
        parrafos = [
            _con_casilla("PROYECTO DE INVESTIGACIÓN CUANTITATIVO"),
            _t("PLAN DE INVESTIGACIÓN"),
            _t("RECURSOS Y MATERIALES"),
        ]
        _, _nivel, valor, _ev, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "proyecto_cuantitativo"
        assert "declarado=" in detalle and "contradictorio" not in detalle

    def test_contradiccion_se_publica(self):
        """El autor declara un tipo pero el documento tiene la estructura de
        otro: se dice, no se elige en silencio."""
        parrafos = [
            _con_casilla("TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUALITATIVA"),
            _t("PLAN DE INVESTIGACIÓN"),
            _t("RECURSOS Y MATERIALES"),
        ]
        ok, nivel, valor, evidencia, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == TIPO_CONTRADICTORIO
        assert nivel == NIVEL_NO_DETERMINADO
        assert evidencia == [
            "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUALITATIVA",
            "PLAN DE INVESTIGACIÓN",
            "RECURSOS Y MATERIALES",
        ], "la contradicción debe reportar las dos evidencias"
        assert ok is False
        assert "declarado=tinv_cualitativo" in detalle
        assert "inferido=proyecto_cuantitativo" in detalle

    def test_etiqueta_variante_del_anexo(self):
        parrafos = [
            _con_casilla("TRABAJO DE SERVICIO"),
            _t("SECUENCIA DIDÁCTICA"),
            _t("SUSTENTO PSICOPEDAGÓGICO"),
        ]
        _, _nivel, valor, _ev, _ = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "tsp"

    def test_el_tsp_se_declara_con_el_termino_del_manual(self):
        """El manual llama a este tipo "Trabajo de Suficiencia Profesional"
        (párr. 89 y 3430). Con ese termino en la casilla del Anexo 10 el tipo
        se reconoce POR DECLARACION.

        Sin esta correccion el tipo no se pierde siempre: el detector lo
        recupera por inferencia (nivel 2) cuando el cuerpo trae 2 de las 3
        firmas. Lo que se rompe es la declaracion, y con ella el caso en que
        la estructura no aporta evidencia suficiente: ahi el documento caia
        en sin_determinar y recibia el error centinela.
        """
        parrafos = [
            _con_casilla("TRABAJO DE SUFICIENCIA PROFESIONAL"),
            _t("SECUENCIA DIDÁCTICA"),
            _t("SUSTENTO PSICOPEDAGÓGICO"),
        ]
        ok, nivel, valor, _ev, detalle = _detectar(
            parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        )
        assert valor == "tsp"
        assert nivel == NIVEL_DECLARADO
        assert ok is True
        assert "sin_determinar" not in detalle

    def test_el_tsp_sigue_aceptando_las_etiquetas_previas(self):
        """La correccion del nombre es aditiva: no debe romper lo que ya
        funcionaba, porque la facultad usa ambas formas en la practica."""
        for etiqueta in ("TRABAJO DE SERVICIO", "SERVICIO SOCIAL"):
            parrafos = [
                _con_casilla(etiqueta),
                _t("SECUENCIA DIDÁCTICA"),
                _t("SUSTENTO PSICOPEDAGÓGICO"),
            ]
            _, _nivel, valor, _ev, _ = _detectar(
                parrafos, {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
            )
            assert valor == "tsp", etiqueta


class TestLinterDeteccionTipo:
    def test_config_valida_no_reporta_hallazgos(self):
        datos = {
            "namespaces": {"w": WNS},
            "reglas": [
                {
                    "id": "deteccion_tipo_documento",
                    "severidad": "warning",
                    "descripcion": "detecta el tipo",
                    "deteccion_tipo": _cfg_deteccion({"anexo": "Anexo 10", "etiquetas": ETIQUETAS}),
                }
            ],
        }
        assert linter(datos) == []

    def test_falta_expone(self):
        cfg = _cfg_deteccion()
        del cfg["expone"]
        datos = {"reglas": [{"id": "d", "deteccion_tipo": cfg}]}
        assert any("falta 'expone'" in h for h in linter(datos))

    def test_expone_a_nivel_de_regla_tambien_sirve(self):
        datos = {
            "reglas": [{"id": "d", "expone": "tipo_documento", "deteccion_tipo": _cfg_deteccion()}]
        }
        assert linter(datos) == []

    def test_firmas_vacia(self):
        datos = {"reglas": [{"id": "d", "deteccion_tipo": {"expone": "x", "firmas": []}}]}
        assert any("'firmas' debe ser una lista no vacía" in h for h in linter(datos))

    def test_evidencia_vacia(self):
        cfg = _cfg_deteccion(firmas=[{"tipo": "t", "evidencia": [], "minimo": 1}])
        assert any(
            "necesita 'evidencia' no vacía" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_tipo_repetido(self):
        cfg = _cfg_deteccion(
            firmas=[
                {"tipo": "t", "evidencia": ["A"], "minimo": 1},
                {"tipo": "t", "evidencia": ["B"], "minimo": 1},
            ]
        )
        assert any(
            "repetido en 'firmas'" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_minimo_menor_que_uno(self):
        cfg = _cfg_deteccion(firmas=[{"tipo": "t", "evidencia": ["A"], "minimo": 0}])
        assert any(
            "necesita 'minimo' >= 1" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_minimo_por_debajo_de_minimo_global(self):
        cfg = _cfg_deteccion(firmas=[{"tipo": "t", "evidencia": ["A", "B"], "minimo": 1}])
        cfg["minimo_global"] = 2
        assert any(
            "por debajo de 'minimo_global'" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_minimo_inevitable(self):
        """Exigir más firmas de las declaradas la dejaría siempre inactiva."""
        cfg = _cfg_deteccion(firmas=[{"tipo": "t", "evidencia": ["A"], "minimo": 2}])
        assert any(
            "nunca puede cumplirse" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_declaracion_sin_etiquetas(self):
        cfg = _cfg_deteccion()
        cfg["declaracion"] = {"anexo": "Anexo 10"}
        assert any(
            "'declaracion.etiquetas' debe mapear" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_etiqueta_de_tipo_desconocido(self):
        cfg = _cfg_deteccion()
        cfg["declaracion"] = {"anexo": "Anexo 10", "etiquetas": {"inventado": ["X"]}}
        assert any(
            "no aparece en 'firmas'" in h
            for h in linter({"reglas": [{"id": "d", "deteccion_tipo": cfg}]})
        )

    def test_expone_anidado_alimenta_el_contexto(self):
        """Una condición puede apuntar a la clave que publica la sección
        `deteccion_tipo`, no solo a la de nivel de regla."""
        cfg = _cfg_deteccion()
        datos = {
            "reglas": [
                {"id": "d", "deteccion_tipo": cfg},
                {
                    "id": "e",
                    "aplicar_si": {"tipo_documento": "tinv_cuantitativo"},
                    "atributo_xml": {
                        "parte": "document",
                        "xpath": "//w:sectPr[1]/w:pgSz",
                        "atributo": "@w:w",
                        "comparacion": "eq",
                        "esperado": "11906",
                    },
                },
            ]
        }
        assert linter(datos) == []


class TestDeteccionDesdeElMotor:
    """La detección se invoca como cualquier otra regla del DSL."""

    def _regla(self, cfg):
        return {
            "id": "deteccion_tipo_documento",
            "tipo": "deteccion",
            "severidad": "warning",
            "descripcion": "Detecta el tipo de documento",
            "deteccion_tipo": cfg,
        }

    def test_publica_el_tipo_en_el_contexto(self):
        cfg = _cfg_deteccion()
        datos = {"namespaces": {"w": WNS}, "reglas": [self._regla(cfg)]}
        path = _docx_de_parrafos([_t("POBLACIÓN Y MUESTRA"), _t("INSTRUMENTO")])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert len(res) == 1
        assert res[0].passed is True

    def test_el_detalle_llega_al_reporte(self):
        """El hueco que este test fijaba quedó cerrado en el paso 3.

        `ReglaCompilada.ejecutar` ya no fuerza `found="cumple"` en las reglas
        que declaran `expone`: ahora muestran el tipo y su evidencia
        (decisión 4 del diseño). El resumen agrupado ("Tipo detectado: X.
        Motivo: ...") se construye en el paso 5.
        """
        cfg = _cfg_deteccion()
        datos = {"namespaces": {"w": WNS}, "reglas": [self._regla(cfg)]}
        path = _docx_de_parrafos([_t("POBLACIÓN Y MUESTRA"), _t("INSTRUMENTO")])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        assert res[0].found != "cumple"
        assert "tinv_cuantitativo" in res[0].found
        assert "POBLACIÓN Y MUESTRA" in res[0].found

    def test_una_condicion_consume_el_tipo_publicado(self):
        cfg = _cfg_deteccion()
        datos = {
            "namespaces": {"w": WNS},
            "reglas": [
                self._regla(cfg),
                {
                    "id": "estructura_cualitativa",
                    "severidad": "error",
                    "descripcion": "solo si es cualitativo",
                    "aplicar_si": {"tipo_documento": "tinv_cualitativo"},
                    "atributo_xml": {
                        "parte": "document",
                        "xpath": "//w:sectPr[1]/w:pgSz",
                        "atributo": "@w:w",
                        "comparacion": "eq",
                        "esperado": "999",
                    },
                },
            ],
        }
        path = _docx_de_parrafos([_t("POBLACIÓN Y MUESTRA")])
        try:
            res = validate_docx(path, datos)
        finally:
            Path(path).unlink(missing_ok=True)
        por_id = {r.rule_id: r for r in res}
        assert por_id["deteccion_tipo_documento"].passed is True
        assert por_id["estructura_cualitativa"].aplicable is False


# ---------------------------------------------------------------------------
# Paso 3: la regla discriminadora en reglas_unt.yaml
# ---------------------------------------------------------------------------

TIPOS_ESPERADOS = {
    "tsp",
    "informe_cuantitativo",
    "informe_cualitativo",
    "proyecto_cuantitativo",
    "proyecto_cualitativo",
    "tinv_revision_literatura",
    "tinv_cualitativo",
    "tinv_cuantitativo",
}


def _regla_deteccion():
    reglas = load_rules(str(RUTA_REGLAS))
    return next(r for r in reglas["reglas"] if r["id"] == "deteccion_tipo_documento")


def _validar_factory():
    """Valida el documento bueno del factory y devuelve (resultados, reporte)."""
    from docx_factory import compilar_docx, configuracion_base

    path = compilar_docx(configuracion_base())
    try:
        res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
    finally:
        Path(path).unlink(missing_ok=True)
    return res, build_report(res)


class TestReglaDeteccionEnElYaml:
    def test_es_la_primera_regla_del_yaml(self):
        """Debe ir primera: evalúa en fase 1 y alimenta el contexto."""
        reglas = load_rules(str(RUTA_REGLAS))
        assert reglas["reglas"][0]["id"] == "deteccion_tipo_documento"

    def test_total_de_reglas(self):
        assert len(load_rules(str(RUTA_REGLAS))["reglas"]) == 48

    def test_severidad_warning(self):
        assert _regla_deteccion()["severidad"] == "warning"

    def test_expone_tipo_documento(self):
        assert _regla_deteccion()["deteccion_tipo"]["expone"] == "tipo_documento"

    def test_ocho_tipos_detectables(self):
        firmas = _regla_deteccion()["deteccion_tipo"]["firmas"]
        assert {f["tipo"] for f in firmas} == TIPOS_ESPERADOS
        assert len(firmas) == len(TIPOS_ESPERADOS)

    def test_minimo_global_uno(self):
        assert _regla_deteccion()["deteccion_tipo"]["minimo_global"] == 1

    def test_todas_las_firmas_declaran_etiquetas_de_declaracion(self):
        cfg = _regla_deteccion()["deteccion_tipo"]
        assert set(cfg["declaracion"]["etiquetas"]) == TIPOS_ESPERADOS

    def test_toda_firma_tiene_minimo_positivo(self):
        for f in _regla_deteccion()["deteccion_tipo"]["firmas"]:
            assert f["minimo"] >= 1


class TestDeteccionEnDocumentosReales:
    def test_doc_bueno_se_detecta_como_cuantitativo(self):
        res, _ = _validar_factory()
        r = next(x for x in res if x.rule_id == "deteccion_tipo_documento")
        assert r.passed is True
        assert "tinv_cuantitativo" in r.found

    def test_plantilla_oficial_se_detecta_como_cuantitativo(self):
        """`recursos/` está en `.gitignore`: se omite si no está disponible."""
        base = TestSinCambioDeComportamiento._ruta_plantilla()
        if not base.exists():
            pytest.skip("las plantillas de recursos/ no están disponibles en este entorno")
        res = validate_docx(str(base), load_rules(str(RUTA_REGLAS)))
        r = next(x for x in res if x.rule_id == "deteccion_tipo_documento")
        assert r.passed is True
        assert "tinv_cuantitativo" in r.found

    def test_una_tesis_con_revision_no_se_toma_como_revision(self):
        """`ESTADO DEL ARTE` está en el marco teórico de cualquier tesis: por
        eso la firma de revisión exige además METODOLOGÍA DE REVISIÓN."""
        res, _ = _validar_factory()
        r = next(x for x in res if x.rule_id == "deteccion_tipo_documento")
        assert "tinv_revision_literatura" not in r.found


class TestInformeMuestraElTipo:
    def test_found_no_es_el_generico_cumple(self):
        """Regla `expone` = informativa: el reporte dice qué encontró."""
        res, _ = _validar_factory()
        r = next(x for x in res if x.rule_id == "deteccion_tipo_documento")
        assert r.found != "cumple"
        assert "inferido=tinv_cuantitativo" in r.found

    def test_las_demas_reglas_siguen_diciendo_cumple(self):
        """El cambio de `found` es exclusivo de las reglas que `expone`."""
        res, _ = _validar_factory()
        for r in res:
            if r.rule_id == "deteccion_tipo_documento":
                continue
            if r.passed and r.aplicable:
                assert r.found == "cumple", r.rule_id

    def test_lo_omitido_se_dice_explicitamente(self):
        """Una regla no aplicable no dice 'cumple': dice por qué se omitió."""
        res, _ = _validar_factory()
        for r in res:
            if not r.aplicable:
                assert r.found == "no aplica a este documento"

    def test_el_semaforo_no_depende_de_la_deteccion(self):
        """Quitar la regla discriminadora (y con ella el filtrado) deja el
        semáforo en rojo, pero solo por los 2 esquemas imposibles. Con ella el
        documento sale verde: eso es exactamente el defecto que se corrige."""
        reglas = load_rules(str(RUTA_REGLAS))
        from docx_factory import compilar_docx, configuracion_base

        # Se quita el `aplicar_si` de las 3 estructuras (no la regla que
        # expone la clave: sin ella el linter rechazaría el archivo, que es
        # lo correcto) para reconstruir el estado previo al paso 4.
        sin_filtrar = {
            **reglas,
            "reglas": [{k: v for k, v in r.items() if k != "aplicar_si"} for r in reglas["reglas"]],
        }
        path = compilar_docx(configuracion_base())
        try:
            completo = build_report(validate_docx(path, reglas))
            previo = build_report(validate_docx(path, sin_filtrar))
        finally:
            Path(path).unlink(missing_ok=True)
        assert completo["semaforo"] == "verde"
        assert previo["semaforo"] == "rojo"
        assert previo["resumen"]["fallidos_error"] == 2


class TestMutacionDeLaDeteccion:
    def _validar_mutado(self):
        from docx_factory import aplicar_mutacion, compilar_docx, configuracion_base

        path = compilar_docx(aplicar_mutacion("deteccion_tipo_documento", configuracion_base()))
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)
        return res, build_report(res)

    def test_declaracion_contraria_se_reporta_como_contradiccion(self):
        res, _ = self._validar_mutado()
        r = next(x for x in res if x.rule_id == "deteccion_tipo_documento")
        assert r.passed is False
        assert "contradictorio" in r.found
        assert "proyecto_cualitativo" in r.found

    def test_solo_mueve_la_deteccion_y_las_reglas_del_tipo(self):
        """La mutación añade un anexo y no toca ningún título, así que lo
        único que cambia es la clasificación: al quedar contradictoria la
        detección, la estructura que antes aplicaba (cuantitativo) deja de
        aplicar porque el tipo ya no es ninguno de los tres, y con ella los
        mínimos de referencias y anexos del mismo tipo. Las reglas de los
        otros tipos ya eran no aplicables y siguen siéndolo."""
        limpio, _ = _validar_factory()
        sucio, _ = self._validar_mutado()
        antes = {r.rule_id: (r.passed, r.found, r.aplicable) for r in limpio}
        despues = {r.rule_id: (r.passed, r.found, r.aplicable) for r in sucio}
        movidas = {rid for rid in antes if antes[rid] != despues[rid]}
        assert movidas == {
            "deteccion_tipo_documento",
            "estructura_tinv_cuantitativo",
            "referencias_minimo_cuantitativo",
            "anexos_minimos_cuantitativo",
        }
        # La que dejó de aplicar pasó de aplicable a no aplicable.
        assert antes["estructura_tinv_cuantitativo"][2] is True
        assert despues["estructura_tinv_cuantitativo"][2] is False

    def test_una_deteccion_contradictoria_da_un_solo_error_claro(self):
        """Un documento que declara un tipo que la estructura desmiente sale en
        rojo, pero con UN error que dice qué hacer, no con dos errores de
        secciones que el estudiante no puede corregir sin adivinar el tipo.

        La detección sigue siendo `warning` (informa, no bloquea) y las
        reglas tipo-específicas no aplican: el único error es el centinela.
        """
        sucio, _ = self._validar_mutado()
        deteccion = next(r for r in sucio if r.rule_id == "deteccion_tipo_documento")
        assert deteccion.severity.value == "warning"
        assert deteccion.passed is False

        # Ninguna regla tipo-específica se evalúa: no sabemos el tipo, así
        # que no se puede exigir la estructura ni los mínimos de ninguno.
        for rid in TIPO_ESPECIFICAS:
            r = next(x for x in sucio if x.rule_id == rid)
            assert r.aplicable is False, rid

        fallidos = {r.rule_id for r in sucio if not r.passed and r.severity.value == "error"}
        assert fallidos == {"tipo_documento_contradictorio"}

    def test_el_centinela_contradictorio_explica_el_conflicto(self):
        """El error no dice solo "algo no cuadra": incluye la evidencia (qué
        declaró el Anexo 10 y qué se dedujo de la estructura) y dice qué
        corregir."""
        sucio, _ = self._validar_mutado()
        centinela = next(r for r in sucio if r.rule_id == "tipo_documento_contradictorio")
        assert centinela.severity.value == "error"
        assert centinela.passed is False
        assert centinela.aplicable is True
        # La evidencia viene del detalle real de la detección.
        assert "declarado=" in centinela.found
        assert "inferido=" in centinela.found
        # Y el mensaje dice qué hacer.
        assert "Anexo 10" in centinela.message


# ---------------------------------------------------------------------------
# Paso 6: los dos casos límite, sin huecos de seguridad
# ---------------------------------------------------------------------------


class TestCasosLimite:
    """Ningún documento mal estructurado puede salir en verde.

    Hay dos formas de no poder clasificar un documento, y las dos tienen que
    terminar en un error que el estudiante pueda entender y corregir: el tipo
    no se pudo determinar, o la declaración choca con la estructura.
    """

    def test_doc_sin_marcadores_da_un_solo_error(self):
        """Un documento sin Anexo 10 y sin firmas: sale 1 error claro, no 8
        errores de estructura inventados."""
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)

        # Este doc mínimo también incumple formato (fuente, tamaños), así que
        # lo que se comprueba es que NO aparecen errores de estructura: el
        # único error de TIPO es el centinela, no las 3 estructuras.
        errores_tipo = [
            r
            for r in res
            if not r.passed
            and r.severity.value == "error"
            and (r.rule_id in TIPO_ESPECIFICAS or "tipo_documento" in r.rule_id)
        ]
        assert [r.rule_id for r in errores_tipo] == ["tipo_documento_no_determinado"]

    def test_tsp_declarado_sin_evidencia_estructural_no_es_sin_determinar(self):
        """Integración con el YAML de producción: un TSP que el autor declara
        con el término del manual debe reconocerse por declaración aunque su
        estructura todavía no aporte 2 de las 3 firmas.

        Este es el caso que la corrección arregla. Sin ella el documento caía
        en `sin_determinado` y salía con el error centinela
        `tipo_documento_no_determinado`, que le pedía al estudiante adivinar
        su propio tipo en vez de decirle que le faltan secciones.
        """
        path = _make_docx(
            headings=["INTRODUCCION", "MARCO TEORICO", "CONCLUSIONES"],
            cover="☒ TRABAJO DE SUFICIENCIA PROFESIONAL",
        )
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)

        deteccion = next(r for r in res if r.rule_id == "deteccion_tipo_documento")
        assert "declarado=tsp" in deteccion.found

        centinelas = [
            r.rule_id
            for r in res
            if r.rule_id in {"tipo_documento_no_determinado", "tipo_documento_contradictorio"}
        ]
        assert centinelas == [], (
            f"un tipo declarado no puede salir como no determinado: aparecieron {centinelas}"
        )

    def test_cada_tipo_se_declara_con_los_dos_vocabularios(self):
        """El manual usa dos vocabularios y no son intercambiables: el del
        titulo que se opta y el que imprime el formulario del Anexo 10.

        El segundo es el que de verdad aparece marcado, porque la declaracion
        se lee del Anexo 10. Antes de esta correccion, un autor que marcaba la
        casilla del formulario no declaraba nada: el motor buscaba el
        vocabulario del titulo, que en el Anexo 10 no aparece ni una vez.
        """
        casos = [
            (
                "tinv_cuantitativo",
                "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUANTITATIVA",
                "TRABAJO DE INVESTIGACIÓN CUANTITATIVO",
            ),
            (
                "tinv_cualitativo",
                "TESIS PARA OBTENER EL TÍTULO PROFESIONAL EN INVESTIGACIÓN CUALITATIVA",
                "TRABAJO DE INVESTIGACIÓN CUALITATIVO",
            ),
            (
                "tinv_revision_literatura",
                "TESIS PARA OBTENER EL GRADO DE BACHILLER EN INVESTIGACIÓN",
                "TRABAJO DE INVESTIGACIÓN DE REVISIÓN DE LA LITERATURA",
            ),
        ]
        for tipo, del_titulo, del_formulario in casos:
            for vocabulario in (del_titulo, del_formulario):
                # El cuerpo no aporta ninguna firma: si el tipo se reconoce,
                # es solo porque la declaracion se leyo.
                _ok, nivel, valor, _ev, _d = _detectar(
                    [_con_casilla(vocabulario)],
                    {"anexo": "Anexo 10", "etiquetas": ETIQUETAS},
                )
                assert valor == tipo, f"{vocabulario} deberia declarar {tipo}"
                assert nivel == NIVEL_DECLARADO, vocabulario

    def test_ninguna_etiqueta_declara_a_un_tipo_ajeno(self):
        """Como el cotejo es por subcadena, anadir el vocabulario del
        formulario podria hacer que una sola casilla declarara a dos tipos. Se
        comprueba que cada etiqueta declara exactamente al tipo que la posee,
        para los 8 tipos y todas sus etiquetas."""
        for tipo, etiquetas in ETIQUETAS.items():
            for etiqueta in etiquetas:
                _ok, _nivel, valor, _ev, _d = _detectar(
                    [_con_casilla(etiqueta)],
                    {"anexo": "Anexo 10", "etiquetas": ETIQUETAS},
                )
                assert valor == tipo, f"{etiqueta} declaro {valor}, no {tipo}"

    def test_las_casillas_del_anexo_10_declaran_su_tipo(self):
        """Integracion con el YAML de produccion para el otro vocabulario.

        El Anexo 10 ofrece casillas que dicen "TRABAJO DE INVESTIGACION
        CUANTITATIVO" (parrr. 5014-5016 del manual), no el nombre del titulo.
        Esas son las palabras que el autor realmente marca, asi que son las
        que el motor tiene que leer. Con el vocabulario equivocado, marcar la
        casilla no declaraba nada y el documento caia en sin_determinado con
        su error centinela.
        """
        casos = [
            ("TRABAJO DE INVESTIGACIÓN CUANTITATIVO", "tinv_cuantitativo"),
            ("TRABAJO DE INVESTIGACIÓN CUALITATIVO", "tinv_cualitativo"),
            (
                "TRABAJO DE INVESTIGACIÓN DE REVISIÓN DE LA LITERATURA",
                "tinv_revision_literatura",
            ),
            ("TRABAJO DE SUFICIENCIA PROFESIONAL", "tsp"),
        ]
        for casilla, tipo in casos:
            path = _make_docx(
                headings=["INTRODUCCION", "MARCO TEORICO", "CONCLUSIONES"],
                cover=f"☒ {casilla}",
            )
            try:
                res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
            finally:
                Path(path).unlink(missing_ok=True)

            deteccion = next(r for r in res if r.rule_id == "deteccion_tipo_documento")
            assert f"declarado={tipo}" in deteccion.found, casilla

            centinelas = [
                r.rule_id
                for r in res
                if r.rule_id in {"tipo_documento_no_determinado", "tipo_documento_contradictorio"}
            ]
            assert centinelas == [], f"{casilla} produjo {centinelas}"

    def test_el_centinela_no_determinado_es_aplicable_y_explica(self):
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)
        c = next(r for r in res if r.rule_id == "tipo_documento_no_determinado")
        assert c.passed is False
        assert c.aplicable is True
        assert "no se pudo determinar" in c.message.lower()
        # El `found` trae el detalle real de por qué no se clasificó.
        assert "sin_determinado" in c.found

    def test_doc_contradictorio_da_un_solo_error(self):
        """Anexo 10 que declara algo que la estructura desmiente: 1 error."""
        sucio, rep = TestMutacionDeLaDeteccion()._validar_mutado()
        fallidos_error = {r.rule_id for r in sucio if not r.passed and r.severity.value == "error"}
        assert fallidos_error == {"tipo_documento_contradictorio"}
        # Y el semáforo está en rojo.
        assert rep["semaforo"] == "rojo"

    def test_ningun_caso_limite_sale_en_verde(self):
        """El invariante del paso: sin determinar o contradictorio, rojo."""
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            rep = build_report(validate_docx(path, load_rules(str(RUTA_REGLAS))))
        finally:
            Path(path).unlink(missing_ok=True)
        assert rep["semaforo"] == "rojo"

    def test_un_tipo_valido_no_genera_centinela(self):
        """El documento bueno NO lleva centinela: los estados terminales solo
        aparecen cuando de verdad no se pudo clasificar."""
        from docx_factory import compilar_docx, configuracion_base  # noqa: E402

        path = compilar_docx(configuracion_base())
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)
        ids = {r.rule_id for r in res}
        assert "tipo_documento_no_determinado" not in ids
        assert "tipo_documento_contradictorio" not in ids
        assert build_report(res)["semaforo"] == "verde"

    def test_el_centinela_aparece_tras_la_deteccion(self):
        """Va justo después de la detección, que es donde el estudiante
        empieza a leer."""
        path = _make_docx(headings=["INTRODUCCION", "RESULTADOS"])
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)
        ids = [r.rule_id for r in res]
        assert (
            ids.index("tipo_documento_no_determinado") == ids.index("deteccion_tipo_documento") + 1
        )


# ---------------------------------------------------------------------------
# Revisión del PR #45 — inferencia solo sobre títulos, declaración robusta y
# aviso de tipo sin estructura cargada.
# ---------------------------------------------------------------------------


class TestInferenciaSoloTitulos:
    """Las firmas estructurales se cotejan SOLO contra párrafos con estilo de
    título (respuesta a la pregunta 1 de la revisión). La prosa es ruido: la
    línea "Línea de investigación:" de la carátula, o un párrafo que mencione
    "recursos y materiales", no debe contar como evidencia y virar el tipo."""

    def test_un_parrafo_normal_no_cuenta_como_firma(self):
        # Prosa con las evidencias de proyecto en párrafos normales.
        prose = [
            _para("Línea de Investigación: innovación educativa"),
            _para("3.4 Recursos y materiales del proyecto"),
            _para("Plan de investigación del pregrado"),
        ]
        _ok, _nivel, valor, evidencia, detalle = _detectar(
            [*prose, _t("POBLACIÓN Y MUESTRA"), _t("INSTRUMENTO")]
        )
        assert valor == "tinv_cuantitativo", detalle
        assert "proyecto_cuantitativo" not in evidencia

    def test_tesis_tinv_que_menciona_proyecto_en_prosa_no_vira(self):
        """Caso exacto de la revisión: una tesis TINV que mencione "recursos
        y materiales" o "plan de investigación" en un párrafo alcanzaba el
        mínimo de proyecto y ganaba. Con títulos, la prosa no cuenta."""
        prose = [_para("Los recursos y materiales de la escuela"), _para("Plan de investigación")]
        _ok, _nivel, valor, _ev, detalle = _detectar(
            [*prose, _t("VARIABLE"), _t("POBLACIÓN Y MUESTRA")]
        )
        assert valor == "tinv_cuantitativo", detalle

    def test_un_proyecto_real_si_se_detecta(self):
        """El fix no debe cegar la detección: si el documento trae los títulos
        de proyecto como encabezados, se detecta proyecto."""
        _ok, _nivel, valor, _ev, detalle = _detectar(
            [_t("PLAN DE INVESTIGACIÓN"), _t("LÍNEA DE INVESTIGACIÓN")]
        )
        assert valor == "proyecto_cuantitativo", detalle


_W14_XMLNS = 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'


def _con_content_control(texto, val="1"):
    """Etiqueta dentro de un content-control de Word (`w:sdt`) con casilla
    `w14:checkbox` en su `w:sdtPr` — el `w14:checked` vive fuera del párrafo."""
    return (
        "<w:sdt>"
        f'<w:sdtPr><w14:checkbox><w14:checked w14:val="{val}"/></w14:checkbox></w:sdtPr>'
        f"<w:sdtContent>{_para(texto)}</w:sdtContent>"
        "</w:sdt>"
    )


def _fila_con_casilla_y_etiqueta(etiqueta, char="F0FE"):
    """Fila de tabla del Anexo 10: la casilla (símbolo Wingdings) en una celda
    y la etiqueta en la celda vecina."""
    celda_casilla = (
        f'<w:tc><w:p><w:r><w:sym w:font="Wingdings" w:char="{char}"/></w:r></w:p></w:tc>'
    )
    celda_etiqueta = f"<w:tc>{_para(etiqueta)}</w:tc>"
    return f"<w:tbl><w:tr>{celda_casilla}{celda_etiqueta}</w:tr></w:tbl>"


class TestDeclaracionEnTablaYSdt:
    """Respuesta a la pregunta 2 de la revisión: la casilla del Anexo 10 debe
    leerse aunque viva dentro de una tabla, en un content-control de Word, o
    en una celda distinta a la de su etiqueta."""

    def test_declaracion_en_una_tabla_con_etiqueta_en_otra_celda(self):
        declaracion = {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        _ok, nivel, valor, _ev, detalle = _detectar(
            [_fila_con_casilla_y_etiqueta("PROYECTO DE INVESTIGACIÓN CUANTITATIVO")],
            declaracion=declaracion,
        )
        assert nivel == NIVEL_DECLARADO
        assert valor == "proyecto_cuantitativo", detalle

    def test_casilla_vacia_en_la_tabla_no_declara(self):
        declaracion = {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        _ok, nivel, valor, _ev, detalle = _detectar(
            ["La fila 1", _fila_con_casilla_y_etiqueta("INFORME DE PROYECTO", char="F0A8")],
            declaracion=declaracion,
        )
        assert valor == TIPO_SIN_DETERMINAR
        assert nivel == NIVEL_NO_DETERMINADO

    def test_declaracion_en_content_control_w14(self):
        declaracion = {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        _ok, _nivel, valor, _ev, detalle = _detectar(
            [_con_content_control("PROYECTO DE INVESTIGACIÓN CUANTITATIVO")],
            declaracion=declaracion,
            xmlns=_W14_XMLNS,
        )
        assert valor == "proyecto_cuantitativo", detalle

    def test_content_control_w14_desmarcado_no_declara(self):
        declaracion = {"anexo": "Anexo 10", "etiquetas": ETIQUETAS}
        _ok, nivel, valor, _ev, detalle = _detectar(
            [_con_content_control("PROYECTO DE INVESTIGACIÓN CUANTITATIVO", val="0")],
            declaracion=declaracion,
            xmlns=_W14_XMLNS,
        )
        assert valor == TIPO_SIN_DETERMINAR
        assert nivel == NIVEL_NO_DETERMINADO


class TestAvisoSinEstructura:
    """Respuesta a la salida B de la revisión: un tipo de documento cuyo
    esquema aún no tiene validación estructural (proyecto, informe y TSP) no
    debe salir en verde silencioso, pero tampoco bloquear: avisa con warning."""

    @pytest.mark.parametrize(
        ("titulos", "esperado", "re"),
        [
            (
                ["PLAN DE INVESTIGACIÓN", "LÍNEA DE INVESTIGACIÓN"],
                "proyecto_cuantitativo",
                "PROYECTO",
            ),
            (
                ["SELECCIÓN DE PARTICIPANTES", "UNIDAD DE ANÁLISIS"],
                "proyecto_cualitativo",
                "PROYECTO",
            ),
            (
                ["SITUACIÓN PROBLEMATIZADA", "DISEÑO DE CONTRASTACIÓN"],
                "informe_cuantitativo",
                "INFORME",
            ),
            (
                [
                    "SITUACIÓN PROBLEMATIZADA",
                    "PARTICIPANTES",
                    "INSTRUMENTOS USADOS EN LA RECOLECCIÓN",
                ],
                "informe_cualitativo",
                "INFORME",
            ),
            (["SECUENCIA DIDÁCTICA", "SUSTENTO PSICOPEDAGÓGICO"], "tsp", "SUFICIENCIA"),
        ],
    )
    def test_aviso_para_los_cinco_tipos_sin_estructura(self, titulos, esperado, re):
        path = _make_docx(headings=titulos)
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)

        deteccion = next(r for r in res if r.rule_id == "deteccion_tipo_documento")
        assert esperado in deteccion.found

        avisos = [r for r in res if r.rule_id == "tipo_documento_sin_estructura"]
        assert avisos, "un tipo sin estructura debe emitir el aviso"
        assert [a.severity.value for a in avisos] == ["warning"]
        assert re in avisos[0].message

    def test_tinv_no_emite_el_aviso(self):
        path = _make_docx(headings=["VARIABLE", "POBLACIÓN Y MUESTRA"])
        try:
            res = validate_docx(path, load_rules(str(RUTA_REGLAS)))
        finally:
            Path(path).unlink(missing_ok=True)
        ids = {r.rule_id for r in res}
        assert "tipo_documento_sin_estructura" not in ids
