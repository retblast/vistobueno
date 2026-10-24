"""API FastAPI para VistoBueno — endpoint POST /validar.

Expone el motor de validación de formato de tesis como servicio HTTP.
Recibe un archivo DOCX, lo procesa contra las reglas de formato de la
UNT, y devuelve un reporte estructurado en JSON.

Uso:
    python -m validator.api
    # o con uvicorn directamente:
    uvicorn validator.api:app --reload
"""

import os
import re
import tempfile
import zipfile
from functools import cache
from pathlib import Path
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from fastapi import FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from .api_models import (
    CampoExtraidoFicha,
    CampoManualFicha,
    ConstanciaRequest,
    DepositoAPI,
    DepositoRecibido,
    EstadoDepositoAPI,
    EstadoNotificacionAPI,
    FichaDeposito,
    FilaRegistroRequest,
    FilasRegistroResponse,
    MetadatosValidacion,
    NotificacionAPI,
    PromptIA,
    ResultadoReglaAPI,
    ResumenValidacion,
    SeveridadAPI,
    ValidarResponse,
)
from .buzon import Buzon
from .constancia import (
    MIME_DOCX as MIME_DOCX_CONSTANCIA,
)
from .constancia import (
    DatosConstancia,
    ErrorConfiguracionConstancia,
    ErrorDatosConstancia,
    _nombre_seguro,
    constancia_en_zip,
    constancias_por_autor,
    filas_a_csv,
    filas_a_tsv,
    filas_a_xlsx,
    llenar_constancia,
)
from .dsl_check import DSLValidationError
from .dspace import ConfigDSpace, depositar_documento, metadatos_desde_formulario
from .engine import build_report, load_ficha_rules, load_rules, validate_docx
from .models import RuleResult
from .notificacion import ConfigSMTP, enviar_notificacion
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

# Claves acordadas de la ficha de depósito (v1.7.0, PLAN_FICHA §4).
# Los extraídos los publica el motor en reporte["ficha"] (handover
# HANDOVER_MOTOR_FICHA_DEPOSITO §4); los manuales los teclea el operador.
CAMPOS_EXTRAIDOS_FICHA = (
    "dc.title",
    "dc.contributor.author",
    "dc.contributor.advisor",
    "dc.description.abstract",
    "dc.subject",
    "dc.date.issued",
    "escuela",
    "renati.juror",
)
CAMPOS_MANUALES_FICHA = (
    "matricula",
    "renati.author.dni",
    "renati.advisor.dni",
    "renati.advisor.orcid",
)


@cache
def _get_rules() -> dict:
    """Carga el YAML de reglas una sola vez (cacheado en memoria)."""
    return load_rules(REGLAS_YAML_PATH)


@cache
def _get_ficha_rules() -> dict:
    """Carga el ruleset de captura de la ficha (diseño 17), una sola vez.

    Devuelve ``{}`` si el archivo no existe (despliegue sin ficha): la
    respuesta sigue trayendo los campos acordados con ``detectado=false``.
    """
    return load_ficha_rules()


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
        aplicable=r.aplicable,
    )


def _extraer_metadata_tipo_documento(
    resultados_motor: list[RuleResult],
) -> dict:
    """Extrae los campos opcionales de tipo de documento de la detección.

    La regla `deteccion_tipo_documento` siempre se ejecuta; su `encontrado`
    contiene la decisión como texto. Se parsea para publicar:

    - `tipo_documento_declarado`: lo que dice el Anexo 10 (None si no declaró).
    - `tipo_documento_inferido`: lo que se dedujo de las firmas (None si no se
      pudo inferir).
    - `tipo_documento_estado`: "vigente" si se determinó un tipo,
      "sin_determinar" si no se pudo, "contradictorio" si el Anexo 10 y las
      firmas no coinciden.

    El parseo es determinista sobre el texto que genera el motor mismo, por
    lo que no hay riesgo de desalineación.
    """
    detector = next((r for r in resultados_motor if r.rule_id == "deteccion_tipo_documento"), None)
    if detector is None or not detector.found:
        return {
            "tipo_documento_declarado": None,
            "tipo_documento_inferido": None,
            "tipo_documento_estado": "sin_determinar",
        }

    encontrado = detector.found
    declarado = re.search(r"declarado=([a-z_]+)", encontrado)
    inferido = re.search(r"inferido=([a-z_]+)", encontrado)
    contradice = "contradictorio:" in encontrado
    sin_determinar = encontrado.startswith("sin_determinado")

    if contradice:
        estado = "contradictorio"
    elif sin_determinar:
        estado = "sin_determinar"
    else:
        estado = "vigente"

    # declarado e inferido son Optional[Match[str]]; en contradice ambos existen
    declarado_val = declarado.group(1) if declarado else None
    inferido_val = inferido.group(1) if inferido else None

    return {
        "tipo_documento_declarado": declarado_val,
        "tipo_documento_inferido": inferido_val,
        "tipo_documento_estado": estado,
    }


