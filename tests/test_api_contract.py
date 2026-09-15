"""Tests de contrato para el endpoint POST /validar.

Verifica que la API devuelva los códigos de estado, la estructura
de respuesta y los campos correctos según el CONTRATO_API.md.

Uso:
    pytest tests/test_api_contract.py -v
"""
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from validator.api import app

# ---------------------------------------------------------------------------
# Configuración de tests
# ---------------------------------------------------------------------------

CLIENTE = TestClient(app)

RECURSOS_DIR = Path(__file__).resolve().parent.parent / "recursos"
PLANTILLA = RECURSOS_DIR / "EDUCACION INICIAL-PLANTILLA INVESTIGACIÓN CUANTITATIVA.docx"

# Campos esperados en cada resultado de regla
CAMPOS_RESULTADO = {
    "rule_id",
    "paso",
    "severidad",
    "mensaje",
    "esperado",
    "encontrado",
    "ubicacion",
    "fuente",
    "cita",
}

CAMPOS_RESUMEN = {"total", "fallidos_error", "fallidos_warning"}

CAMPOS_METADATOS = {
    "archivo_nombre",
    "archivo_tamano_bytes",
    "reglas_evaluadas",
    "version_esquema",
}


# ---------------------------------------------------------------------------
# Tests: respuesta exitosa (200)
# ---------------------------------------------------------------------------


