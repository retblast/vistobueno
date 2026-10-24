"""Tests de contrato para el endpoint POST /validar.

Verifica que la API devuelva los códigos de estado, la estructura
de respuesta y los campos correctos según el CONTRATO_API.md.

Uso:
    pytest tests/test_api_contract.py -v
"""

import io
import zipfile
from pathlib import Path

import pytest
from _docx_generator import build_large_docx
from _mutations import aplicar_mutacion
from conftest import (
    CAMPOS_METADATOS,
    CAMPOS_RESULTADO,
    CAMPOS_RESUMEN,
    CLIENTE,
    MIME_DOCX,
    ruta_docx_prueba,
    subir_plantilla,
)
from docx_factory import compilar_docx, configuracion_base

import validator.api
from validator.api import CAMPOS_EXTRAIDOS_FICHA, CAMPOS_MANUALES_FICHA, REGLAS_YAML_PATH
from validator.api_models import ResultadoReglaAPI
from validator.engine import build_report, load_rules, validate_docx

# ---------------------------------------------------------------------------
# Tests: respuesta exitosa (200)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def respuesta_plantilla():
    """Envía la plantilla oficial una sola vez por módulo.

    Una sola validación (47 reglas) alcanza para todos los tests de
    TestRespuestaExitosa, cuya aserciones son de solo lectura.
    """
    return subir_plantilla()