def _ficha_desde_reporte(reporte: dict) -> FichaDeposito:
    """Construye la ficha de depósito a partir del reporte del motor.

    El motor publicará las extracciones en `reporte["ficha"]` como un
    dict campo→dato, cada dato con la forma acordada del handover §4:
    `{"valor": …, "pagina": …, "detectado": …}`. Hasta esa entrega, la
    ficha viaja completa pero con todos los extraídos en `detectado=false`:
    el contrato es estable y el frontend puede construirse ya.

    Los manuales siempre viajan vacíos desde el servidor: los llena el
    operador en la pantalla.
    """
    datos_motor = reporte.get("ficha") or {}
    extraidos = []
    for campo in CAMPOS_EXTRAIDOS_FICHA:
        dato = datos_motor.get(campo) or {}
        extraidos.append(
            CampoExtraidoFicha(
                campo=campo,
                valor=dato.get("valor"),
                pagina=dato.get("pagina"),
                detectado=bool(dato.get("detectado")),
            )
        )
    manuales = [CampoManualFicha(campo=c, valor=None) for c in CAMPOS_MANUALES_FICHA]
    return FichaDeposito(extraidos=extraidos, manuales=manuales)


def _construir_respuesta(
    resultados_motor: list,
    reporte: dict,
    prompts_data: list,
    archivo_nombre: str,
    archivo_tamano: int,
    rules_data: dict,
) -> ValidarResponse:
    """Ensambla la respuesta completa de la API a partir de la salida del motor."""
    resultados_dto = [
        _rule_result_a_dto(r)
        for r in resultados_motor
        # Las reglas de CAPTURA (diseño 17) no son reglas de validación:
        # no viajan en `resultados`; sus datos van en `ficha_deposito`.
        if not r.captura
    ]
    resumen_motor = reporte["resumen"]

    # La ficha solo materializa con semáforo verde (invariante del
    # contrato v1.7.0): un documento con errores bloqueantes no se
    # deposita, y no hay nada que pre-llenar.
    ficha = _ficha_desde_reporte(reporte) if reporte["semaforo"] == "verde" else None

    return ValidarResponse(
        semaforo=reporte["semaforo"],
        resumen=ResumenValidacion(
            total=resumen_motor["total"],
            total_evaluadas=resumen_motor["total_evaluadas"],
            reglas_no_aplicables=resumen_motor["reglas_no_aplicables"],
            fallidos_error=resumen_motor["fallidos_error"],
            fallidos_warning=resumen_motor["fallidos_warning"],
        ),
        resultados=resultados_dto,
        como_preguntar_a_una_ia=[
            PromptIA(rule_id=p["rule_id"], prompt=p["prompt"]) for p in prompts_data
        ],
        metadatos=MetadatosValidacion(
            archivo_nombre=archivo_nombre,
            archivo_tamano_bytes=archivo_tamano,
            reglas_evaluadas=resumen_motor["total_evaluadas"],
            reglas_totales=resumen_motor["total"],
            version_esquema=rules_data.get("version", "desconocido"),
            **_extraer_metadata_tipo_documento(resultados_motor),
        ),
        ficha_deposito=ficha,
    )


