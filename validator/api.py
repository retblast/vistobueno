"""API FastAPI para VistoBueno — endpoint POST /validar.

Expone el motor de validación de formato de tesis como servicio HTTP.
Recibe un archivo DOCX, lo procesa contra las reglas de formato de la
UNT, y devuelve un reporte estructurado en JSON.

Uso:
    python -m validator.api
    # o con uvicorn directamente:
    uvicorn validator.api:app --reload
"""

import tempfile
import zipfile
from functools import cache
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from .api_models import (
    MetadatosValidacion,
    PromptIA,
    ResultadoReglaAPI,
    ResumenValidacion,
    SeveridadAPI,
    ValidarResponse,
)
from .engine import build_report, load_rules, validate_docx
from .models import RuleResult
from .prompts import build_ai_help_section

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# F5: la API consume el motor DSL (reglas_unt.yaml, 47 reglas) en lugar del
# YAML legacy (unt_format_rules_schema.yaml, 32 mecánicas). Esto activa las
# 9 reglas F3 (resumen_longitud, referencias_minimo_*, anexos_minimos_*,
# caratula_orcid, proyecto_caratula_texto) y las de la F2 (paginación,
# encabezados/pies) dentro de POST /validar.
REGLAS_YAML_PATH = str(Path(__file__).resolve().parent.parent / "reglas_unt.yaml")

TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB

TIPOS_ACEPTADOS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # algunos navegadores envían esto para .docx
}

EXTENSION_ACEPTADA = ".docx"


@cache
def _get_rules() -> dict:
    """Carga el YAML de reglas una sola vez (cacheado en memoria)."""
    return load_rules(REGLAS_YAML_PATH)


# ---------------------------------------------------------------------------
# Mapeo motor interno → DTO API
# ---------------------------------------------------------------------------


def _rule_result_a_dto(r: RuleResult) -> ResultadoReglaAPI:
    """Convierte un RuleResult del motor a un ResultadoReglaAPI (DTO)."""
    return ResultadoReglaAPI(
        rule_id=r.rule_id,
        paso=r.passed,
        severidad=SeveridadAPI(r.severity.value),
        mensaje=r.message,
        esperado=r.expected,
        encontrado=r.found,
        ubicacion=r.location,
        fuente=r.fuente,
        cita=r.cita,
    )


def _construir_respuesta(
    resultados_motor: list,
    reporte: dict,
    prompts_data: list,
    archivo_nombre: str,
    archivo_tamano: int,
    rules_data: dict,
) -> ValidarResponse:
    """Ensambla la respuesta completa de la API a partir de la salida del motor."""
    resultados_dto = [_rule_result_a_dto(r) for r in resultados_motor]

    return ValidarResponse(
        semaforo=reporte["semaforo"],
        resumen=ResumenValidacion(
            total=reporte["resumen"]["total"],
            fallidos_error=reporte["resumen"]["fallidos_error"],
            fallidos_warning=reporte["resumen"]["fallidos_warning"],
        ),
        resultados=resultados_dto,
        como_preguntar_a_una_ia=[
            PromptIA(rule_id=p["rule_id"], prompt=p["prompt"]) for p in prompts_data
        ],
        metadatos=MetadatosValidacion(
            archivo_nombre=archivo_nombre,
            archivo_tamano_bytes=archivo_tamano,
            reglas_evaluadas=reporte["resumen"]["total"],
            version_esquema=rules_data.get("version", "desconocido"),
        ),
    )


def _validar_correo(correo: str | None) -> str | None:
    """Valida el correo electrónico del estudiante (campo opcional).

    - `None` o cadena vacía → `None` (el frontend puede omitirlo o enviar "").
    - Si se envía, debe tener formato de correo válido; si no, lanza 422
      con mensaje descriptivo en español.

    El endpoint descarta el valor retornado por ahora: la normalización
    queda como cimientos para la Actividad 6 (notificación por correo),
    que usará el correo normalizado como destinatario.
    """
    if correo is None:
        return None
    correo_limpio = correo.strip()
    if not correo_limpio:
        return None

    try:
        resultado = validate_email(correo_limpio, check_deliverability=False)
        return resultado.normalized
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Correo electrónico inválido: '{correo_limpio}'. "
                f"Formato esperado: usuario@dominio."
            ),
        ) from e


# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="VistoBueno API",
    description="API de validación automática de formato de tesis — UNT FECyC",
    version="1.2.0",
)