class TestRespuestaExitosa:
    """Tests para el caso feliz: DOCX válido → 200 con reporte completo."""

    @pytest.fixture(autouse=True)
    def _cargar_respuesta(self, respuesta_plantilla):
        """Comparte la respuesta en cada test (las aserciones solo leen)."""
        self.respuesta = respuesta_plantilla
        self.datos = respuesta_plantilla.json()

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

        # Semántica nueva: reglas_evaluadas = total_evaluadas (43 para doc bueno),
        # reglas_totales = total de reglas en YAML (49)
        rules_data = load_rules(REGLAS_YAML_PATH)
        resultados_motor = validate_docx(str(ruta_docx_prueba()), rules_data)
        reporte = build_report(resultados_motor)
        assert metadatos["reglas_evaluadas"] == reporte["resumen"]["total_evaluadas"]
        assert metadatos["reglas_totales"] == reporte["resumen"]["total"]

    def test_aplicable_en_resultados(self):
        """Cada resultado debe tener 'aplicable'; las dos estructuras de otros
        tipos deben venir con aplicable=False para el documento bueno."""
        aplicables = {r["rule_id"]: r["aplicable"] for r in self.datos["resultados"]}
        # Regla genérica siempre aplicable
        assert aplicables.get("papel_tamano") is True
        # Las 3 estructuras TINV: solo la cuantitativa aplica al doc bueno
        assert aplicables.get("estructura_tinv_cuantitativo") is True
        assert aplicables.get("estructura_tinv_cualitativo") is False
        assert aplicables.get("estructura_tinv_revision_literatura") is False

    def test_resumen_conteos_nuevos(self):
        """Los nuevos campos del resumen coinciden con el motor."""
        rules_data = load_rules(REGLAS_YAML_PATH)
        resultados_motor = validate_docx(str(ruta_docx_prueba()), rules_data)
        reporte = build_report(resultados_motor)
        resumen = self.datos["resumen"]
        assert resumen["total_evaluadas"] == reporte["resumen"]["total_evaluadas"]
        assert resumen["reglas_no_aplicables"] == reporte["resumen"]["reglas_no_aplicables"]

    def test_tipo_documento_metadata(self):
        """Metadatos opcionales de tipo de documento están presentes."""
        metadatos = self.datos["metadatos"]
        for campo in (
            "tipo_documento_declarado",
            "tipo_documento_inferido",
            "tipo_documento_estado",
        ):
            assert campo in metadatos, f"Falta {campo} en metadatos"
        # Para el doc bueno (plantilla cuantitativa), se infiere el tipo
        assert metadatos["tipo_documento_estado"] == "vigente"
        assert metadatos["tipo_documento_inferido"] is not None

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
        respuesta = subir_plantilla("/validar?incluir_prompts_ia=false")
        assert respuesta.status_code == 200
        assert respuesta.json()["como_preguntar_a_una_ia"] == []

    def test_prompts_habilitados_por_defecto(self):
        """Por defecto, los prompts IA deben estar habilitados."""
        respuesta = subir_plantilla()
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
            files={"archivo": ("vacio.docx", b"", MIME_DOCX)},
        )
        assert respuesta.status_code == 422
        assert "vacío" in respuesta.json()["detail"]

    def test_archivo_corrupto(self):
        """Archivo ZIP corrupto con extensión .docx → 422."""
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("corrupto.docx", b"esto no es un zip", MIME_DOCX)},
        )
        assert respuesta.status_code == 422
        assert "detail" in respuesta.json()

    def test_zip_valido_pero_no_docx(self):
        """ZIP válido pero sin document.xml → 422 (corrupto)."""
        # Crear un ZIP válido pero con contenido que no es DOCX
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("random/file.txt", "esto no es un documento Word")
            zf.writestr("data/info.json", '{"clave": "valor"}')
        buf.seek(0)
        contenido = buf.read()

        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("falso.docx", contenido, MIME_DOCX)},
        )
        # El KeyError por document.xml faltante se captura y devuelve
        # 422 con un mensaje descriptivo.
        assert respuesta.status_code == 422
        assert "detail" in respuesta.json()
        assert "Word válido" in respuesta.json()["detail"]

    def test_archivo_demasiado_grande(self):
        """Archivo >10 MB → 413."""
        contenido = build_large_docx(target_bytes=11 * 1024 * 1024)
        assert len(contenido) > 10 * 1024 * 1024

        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("grande.docx", contenido, MIME_DOCX)},
        )
        assert respuesta.status_code == 413
        assert "excede" in respuesta.json()["detail"].lower()

    def test_archivo_limite_exacto(self):
        """Archivo justo bajo 10 MB → 200 (debe pasar)."""
        min_bytes = 10 * 1024 * 1024
        contenido = build_large_docx(target_bytes=min_bytes, seed=99)
        assert len(contenido) <= min_bytes

        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("limite.docx", contenido, MIME_DOCX)},
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["semaforo"] in ("verde", "rojo")

    def test_archivo_sin_nombre(self):
        """UploadFile con nombre vacío → 400 o 422."""
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("", b"contenido", MIME_DOCX)},
        )
        assert respuesta.status_code in (400, 422)

    def test_content_type_omitido(self):
        """Sin Content-Type específico → debe aceptarse por extensión .docx."""
        respuesta = subir_plantilla(mime="")
        assert respuesta.status_code == 200

    def test_archivo_nombre_con_espacios(self):
        """Nombre con espacios y caracteres especiales → debe procesarse."""
        respuesta = subir_plantilla(nombre="mi tesis (copia).docx")
        assert respuesta.status_code == 200
        assert respuesta.json()["metadatos"]["archivo_nombre"] == "mi tesis (copia).docx"

    def test_content_type_octet_stream(self):
        """Algunos navegadores envían application/octet-stream para .docx → debe aceptarse."""
        respuesta = subir_plantilla(mime="application/octet-stream")
        assert respuesta.status_code == 200
        assert respuesta.json()["semaforo"] in ("verde", "rojo")

    def test_zip_magic_bytes_invalidos(self):
        """Archivo .docx con cabecera que no es ZIP (PK) → 422."""
        contenido = b"MZ" + b"\x00" * 200  # cabecera MZ (EXE) + relleno
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("falso.docx", contenido, MIME_DOCX)},
        )
        # Validación temprana de magic bytes → 422 con mensaje de cabecera
        assert respuesta.status_code == 422
        assert "cabecera" in respuesta.json()["detail"]
        assert "PK" in respuesta.json()["detail"]

    def test_zip_magic_bytes_truncados(self):
        """Cabecera ZIP incompleta (solo 'PK\\x03') → 422."""
        contenido = b"PK\x03"
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("truncado.docx", contenido, MIME_DOCX)},
        )
        assert respuesta.status_code == 422
        assert "cabecera" in respuesta.json()["detail"]

    def test_mensajes_error_son_descriptivos(self):
        """Todos los mensajes de error deben tener 'detail' con información útil."""
        # Sin archivo → FastAPI devuelve 422 con lista de errores
        r1 = CLIENTE.post("/validar")
        assert r1.status_code == 422
        assert "detail" in r1.json()

        # Tipo no soportado → mensaje en español
        r2 = CLIENTE.post(
            "/validar",
            files={"archivo": ("prueba.txt", b"contenido", "text/plain")},
        )
        assert r2.status_code == 415
        assert isinstance(r2.json()["detail"], str)
        assert len(r2.json()["detail"]) > 0

        # Archivo vacío
        r3 = CLIENTE.post(
            "/validar",
            files={"archivo": ("vacio.docx", b"", MIME_DOCX)},
        )
        assert r3.status_code == 422
        assert isinstance(r3.json()["detail"], str)
        assert len(r3.json()["detail"]) > 0

        # Archivo corrupto → 422 (BadZipFile capturado)
        r4 = CLIENTE.post(
            "/validar",
            files={"archivo": ("corrupto.docx", b"no es zip", MIME_DOCX)},
        )
        assert r4.status_code == 422
        assert isinstance(r4.json()["detail"], str)
        assert len(r4.json()["detail"]) > 0

    def test_error_interno_de_mapeo_responde_500(self, monkeypatch):
        """B6: un bug interno del mapeo a DTO no debe vestirse de 422.

        pydantic.ValidationError es subclase de ValueError. Cuando el
        except ValueError cubría toda la respuesta, un fallo interno
        del mapeo respondía 422 culpando al DOCX del estudiante.
        """

        def dto_roto(r):
            # Construcción inválida a propósito: pydantic lanza ValidationError
            return ResultadoReglaAPI(paso="no-es-bool", severidad="no-existe")

        monkeypatch.setattr(validator.api, "_rule_result_a_dto", dto_roto)
        contenido = build_large_docx(target_bytes=1024)
        respuesta = CLIENTE.post(
            "/validar",
            files={"archivo": ("tesis.docx", contenido, MIME_DOCX)},
        )
        assert respuesta.status_code == 500
        assert "Error interno del validador" in respuesta.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: validación del campo correo (opcional)