def _validar_correo(correo: str | None) -> str | None:
    """Valida el correo electrónico del estudiante (campo opcional).

    - `None` o cadena vacía → `None` (el frontend puede omitirlo o enviar "").
    - Si se envía, debe tener formato de correo válido; si no, lanza 422
      con mensaje descriptivo en español.

    El valor normalizado retornado es el destinatario de la notificación de
    observaciones (Actividad 6): se envía un correo cuando el semáforo es
    "rojo", la notificación está habilitada y el servidor SMTP acepta el envío.
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
    version="1.7.0",
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
            "Destinatario de las observaciones cuando se solicita el envío "
            "(campo `notificar`)."
        ),
        # Swagger prellenaba "string" y un Execute sin editar enviaba
        # basura; con ejemplo vacío el campo se deja en blanco solo
        # (revisión del PR #55, hallazgo 2).
        examples=[""],
    ),
    notificar: bool = Form(
        default=False,
        description=(
            "Solicitar el envío del correo de observaciones al estudiante "
            "(opt-in del operador). Solo aplica con semáforo rojo y un "
            "`correo` válido."
        ),
    ),
    depositar: bool = Form(
        default=False,
        description=(
            "Solicitar el depósito del documento en el repositorio "
            "institucional DSpace (opt-in del operador, actividad 10). "
            "Solo aplica con semáforo verde."
        ),
    ),
    titulo: str | None = Form(
        default=None,
        description="Título del trabajo: metadato dc.title del depósito (opcional)",
        examples=[""],
    ),
    autores: str | None = Form(
        default=None,
        description=(
            "Autor(es), separados por ';' o saltos de línea: metadato "
            "dc.contributor.author del depósito (opcional)"
        ),
        examples=[""],
    ),
    asesor: str | None = Form(
        default=None,
        description="Asesor(a): metadato dc.contributor.advisor del depósito (opcional)",
        examples=[""],
    ),
    resumen: str | None = Form(
        default=None,
        description="Resumen: metadato dc.description.abstract del depósito (opcional)",
        examples=[""],
    ),
    palabras_clave: str | None = Form(
        default=None,
        description=(
            "Palabras clave, separadas por ';' o ',': metadato dc.subject del depósito (opcional)"
        ),
        examples=[""],
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
    correo_normalizado = _validar_correo(correo)

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

        # El escaneo del DOCX es lo ÚNICO cuyos errores significan "el
        # archivo del usuario está mal". El 422 se acota a esta llamada
        # (hallazgo B6): pydantic.ValidationError es subclase de ValueError,
        # así que un bug interno del mapeo a DTO o del motor respondía 422
        # culpando al documento del estudiante. Ahora esos caen al 500
        # genérico del bloque exterior.
        # El motor es síncrono y CPU-intenso (recompila el DSL en cada
        # request): se despacha al threadpool para no congelar el event
        # loop mientras dura la validación. Se pasa el ruleset de captura
        # de la ficha (diseño 17) en la MISMA pasada: sus capturas viajan
        # en reporte["ficha"] y no afectan semáforo ni resumen.
        try:
            resultados_motor = await run_in_threadpool(
                validate_docx, tmp_path, rules_data, _get_ficha_rules()
            )
        except DSLValidationError as e:
            # Reglas rotas = error de configuración del servidor, no del
            # documento del estudiante.
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del validador: configuración de reglas inválida: {e}",
            ) from e
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

        reporte = build_report(resultados_motor)

        # Prompts de IA (solo si se solicitan)
        prompts_data = []
        if incluir_prompts_ia:
            fallidos = [r for r in resultados_motor if not r.passed]
            prompts_data = build_ai_help_section(fallidos)

        respuesta = _construir_respuesta(
            resultados_motor=resultados_motor,
            reporte=reporte,
            prompts_data=prompts_data,
            archivo_nombre=archivo.filename,
            archivo_tamano=tamano,
            rules_data=rules_data,
        )

        # --- Notificación de observaciones (Actividad 6, best-effort) ---
        # El estado se expone al personal del repositorio (herramienta de
        # uso interno): "enviado" permite informar "enviamos las observaciones
        # al correo del estudiante"; "fallo" incluye el motivo técnico.
        # El envío es opt-in por solicitud (`notificar`): el operador decide
        # cuándo el reporte está listo para llegarle al estudiante. Se exige
        # además semáforo "rojo" y un `correo` válido, y el servidor debe
        # tener la notificación habilitada. enviar_notificacion() NUNCA
        # lanza: un fallo de SMTP no debe romper la respuesta HTTP.
        estado = EstadoNotificacionAPI.SIN_CORREO
        detalle: str | None = None
        if correo_normalizado:
            if not notificar:
                estado = EstadoNotificacionAPI.NO_SOLICITADO
            elif respuesta.semaforo != "rojo":
                estado = EstadoNotificacionAPI.SIN_OBSERVACIONES
            else:
                config_smtp = ConfigSMTP.desde_entorno()
                if not config_smtp.enabled:
                    estado = EstadoNotificacionAPI.DESHABILITADO
                    # Nota de configuración para el personal del repositorio
                    # (hallazgo B3): sin esto, "casilla marcada → 200 OK →
                    # nada" era indistinguible de un envío silencioso. El
                    # detalle indica cómo habilitar el servidor.
                    detalle = (
                        "El servidor no tiene la notificación habilitada: "
                        "configure VISTOBUENO_NOTIFICACIONES=1 y VISTOBUENO_SMTP_HOST."
                    )
                else:
                    # smtplib es bloqueante (timeout de hasta 10 s): fuera
                    # del event loop, o un SMTP caído congela toda la API.
                    resultado_envio = await run_in_threadpool(
                        enviar_notificacion,
                        respuesta,
                        correo_normalizado,
                        config=config_smtp,
                    )
                    if resultado_envio.enviado:
                        estado = EstadoNotificacionAPI.ENVIADO
                    else:
                        estado = EstadoNotificacionAPI.FALLO
                        detalle = resultado_envio.detalle
        respuesta.notificacion = NotificacionAPI(estado=estado, detalle=detalle)

        # --- Depósito en DSpace (Actividad 10, best-effort) ---
        # Misma mecánica que la notificación: opt-in del operador
        # (`depositar`), pero SOLO con semáforo "verde" (documento apto
        # para el repositorio). El ítem queda en la cola de aprobación de
        # la sede (workflow de DSpace), nunca se publica directo.
        # depositar_documento() NUNCA lanza: un fallo de DSpace no debe
        # romper la respuesta HTTP.
        estado_dep = EstadoDepositoAPI.SIN_SOLICITUD
        detalle_dep: str | None = None
        if depositar:
            if respuesta.semaforo != "verde":
                estado_dep = EstadoDepositoAPI.NO_APTO
                detalle_dep = "solo se depositan documentos con semáforo verde"
            else:
                config_dspace = ConfigDSpace.desde_entorno()
                if not config_dspace.enabled:
                    estado_dep = EstadoDepositoAPI.DESHABILITADO
                    # Nota de configuración para el personal del repositorio
                    # (mismo criterio que el hallazgo B3 de la notificación):
                    # la respuesta indica exactamente qué falta configurar.
                    detalle_dep = (
                        "El servidor no tiene el depósito habilitado: configure "
                        "VISTOBUENO_DSPACE=1 y " + ", ".join(config_dspace.faltantes) + "."
                    )
                else:
                    metadatos_dep = metadatos_desde_formulario(
                        titulo=titulo,
                        autores=autores,
                        asesor=asesor,
                        resumen=resumen,
                        palabras_clave=palabras_clave,
                    )
                    # httpx es bloqueante (timeout por solicitud): fuera del
                    # event loop, o un DSpace caído congela toda la API.
                    resultado_dep = await run_in_threadpool(
                        depositar_documento,
                        tmp_path,
                        metadatos_dep,
                        config_dspace,
                    )
                    if resultado_dep.enviado:
                        estado_dep = EstadoDepositoAPI.ENVIADO
                    else:
                        estado_dep = EstadoDepositoAPI.FALLO
                    detalle_dep = resultado_dep.detalle
        respuesta.deposito = DepositoAPI(estado=estado_dep, detalle=detalle_dep)

        return respuesta

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del validador: {type(e).__name__}: {e}",
        ) from e
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Buzón de una ranura: comunicación con el userscript de depósito
# ---------------------------------------------------------------------------

# Instancia única del buzón (una ranura de ficha + una de depósito, TTL 1h).
# Es la única pieza de estado del servidor: ver docs/PLAN_FICHA_DEPOSITO.md §6.
_BUZON = Buzon()


@app.post(
    "/ficha-pendiente",
    status_code=204,
    summary="Publicar la ficha completada en el buzón",
    description=(
        "La SPA publica la ficha (extraídos + manuales) para que el "
        "userscript de depósito la lea desde el navegador del operador. "
        "El buzón tiene UNA ranura con TTL de 1 hora: publicar de nuevo "
        "reemplaza la ficha anterior ('última gana')."
    ),
)
async def publicar_ficha_pendiente(ficha: FichaDeposito) -> None:
    _BUZON.publicar_ficha(ficha.model_dump())


@app.get(
    "/ficha-pendiente",
    response_model=FichaDeposito,
    summary="Leer la ficha pendiente del buzón",
    description=(
        "El userscript lee aquí la ficha a rellenar en el formulario "
        "oficial de DSpace. 404 cuando no hay ficha o la publicada "
        "expiró (TTL de 1 hora)."
    ),
    responses={404: {"description": "Sin ficha pendiente: vacía o expirada"}},
)
async def leer_ficha_pendiente() -> FichaDeposito:
    ficha = _BUZON.leer_ficha()
    if ficha is None:
        raise HTTPException(
            status_code=404,
            detail="Sin ficha pendiente: vacía o expirada (TTL de 1 hora).",
        )
    return FichaDeposito(**ficha)


@app.post(
    "/deposito",
    status_code=204,
    summary="Reportar un depósito realizado",
    description=(
        "El userscript reporta el depósito desde la página del ítem "
        "archivado: handle del ítem, título y el timestamp del clic en "
        "Depositar. La SPA lo recoge sondeando GET /deposito y arma la "
        "constancia y la fila del registro."
    ),
)
async def reportar_deposito(datos: DepositoRecibido) -> None:
    _BUZON.reportar_deposito(datos.model_dump())


@app.get(
    "/deposito",
    response_model=DepositoRecibido,
    summary="Leer el depósito reportado",
    description=(
        "La SPA sondea aquí mientras espera el handle del ítem. 404 "
        "cuando no hay reporte o expiró (TTL de 1 hora). Por seguridad, "
        "la SPA debe cotejar el `titulo` reportado con la ficha en vuelo "
        "antes de usar el handle."
    ),
    responses={404: {"description": "Sin depósito reportado: vacío o expirado"}},
)
async def leer_deposito_reportado() -> DepositoRecibido:
    datos = _BUZON.leer_deposito()
    if datos is None:
        raise HTTPException(
            status_code=404,
            detail="Sin depósito reportado: vacío o expirado (TTL de 1 hora).",
        )
    return DepositoRecibido(**datos)


# ---------------------------------------------------------------------------
# Constancia de depósito (Modelo B) y fila de registro
# ---------------------------------------------------------------------------

# Plantilla oficial de la constancia. Vive en recursos/ (no versionada:
# es un artefacto institucional). Ruta sobreescribible por entorno.
PLANTILLA_CONSTANCIA_POR_DEFECTO = (
    Path(__file__).resolve().parent.parent / "recursos" / "TESIS DIGITAL MODELO B-2026.docx"
)


def _ruta_plantilla_constancia() -> Path:
    """Ruta de la plantilla del Modelo B (configurable por entorno)."""
    return Path(
        os.environ.get("VISTOBUENO_PLANTILLA_CONSTANCIA", str(PLANTILLA_CONSTANCIA_POR_DEFECTO))
    )


def _firma_operador() -> str:
    """Firma del responsable (columna FIRMA del registro), por entorno."""
    return os.environ.get("VISTOBUENO_FIRMA", "").strip()


def _constancias_de_solicitud(solicitud: FilaRegistroRequest) -> list[DatosConstancia]:
    """Valida la solicitud y arma los datos: una constancia por autor.

    Errores:

    - 422: timestamp que no es ISO 8601, o falta un dato de la ficha
      (título, autores, matrículas alineadas).
    - 500: configuración del servidor (firma o plantilla).
    """
    try:
        momento = _parsear_timestamp(solicitud.timestamp)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Timestamp inválido: '{solicitud.timestamp}'. Use ISO 8601 (p. ej. 2026-10-19T18:10:00).",
        ) from e

    firma = _firma_operador()
    if not firma:
        raise HTTPException(
            status_code=500,
            detail=(
                "El servidor no tiene la firma del responsable configurada: "
                "defina VISTOBUENO_FIRMA (nombre que va en la columna FIRMA del registro)."
            ),
        )

    try:
        return constancias_por_autor(solicitud.ficha.model_dump(), solicitud.handle, momento, firma)
    except ErrorDatosConstancia as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _parsear_timestamp(texto: str):
    """Parsea el timestamp ISO 8601 reportado por el userscript."""
    from datetime import datetime

    return datetime.fromisoformat(texto)


def _nombre_archivo_constancia(datos: DatosConstancia) -> str:
    """Nombre de descarga: 'constancia - {autor sanitizado}.docx'.

    Delega a _nombre_seguro en constancia.py para que el nombre del
    zip y el del docx sean consistentes entre sí.
    """
    return f"constancia - {_nombre_seguro(datos.autor)}.docx"


@app.post(
    "/constancia",
    summary="Descargar la constancia de UN autor (Modelo B lleno, o paquete zip)",
    description=(
        "Genera la constancia de depósito del Modelo B con los MERGEFIELD "
        "reemplazados por los valores de la ficha. Una constancia POR "
        "AUTOR: la SPA descarga una por cada estudiante iterando "
        "`indice_autor`. Devuelve el .docx como descarga binaria. Con "
        "`formato=zip` devuelve en su lugar un paquete con la constancia "
        ".docx y la fila del registro del autor como .csv (hallazgo 11: "
        '"POST /constancia podría incluirlo").'
    ),
    responses={
        200: {"description": "Constancia .docx (o paquete .zip con formato=zip)"},
        422: {
            "description": "Timestamp inválido, falta un dato de la ficha o índice fuera de rango"
        },
        500: {"description": "Firma o plantilla sin configurar en el servidor"},
    },
)
async def descargar_constancia(
    solicitud: ConstanciaRequest,
    formato: Literal["docx", "zip"] = Query(
        default="docx",
        description=(
            "docx: la constancia (retrocompatible). zip: constancia + "
            "registro.csv del autor en un solo paquete (hallazgo 11: "
            "'la constancia podría incluirlo')"
        ),
    ),
) -> Response:
    datos = _constancias_de_solicitud(solicitud)
    if solicitud.indice_autor >= len(datos):
        raise HTTPException(
            status_code=422,
            detail=(
                f"indice_autor={solicitud.indice_autor} fuera de rango: "
                f"la ficha trae {len(datos)} autor(es)."
            ),
        )
    objetivo = datos[solicitud.indice_autor]
    try:
        if formato == "zip":
            return Response(
                content=constancia_en_zip(_ruta_plantilla_constancia(), objetivo),
                media_type="application/zip",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{_nombre_archivo_constancia(objetivo)}.zip"'
                    )
                },
            )
        contenido = llenar_constancia(_ruta_plantilla_constancia(), objetivo)
    except ErrorConfiguracionConstancia as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return Response(
        content=contenido,
        media_type=MIME_DOCX_CONSTANCIA,
        headers={
            "Content-Disposition": f'attachment; filename="{_nombre_archivo_constancia(objetivo)}"'
        },
    )


@app.post(
    "/fila-registro",
    response_model=FilasRegistroResponse,
    summary="Generar las filas del registro (TSV, una por autor)",
    description=(
        "Devuelve las filas listas para pegar en el registro oficial de la "
        "biblioteca (XLSX): una por autor, en el orden exacto de columnas. "
        "La app JAMÁS escribe el registro oficial: el operador pega la fila. "
        "Con `formato` en `tsv`, `csv` o `xlsx` devuelve en su lugar un "
        "ARCHIVO descargable listo para abrir en Excel/LibreOffice "
        "(hallazgo 11 de la revisión del PR #55): elimina los errores de "
        "pegado (encoding, tabs perdidos, columnas desalineadas)."
    ),
    responses={
        200: {"description": "Lista de filas TSV (json) o archivo descargable (tsv/csv/xlsx)"},
        422: {"description": "Timestamp inválido, falta un dato de la ficha o formato desconocido"},
        500: {"description": "Firma sin configurar en el servidor"},
    },
)
async def generar_fila_registro(
    solicitud: FilaRegistroRequest,
    formato: Literal["json", "tsv", "csv", "xlsx"] = Query(
        default="json",
        description="json: la lista TSV (retrocompatible). tsv/csv/xlsx: archivo descargable",
    ),
):
    datos = _constancias_de_solicitud(solicitud)
    filas = [d.fila_registro() for d in datos]

    if formato == "json":
        return FilasRegistroResponse(filas=filas)

    if formato == "tsv":
        return Response(
            content=filas_a_tsv(filas).encode("utf-8"),
            media_type="text/tab-separated-values; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="registro_vistobueno.tsv"'},
        )
    if formato == "csv":
        return Response(
            content=filas_a_csv(filas).encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="registro_vistobueno.csv"'},
        )
    # formato == "xlsx"
    return Response(
        content=filas_a_xlsx(filas),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="registro_vistobueno.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Punto de entrada para ejecución directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
