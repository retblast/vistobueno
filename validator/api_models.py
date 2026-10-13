"""Modelos Pydantic DTO para la API de validación.

Estos modelos definen el contrato externo de la API. Existen separados
del modelo interno `RuleResult` (dataclass) para:
1. Usar nombres en español en el JSON de respuesta (paso, severidad, mensaje...).
2. Agregar campos que solo existen en la capa API (metadatos).
3. Permitir versionar el contrato sin romper el motor de validación.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class SeveridadAPI(StrEnum):
    """Severidad de una regla de validación."""

    ERROR = "error"
    WARNING = "warning"


class EstadoNotificacionAPI(StrEnum):
    """Estado del envío del correo de observaciones al estudiante.

    La herramienta es de uso interno (personal del repositorio): el estado
    describe qué pasó con el envío para que el operador pueda informar al
    estudiante o reintentar manualmente. El envío es opt-in por solicitud
    (campo `notificar`): el operador decide cuándo el reporte está listo
    para llegarle al estudiante.
    """

    ENVIADO = "enviado"
    FALLO = "fallo"
    SIN_CORREO = "sin_correo"
    NO_SOLICITADO = "no_solicitado"
    SIN_OBSERVACIONES = "sin_observaciones"
    DESHABILITADO = "deshabilitado"


class ResultadoReglaAPI(BaseModel):
    """Resultado de una regla individual en la respuesta de la API.

    Equivalente al `RuleResult` interno del motor, pero con campos
    renombrados a español y en formato snake_case para JSON.
    """

    rule_id: str = Field(..., description="Identificador único de la regla")
    paso: bool = Field(..., description="True si la regla se cumplió")
    severidad: SeveridadAPI = Field(..., description="error o warning")
    mensaje: str = Field(..., description="Descripción de la regla en lenguaje natural")
    esperado: str = Field(default="", description="Valor esperado según el reglamento")
    encontrado: str = Field(default="", description="Lo que encontró el validador")
    ubicacion: str | None = Field(
        default=None, description="Referencia al documento del reglamento"
    )
    fuente: str = Field(default="", description="Archivo fuente del que se extrajo la regla")
    cita: str = Field(default="", description="Cita textual del reglamento")
    aplicable: bool = Field(
        True,
        description="True si la regla se evaluó. False = la regla no aplica a este tipo de documento",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rule_id": "papel_tamano",
                    "paso": True,
                    "severidad": "error",
                    "mensaje": "El tamaño del papel debe ser A4",
                    "esperado": "210 x 297 mm",
                    "encontrado": "cumple",
                    "aplicable": True,
                    "ubicacion": 'Sección "Formato general" (párr. 124-125)',
                    "fuente": "MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx",
                    "cita": '"Tamaño A4/papel (210x297 cm)"',
                },
                {
                    "rule_id": "estructura_tinv_cualitativo",
                    "paso": True,
                    "severidad": "error",
                    "mensaje": "Se deben incluir las secciones del diseño cualitativo",
                    "esperado": "secciones obligatorias del esquema cualitativo",
                    "encontrado": "no aplica a este documento",
                    "aplicable": False,
                    "ubicacion": "Capítulo II — esquemas formales por tipo de título (párr. 75-90)",
                    "fuente": "MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx",
                    "cita": '"Cada título profesional exige un esquema formal distinto"',
                },
            ]
        }
    }


class PromptIA(BaseModel):
    """Bloque 'cómo preguntar a una IA' para una regla fallida.

    Contiene un prompt listo para copiar y pegar en un LLM externo,
    con el contexto de la regla incumplida.
    """

    rule_id: str = Field(..., description="ID de la regla fallida")
    prompt: str = Field(..., description="Prompt completo en español")


class ResumenValidacion(BaseModel):
    """Resumen cuantitativo de la validación."""

    total: int = Field(..., description="Total de reglas presentes en el YAML")
    total_evaluadas: int = Field(..., description="Reglas realmente evaluadas sobre el documento")
    reglas_no_aplicables: int = Field(
        ..., description="Reglas omitidas porque no aplican a este tipo de documento"
    )
    fallidos_error: int = Field(..., description="Reglas con severidad error que no pasaron")
    fallidos_warning: int = Field(..., description="Reglas con severidad warning que no pasaron")


class MetadatosValidacion(BaseModel):
    """Metadatos del procesamiento, agregados por la capa API.

    Estos campos no existen en el motor interno; se agregan aquí
    para dar contexto al frontend sobre el archivo procesado.
    """

    archivo_nombre: str = Field(..., description="Nombre original del archivo subido")
    archivo_tamano_bytes: int = Field(..., description="Tamaño en bytes del archivo")
    reglas_evaluadas: int = Field(..., description="Reglas realmente ejecutadas")
    reglas_totales: int = Field(..., description="Total de reglas presentes en el YAML")
    version_esquema: str = Field(..., description="Versión del esquema YAML de reglas")
    tipo_documento_declarado: str | None = Field(
        None, description="Lo que declara el Anexo 10; None si no declaró"
    )
    tipo_documento_inferido: str | None = Field(
        None, description="Lo que se dedujo de las firmas estructurales; None si no pudo inferirse"
    )
    tipo_documento_estado: str | None = Field(
        None, description="Estado de la detección: vigente, sin_determinar o contradictorio"
    )


class NotificacionAPI(BaseModel):
    """Estado de la notificación por correo de observaciones.

    Exposición para el personal del repositorio: con `estado` "enviado" la
    interfaz puede informar "enviamos las observaciones al correo del
    estudiante"; con "fallo", el `detalle` explica el motivo técnico para
    reintentar o enviar manualmente; con "deshabilitado", el `detalle`
    indica cómo habilitar el servidor (nota de configuración).
    """

    estado: EstadoNotificacionAPI = Field(..., description="Veredicto del envío")
    detalle: str | None = Field(
        default=None,
        description=(
            "Motivo técnico cuando el envío falló; nota de configuración "
            "cuando el servidor está deshabilitado; None en el resto de casos"
        ),
    )


class ValidarResponse(BaseModel):
    """Respuesta completa del endpoint POST /validar.

    Agrupa el semáforo, el resumen, los resultados individuales por regla,
    los prompts de IA y los metadatos del procesamiento.
    """

    semaforo: str = Field(
        ..., description='"verde" si todas las reglas error pasan, "rojo" si alguna falla'
    )
    notificacion: NotificacionAPI = Field(
        default_factory=lambda: NotificacionAPI(estado=EstadoNotificacionAPI.SIN_CORREO),
        description=(
            "Estado del envío del correo de observaciones al estudiante. "
            "El envío es opt-in (campo de formulario `notificar`): solo se "
            "intenta cuando el operador lo solicita, hay observaciones "
            'bloqueantes (semáforo "rojo"), se envió un campo `correo` '
            "válido y la notificación está habilitada en el servidor."
        ),
    )
    resumen: ResumenValidacion = Field(..., description="Resumen cuantitativo")
    resultados: list[ResultadoReglaAPI] = Field(..., description="Resultados por regla")
    como_preguntar_a_una_ia: list[PromptIA] = Field(
        default_factory=list,
        description="Bloques de prompts IA para reglas fallidas",
    )
    metadatos: MetadatosValidacion = Field(..., description="Metadatos del procesamiento")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "semaforo": "verde",
                    "notificacion": {"estado": "sin_correo", "detalle": None},
                    "resumen": {
                        "total": 49,
                        "total_evaluadas": 43,
                        "reglas_no_aplicables": 6,
                        "fallidos_error": 0,
                        "fallidos_warning": 2,
                    },
                    "resultados": [
                        {
                            "rule_id": "papel_tamano",
                            "paso": True,
                            "severidad": "error",
                            "mensaje": "El tamaño del papel debe ser A4",
                            "esperado": "210 x 297 mm",
                            "encontrado": "cumple",
                            "aplicable": True,
                            "ubicacion": 'Sección "Formato general" (párr. 124-125)',
                            "fuente": "MANUAL REVISADO TERCERA VERSION OBSERVACIONES 11-07-2025.docx",
                            "cita": '"Tamaño A4/papel (210x297 cm)"',
                        }
                    ],
                    "como_preguntar_a_una_ia": [],
                    "metadatos": {
                        "archivo_nombre": "mi_tesis.docx",
                        "archivo_tamano_bytes": 123456,
                        "reglas_evaluadas": 43,
                        "reglas_totales": 49,
                        "version_esquema": "2026-09-01",
                        "tipo_documento_declarado": None,
                        "tipo_documento_inferido": None,
                        "tipo_documento_estado": "vigente",
                    },
                }
            ]
        }
    }