# ---------------------------------------------------------------------------


class TestCorreo:
    """Cobertura del campo 'correo' (opcional) de POST /validar."""

    def _docx_payload(self) -> dict:
        """Payload mínimo para tests de validación del campo correo.

        El contenido NO es un DOCX real: solo lleva la firma PK para pasar
        el chequeo de magic bytes. Funciona porque la validación de 'correo'
        ocurre ANTES de procesar el archivo; si ese orden cambia, estos
        tests fallarían por el DOCX falso.
        """
        return {"archivo": ("prueba.docx", b"PK\x03\x04contenido-de-prueba", MIME_DOCX)}

    def test_correo_valido_aceptado(self):
        """Correo válido → la validación de campos no falla con 422 de correo."""
        respuesta = subir_plantilla(data={"correo": "estudiante@unitru.edu.pe"})
        assert respuesta.status_code == 200

    def test_correo_invalido_rechazado(self):
        """Correo sin formato válido → 422 con mensaje en español."""
        respuesta = CLIENTE.post(
            "/validar",
            data={"correo": "no-es-un-correo"},
            files=self._docx_payload(),
        )
        assert respuesta.status_code == 422
        assert "Correo electrónico inválido" in respuesta.json()["detail"]

    def test_correo_ausente_aceptado(self):
        """Campo 'correo' omitido → 200 (retrocompatible, opcional)."""
        respuesta = subir_plantilla()
        assert respuesta.status_code == 200

    def test_correo_vacio_tratado_como_ausente(self):
        """Correo vacío ('') → tratado como ausente, no rechazado."""
        respuesta = subir_plantilla(data={"correo": ""})
        assert respuesta.status_code == 200

    def test_correo_con_espacios_normalizado(self):
        """Correo con espacios alrededor → normalizado y aceptado."""
        respuesta = subir_plantilla(data={"correo": "  estudiante@unitru.edu.pe  "})
        assert respuesta.status_code == 200

    def test_correo_invalido_detectado_antes_de_procesar_archivo(self):
        """Correo inválido con archivo corrupto → falla primero por correo (422)."""
        respuesta = CLIENTE.post(
            "/validar",
            data={"correo": "@@malformed@@"},
            files={"archivo": ("corrupto.docx", b"no es zip", MIME_DOCX)},
        )
        assert respuesta.status_code == 422
        assert "Correo electrónico inválido" in respuesta.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: paridad API = CLI