class TestRespuestaExitosa:
    """Tests para el caso feliz: DOCX válido → 200 con reporte completo."""

    @pytest.fixture(autouse=True)
    def _cargar_respuesta(self):
        """Envía la plantilla oficial y guarda la respuesta."""
        if not PLANTILLA.exists():
            pytest.skip("Plantilla de prueba no disponible")
        with open(PLANTILLA, "rb") as f:
            self.respuesta = CLIENTE.post(
                "/validar",
                files={"archivo": ("tesis.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        self.datos = self.respuesta.json()

    def test_status_code(self):
        """El endpoint debe devolver 200 para un DOCX válido."""
        assert self.respuesta.status_code == 200

    def test_semaforo_presente(self):
        """La respuesta debe incluir 'semaforo' (verde o rojo)."""
        assert "semaforo" in self.datos
        assert self.datos["semaforo"] in ("verde", "rojo")

    def test_resumen_estructura(self):
        """El resumen debe tener total, fallidos_error, fallidos_warning."""
        resumen = self.datos["resumen"]
        assert set(resumen.keys()) == CAMPOS_RESUMEN
        assert isinstance(resumen["total"], int)
        assert resumen["total"] > 0

    def test_resultados_es_lista(self):
        """resultados debe ser una lista con al menos un elemento."""
        assert isinstance(self.datos["resultados"], list)
        assert len(self.datos["resultados"]) > 0

    def test_resultados_campos(self):
        """Cada resultado debe tener los campos del contrato."""
        for r in self.datos["resultados"]:
            assert set(r.keys()) == CAMPOS_RESULTADO, f"Faltan campos en: {r['rule_id']}"

    def test_resultados_severidades_validas(self):
        """Las severidades deben ser 'error' o 'warning'."""
        for r in self.datos["resultados"]:
            assert r["severidad"] in ("error", "warning")

    def test_resultados_paso_es_bool(self):
        """El campo 'paso' debe ser booleano."""
        for r in self.datos["resultados"]:
            assert isinstance(r["paso"], bool)

    def test_prompts_ia_presente(self):
        """como_preguntar_a_una_ia debe ser una lista."""
        assert "como_preguntar_a_una_ia" in self.datos
        assert isinstance(self.datos["como_preguntar_a_una_ia"], list)

    def test_prompts_ia_campos(self):
        """Cada prompt IA debe tener rule_id y prompt."""
        for p in self.datos["como_preguntar_a_una_ia"]:
            assert "rule_id" in p
            assert "prompt" in p
            assert isinstance(p["prompt"], str)
            assert len(p["prompt"]) > 0

    def test_metadatos_presente(self):
        """La respuesta debe incluir metadatos del procesamiento."""
        metadatos = self.datos["metadatos"]
        assert set(metadatos.keys()) == CAMPOS_METADATOS
        assert metadatos["archivo_nombre"] == "tesis.docx"
        assert metadatos["archivo_tamano_bytes"] > 0
        assert metadatos["reglas_evaluadas"] == len(self.datos["resultados"])

    def test_coherencia_semaforo_resumen(self):
        """Si hay fallidos_error > 0, semáforo debe ser 'rojo'."""
        if self.datos["resumen"]["fallidos_error"] > 0:
            assert self.datos["semaforo"] == "rojo"
        else:
            assert self.datos["semaforo"] == "verde"


# ---------------------------------------------------------------------------
# Tests: query param incluir_prompts_ia
# ---------------------------------------------------------------------------


class TestQueryParams:
    """Tests para el parámetro incluir_prompts_ia."""

    def test_prompts_deshabilitados(self):
        """Si incluir_prompts_ia=false, la lista debe estar vacía."""
        if not PLANTILLA.exists():
            pytest.skip("Plantilla de prueba no disponible")
        with open(PLANTILLA, "rb") as f:
            respuesta = CLIENTE.post(
                "/validar?incluir_prompts_ia=false",
                files={"archivo": ("tesis.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        assert respuesta.status_code == 200
        assert respuesta.json()["como_preguntar_a_una_ia"] == []

    def test_prompts_habilitados_por_defecto(self):
        """Por defecto, los prompts IA deben estar habilitados."""
        if not PLANTILLA.exists():
            pytest.skip("Plantilla de prueba no disponible")
        with open(PLANTILLA, "rb") as f:
            respuesta = CLIENTE.post(
                "/validar",
                files={"archivo": ("tesis.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        assert respuesta.status_code == 200
        # Si hay errores, debe haber prompts
        datos = respuesta.json()
        if datos["resumen"]["fallidos_error"] + datos["resumen"]["fallidos_warning"] > 0:
            assert len(datos["como_preguntar_a_una_ia"]) > 0


# ---------------------------------------------------------------------------
# Tests: errores de cliente
# ---------------------------------------------------------------------------


class TestErrores:
    """Tests para los diferentes códigos de error."""

    def test_archivo_faltante(self):
        """Sin campo 'archivo' → 422 (validación de FastAPI)."""
        respuesta = CLIENTE.post("/validar")
        assert respuesta.status_code == 422

    def test_tipo_no_soportado(self):
        """Archivo .txt → 415."""
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("prueba.txt", b"contenido", "text/plain")},
        )
        assert respuesta.status_code == 415
        assert "detail" in respuesta.json()

    def test_archivo_vacio(self):
        """Archivo vacío .docx → 422."""
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("vacio.docx", b"", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert respuesta.status_code == 422
        assert "vacío" in respuesta.json()["detail"]

    def test_archivo_corrupto(self):
        """Archivo ZIP corrupto con extensión .docx → 422."""
        contenido_invalido = b"esto no es un zip"
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("corrupto.docx", contenido_invalido, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert respuesta.status_code == 422
        assert "detail" in respuesta.json()

    def test_archivo_demasiado_grande(self):
        """Archivo >10 MB → 413."""
        # Crear contenido de 11 MB (11 * 1024 * 1024 bytes)
        contenido_grande = b"x" * (11 * 1024 * 1024)
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("grande.docx", contenido_grande, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert respuesta.status_code == 413
        assert "10 MB" in respuesta.json()["detail"]

    def test_content_type_octet_stream(self):
        """Algunos navegadores envían application/octet-stream para .docx → debe aceptarse."""
        if not PLANTILLA.exists():
            pytest.skip("Plantilla de prueba no disponible")
        with open(PLANTILLA, "rb") as f:
            respuesta = CLIENTE.post(
                "/validar",
                files={"archivo": ("tesis.docx", f, "application/octet-stream")},
            )
        # Debe aceptar el archivo (extensión .docx válida)
        assert respuesta.status_code == 200
        assert respuesta.json()["semaforo"] in ("verde", "rojo")


# ---------------------------------------------------------------------------
# Tests: paridad API = CLI
# ---------------------------------------------------------------------------


class TestParidadAPICLI:
    """Verifica que la respuesta de la API tenga la misma información que el CLI."""

    def test_mismos_campos_que_motor(self):
        """Los campos del motor (RuleResult.to_dict) deben aparecer en la respuesta API."""
        if not PLANTILLA.exists():
            pytest.skip("Plantilla de prueba no disponible")

        from validator.api import REGLAS_YAML_PATH
        from validator.engine import build_report, load_rules, validate_docx

        # El motor se compara contra el MISMO YAML que carga la API (F5: DSL).
        rules_data = load_rules(REGLAS_YAML_PATH)
        resultados_motor = validate_docx(str(PLANTILLA), rules_data)
        reporte = build_report(resultados_motor)

        with open(PLANTILLA, "rb") as f:
            respuesta = CLIENTE.post(
                "/validar",
                files={"archivo": ("tesis.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )

        datos_api = respuesta.json()

        # Mismos counts
        assert datos_api["resumen"]["total"] == reporte["resumen"]["total"]
        assert datos_api["resumen"]["fallidos_error"] == reporte["resumen"]["fallidos_error"]
        assert datos_api["resumen"]["fallidos_warning"] == reporte["resumen"]["fallidos_warning"]

        # Mismos semáforo
        assert datos_api["semaforo"] == reporte["semaforo"]

        # Mismos rule_ids
        ids_motor = {r.rule_id for r in resultados_motor}
        ids_api = {r["rule_id"] for r in datos_api["resultados"]}
        assert ids_api == ids_motor

        # Mismos passed values
        for r_motor, r_api in zip(resultados_motor, datos_api["resultados"]):
            assert r_motor.passed == r_api["paso"], f"Discrepancia en {r_motor.rule_id}"