@app.post(
    "/validar",
    response_model=ValidarResponse,
    summary="Validar formato de tesis",
    description=(
        "Recibe un archivo DOCX de tesis y devuelve un reporte de validación "
        "contra las reglas de formato de la Universidad Nacional de Trujillo."
    ),
    responses={
        400: {"description": "Sin archivo en la solicitud"},
        413: {"description": "Archivo excede el tamaño máximo (10 MB)"},
        415: {"description": "Tipo de archivo no soportado"},
        422: {"description": "Archivo corrupto, no es DOCX válido o correo inválido"},
        500: {"description": "Error interno del validador"},
    },
)
async def validar(
    archivo: UploadFile = File(..., description="Archivo .docx a validar"),
    incluir_prompts_ia: bool = Query(
        default=True,
        description="Incluir la sección 'Cómo preguntar a una IA' en la respuesta",
    ),
    correo: str | None = Form(
        default=None,
        description=(
            "Correo electrónico del estudiante (opcional). "
            "Se usará para notificar resultados cuando el envío esté habilitado."
        ),
    ),
):
    # --- Validación: ¿hay archivo? ---
    if archivo.filename is None or archivo.filename == "":
        raise HTTPException(
            status_code=400,
            detail="Campo 'archivo' requerido. Envíe un archivo .docx en el campo 'archivo' del formulario multipart.",
        )

    # --- Validación: extensión ---
    if not archivo.filename.lower().endswith(EXTENSION_ACEPTADA):
        raise HTTPException(
            status_code=415,
            detail=(
                f"Tipo de archivo no soportado: '{archivo.filename}'. "
                f"Solo se aceptan archivos .docx "
                f"({EXTENSION_ACEPTADA})."
            ),
        )

    # --- Validación: content-type (advisory, no definitivo) ---
    content_type = archivo.content_type or ""
    if content_type and content_type not in TIPOS_ACEPTADOS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Content-Type no soportado: '{content_type}'. Solo se aceptan archivos .docx."
            ),
        )

    # --- Validación: correo electrónico (opcional) ---
    _validar_correo(correo)

    # --- Leer contenido (con tope) ---
    # Leer a lo sumo TAMANO_MAXIMO_BYTES + 1: evita cargar en memoria
    # un upload arbitrariamente grande antes de validar el tamaño.
    # Nota: por eso el 413 no reporta el tamaño exacto recibido.
    try:
        contenido = await archivo.read(TAMANO_MAXIMO_BYTES + 1)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail="No se pudo leer el archivo enviado.",
        ) from e

    # --- Validación: tamaño ---
    tamano = len(contenido)
    if tamano > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=("El archivo excede el tamaño máximo permitido (10 MB)."),
        )

    if tamano == 0:
        raise HTTPException(
            status_code=422,
            detail="El archivo está vacío.",
        )

    # --- Validación: magic bytes de un ZIP/DOCX (cabecera PK) ---
    # Un DOCX es un paquete OPC (ZIP). Toda imagen ZIP válida comienza con
    # la firma local 'PK\x03\x04'. Verificarla antes de escribir el temporal
    # permite rechazar rápido archivos renombrados a .docx sin abrirlos.
    if not contenido.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=422,
            detail=(
                "El archivo no es un ZIP/DOCX válido: cabecera incorrecta "
                "(se esperaba la firma 'PK')."
            ),
        )

    # --- Guardar en archivo temporal y procesar ---
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=EXTENSION_ACEPTADA) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name

        rules_data = _get_rules()
        resultados_motor = validate_docx(tmp_path, rules_data)
        reporte = build_report(resultados_motor)

        # Prompts de IA (solo si se solicitan)
        prompts_data = []
        if incluir_prompts_ia:
            fallidos = [r for r in resultados_motor if not r.passed]
            prompts_data = build_ai_help_section(fallidos)

        return _construir_respuesta(
            resultados_motor=resultados_motor,
            reporte=reporte,
            prompts_data=prompts_data,
            archivo_nombre=archivo.filename,
            archivo_tamano=tamano,
            rules_data=rules_data,
        )

    except HTTPException:
        raise
    except zipfile.BadZipFile as e:
        # Archivo no es un ZIP válido (truncado, corrupto, etc.)
        raise HTTPException(
            status_code=422,
            detail=(
                "No se pudo procesar el archivo DOCX: archivo corrupto o no es un DOCX válido."
            ),
        ) from e
    except KeyError as e:
        # El ZIP es válido pero falta word/document.xml (u otra parte
        # esencial del formato DOCX). El extractor lanza KeyError al
        # intentar leer el archivo interno del paquete OPC.
        raise HTTPException(
            status_code=422,
            detail=(
                f"El archivo no contiene un documento Word válido: archivo interno faltante ({e})."
            ),
        ) from e
    except ValueError as e:
        # El extractor no encontró una parte esperada del DOCX
        # (lanzado por ExtractedDocx.xpath cuando una parte no está
        # disponible).
        raise HTTPException(
            status_code=422,
            detail=(f"El archivo no contiene un documento Word válido: {e}."),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del validador: {type(e).__name__}: {e}",
        ) from e
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Punto de entrada para ejecución directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