# ---------------------------------------------------------------------------


class TestParidadAPICLI:
    """Verifica que la respuesta de la API tenga la misma información que el CLI."""

    def test_mismos_campos_que_motor(self):
        """Los campos del motor (RuleResult.to_dict) deben aparecer en la respuesta API."""
        # El motor se compara contra el MISMO YAML que carga la API (F5: DSL)
        # y el MISMO DOCX de prueba (plantilla oficial o factory).
        rules_data = load_rules(REGLAS_YAML_PATH)
        docx = str(ruta_docx_prueba())
        resultados_motor = validate_docx(docx, rules_data)
        reporte = build_report(resultados_motor)

        respuesta = subir_plantilla()
        datos_api = respuesta.json()

        # Mismos counts (los dos nuevos campos)
        assert datos_api["resumen"]["total"] == reporte["resumen"]["total"]
        assert datos_api["resumen"]["total_evaluadas"] == reporte["resumen"]["total_evaluadas"]
        assert (
            datos_api["resumen"]["reglas_no_aplicables"]
            == reporte["resumen"]["reglas_no_aplicables"]
        )
        assert datos_api["resumen"]["fallidos_error"] == reporte["resumen"]["fallidos_error"]
        assert datos_api["resumen"]["fallidos_warning"] == reporte["resumen"]["fallidos_warning"]

        # Mismos semáforo
        assert datos_api["semaforo"] == reporte["semaforo"]

        # Mismos rule_ids
        ids_motor = {r.rule_id for r in resultados_motor}
        ids_api = {r["rule_id"] for r in datos_api["resultados"]}
        assert ids_api == ids_motor

        # Mismos passed values (strict: un desfase de longitud debe fallar,
        # no truncarse silenciosamente)
        for r_motor, r_api in zip(resultados_motor, datos_api["resultados"], strict=True):
            assert r_motor.passed == r_api["paso"], f"Discrepancia en {r_motor.rule_id}"

        # Los nuevos campos de resultado
        for r_motor, r_api in zip(resultados_motor, datos_api["resultados"], strict=True):
            assert r_motor.aplicable == r_api["aplicable"], (
                f"Discrepancia de aplicable en {r_motor.rule_id}"
            )

        # Metadatos de tipo de documento (opcionales)
        metadatos_api = datos_api["metadatos"]
        assert metadatos_api["tipo_documento_declarado"] is None  # plantilla no declara
        assert (
            metadatos_api["tipo_documento_inferido"] == "tinv_cuantitativo"
        )  # infiere cuantitativo
        assert metadatos_api["tipo_documento_estado"] == "vigente"


# ---------------------------------------------------------------------------
# Tests: ficha de depósito (v1.7.0)
# ---------------------------------------------------------------------------


class TestFichaDeposito:
    """v1.7.0: la ficha de depósito SOLO materializa con semáforo verde.

    Invariante del contrato (PLAN_FICHA §3, decisión 14): un documento
    con errores bloqueantes no se deposita, y no hay nada que pre-llenar.
    Los documentos de prueba salen del factory determinista: el doc bueno
    (verde) y el doc bueno con la mutación de `papel_tamano` (regla de
    severidad error → rojo garantizado).
    """

    @staticmethod
    def _subir_cfg(cfg: dict):
        """Compila un DOCX del factory y lo sube a POST /validar."""
        ruta = Path(compilar_docx(cfg))
        with open(ruta, "rb") as f:
            return CLIENTE.post(
                "/validar",
                files={"archivo": ("tesis.docx", f, MIME_DOCX)},
            )

    @staticmethod
    def _subir_doc_bueno():
        return TestFichaDeposito._subir_cfg(configuracion_base())

    @staticmethod
    def _subir_doc_rojo():
        # papel_tamano es severidad error: mutarla garantiza semáforo rojo.
        cfg = aplicar_mutacion("papel_tamano", configuracion_base())
        return TestFichaDeposito._subir_cfg(cfg)

    def test_doc_bueno_es_verde(self):
        """Precondición del invariante: el doc bueno del factory da verde."""
        datos = self._subir_doc_bueno().json()
        assert datos["semaforo"] == "verde"

    def test_doc_mutado_es_rojo(self):
        """Precondición del invariante: la mutación de papel_tamano da rojo."""
        datos = self._subir_doc_rojo().json()
        assert datos["semaforo"] == "rojo"

    def test_ficha_presente_con_todos_los_campos_en_verde(self):
        """VERDE → ficha con los 8 extraídos acordados y los 4 manuales."""
        ficha = self._subir_doc_bueno().json()["ficha_deposito"]
        assert ficha is not None

        extraidos = ficha["extraidos"]
        assert tuple(c["campo"] for c in extraidos) == CAMPOS_EXTRAIDOS_FICHA
        for c in extraidos:
            assert set(c.keys()) == {"campo", "valor", "pagina", "detectado"}
            assert isinstance(c["detectado"], bool)

        manuales = ficha["manuales"]
        assert tuple(c["campo"] for c in manuales) == CAMPOS_MANUALES_FICHA
        for c in manuales:
            assert set(c.keys()) == {"campo", "valor"}

    def test_ficha_poblada_por_el_motor(self):
        """El motor (diseño 17) entrega los valores reales: detectado=true.

        El doc bueno del factory tiene contenido conocido, así que los
        extraídos llegan completos — salvo `renati.juror`, cuya captura
        quedó como no confiable (el operador lo teclea; ver handover).
        """
        ficha = self._subir_doc_bueno().json()["ficha_deposito"]
        por_campo = {c["campo"]: c for c in ficha["extraidos"]}

        self._assert_extraido(por_campo["dc.title"], True, str)
        assert "Estrategias lúdicas" in por_campo["dc.title"]["valor"]
        self._assert_extraido(por_campo["dc.contributor.author"], True, list)
        assert por_campo["dc.contributor.author"]["valor"] == ["Ana María Pérez García"]
        self._assert_extraido(por_campo["dc.contributor.advisor"], True, str)
        self._assert_extraido(por_campo["dc.description.abstract"], True, str)
        self._assert_extraido(por_campo["dc.subject"], True, list)
        assert por_campo["dc.subject"]["valor"] == ["clave0", "clave1", "clave2"]
        self._assert_extraido(por_campo["dc.date.issued"], True, str)
        assert por_campo["dc.date.issued"]["valor"] == "2026"
        self._assert_extraido(por_campo["escuela"], True, str)
        # Jurado: captura no confiable según el handover → sin dato.
        self._assert_extraido(por_campo["renati.juror"], False, type(None))

    @staticmethod
    def _assert_extraido(campo, detectado, tipo_valor):
        assert campo["detectado"] is detectado, campo["campo"]
        assert isinstance(campo["valor"], tipo_valor), campo["campo"]
        if detectado:
            assert campo["pagina"] is None or isinstance(campo["pagina"], int)
        if not detectado:
            assert campo["valor"] is None, campo["campo"]

    def test_ficha_vacia_cuando_el_motor_no_publica(self):
        """Despliegue sin ruleset de ficha: todos los campos en detectado=false.

        La forma del contrato es estable aunque falte la captura (un
        despliegue sin reglas_ficha.yaml sigue respondiendo la ficha
        completa, solo que sin datos).
        """
        from validator.api import CAMPOS_EXTRAIDOS_FICHA, _ficha_desde_reporte

        ficha = _ficha_desde_reporte({"ficha": {}})
        assert all(c.detectado is False for c in ficha.extraidos)
        assert tuple(c.campo for c in ficha.extraidos) == CAMPOS_EXTRAIDOS_FICHA

    def test_ficha_manuales_vacios_desde_el_servidor(self):
        """Los manuales viajan null: los llena el operador en pantalla."""
        ficha = self._subir_doc_bueno().json()["ficha_deposito"]
        assert all(c["valor"] is None for c in ficha["manuales"])

    def test_ficha_nula_en_rojo(self):
        """ROJO → ficha_deposito es null: no hay nada que pre-llenar."""
        datos = self._subir_doc_rojo().json()
        assert datos["ficha_deposito"] is None
