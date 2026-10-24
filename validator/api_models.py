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


class EstadoDepositoAPI(StrEnum):
    """Estado del depósito del documento en DSpace (Actividad 10).

    El depósito es opt-in por solicitud (campo `depositar`) y solo procede
    con semáforo verde: el operador decide que el documento está apto para
    entrar al repositorio institucional. El ítem queda en la cola de
    aprobación de la sede (workflow de DSpace), no se publica directo.
    """

    ENVIADO = "enviado"
    FALLO = "fallo"
    SIN_SOLICITUD = "sin_solicitud"
    NO_APTO = "no_apto"
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


class DepositoAPI(BaseModel):
    """Estado del depósito del documento en DSpace (Actividad 10).

    Misma forma que NotificacionAPI: `estado` describe qué pasó con el
    depósito para que el operador pueda informar al estudiante o reintentar.
    Con "enviado", el `detalle` recuerda que el ítem queda en la cola de
    aprobación de la sede; con "fallo" o "deshabilitado", el `detalle`
    trae el motivo técnico o la nota de configuración.
    """

    estado: EstadoDepositoAPI = Field(..., description="Veredicto del depósito")
    detalle: str | None = Field(
        default=None,
        description=(
            "Nota de seguimiento cuando se depositó (cola de aprobación); "
            "motivo técnico cuando falló; nota de configuración cuando el "
            "servidor está deshabilitado; None en el resto de casos"
        ),
    )


class CampoExtraidoFicha(BaseModel):
    """Valor extraído del DOCX por el motor (ficha de depósito, v1.7.0).

    Hasta que el motor publique sus extracciones (handover
    HANDOVER_MOTOR_FICHA_DEPOSITO), todos los campos extraídos viajan con
    `detectado=false` y `valor=null`; la forma del contrato es estable.
    """

    campo: str = Field(..., description="Clave acordada (dc.title, escuela, …)")
    valor: str | list[str] | None = Field(
        default=None,
        description="Texto completo o lista de textos (autores, palabras clave); None si no detectado",
    )
    pagina: int | None = Field(
        default=None, description="Página de origen en el DOCX, si el motor la conoce"
    )
    detectado: bool = Field(default=False, description="True si el motor encontró el elemento")


class CampoManualFicha(BaseModel):
    """Campo que el operador teclea en la pantalla de ficha (v1.7.0).

    Matrícula, DNI del autor/asesor y ORCID no salen del DOCX: el
    operador los escribe UNA vez aquí y fluyen al formulario de DSpace
    (vía userscript), a la constancia y a la fila del registro.
    """

    campo: str = Field(..., description="Clave acordada (matricula, renati.author.dni, …)")
    valor: str | list[str] | None = Field(
        default=None,
        description=(
            "Valor tecleado por el operador; None hasta que lo llene. "
            "`matricula` y `renati.author.dni` aceptan una LISTA alineada "
            "por posición con los autores (una por estudiante): las tesis "
            "con dos autores generan dos constancias y dos filas"
        ),
    )


class FichaDeposito(BaseModel):
    """Ficha de depósito: valores detectados + campos manuales (v1.7.0).

    La SPA la recibe en la respuesta de POST /validar (solo con semáforo
    verde), el operador la corrige y completa, y viaja intacta por el
    buzón hasta el userscript que rellena el formulario oficial.
    """

    extraidos: list[CampoExtraidoFicha] = Field(
        ...,
        description="Valores extraídos del DOCX por el motor (título, autores, asesor, resumen, palabras clave, año, escuela, jurado)",
    )
    manuales: list[CampoManualFicha] = Field(
        ...,
        description="Campos que el operador teclea (matrícula, DNI del autor, DNI del asesor, ORCID del asesor)",
    )


class DepositoRecibido(BaseModel):
    """Depósito reportado por el userscript desde la página del ítem (v1.7.0).

    El userscript detecta el handle del ítem archivado y lo reporta al
    buzón; la SPA lo recoge sondeando GET /deposito y arma la constancia
    y la fila del registro. El `titulo` permite a la SPA confirmar que
    el handle corresponde a la ficha en vuelo (por seguridad, la
    coincidencia se verifica contra el título de la ficha preparada).
    """

    handle: str = Field(..., description="URI del ítem (https://hdl.handle.net/…)")
    titulo: str | None = Field(
        default=None,
        description="Título de la tesis depositada; la SPA lo coteja con la ficha en vuelo",
    )
    timestamp: str = Field(
        ...,
        description="Momento del clic en Depositar (ISO 8601), capturado por el userscript",
    )


class FilaRegistroRequest(BaseModel):
    """Solicitud de la fila de registro (v1.7.0).

    La SPA la envía cuando el buzón reporta el depósito (handle +
    timestamp del clic en Depositar). El timestamp alimenta DD/MM/AA,
    HORA, AÑO y la fecha del documento, igual que en el registro
    oficial de la biblioteca.
    """

    ficha: FichaDeposito = Field(
        ...,
        description="La ficha completada por el operador (extraídos corregidos + manuales llenos)",
    )
    handle: str = Field(..., description="URI del ítem depositado (https://hdl.handle.net/…)")
    timestamp: str = Field(
        ...,
        description="Momento del clic en Depositar (ISO 8601), reportado por el userscript",
    )


class ConstanciaRequest(FilaRegistroRequest):
    """Solicitud de UNA constancia (Modelo B) en particular (v1.7.0).

    Una constancia por autor: la SPA descarga una por cada estudiante,
    iterando `indice_autor` sobre la lista de autores de la ficha.
    """

    indice_autor: int = Field(
        default=0,
        ge=0,
        description="Índice (0-based) del autor cuya constancia se descarga",
    )


class FilasRegistroResponse(BaseModel):
    """Filas TSV listas para pegar en el registro oficial (v1.7.0).

    Una fila por autor, en el orden exacto de columnas del registro
    (N°, TESIS/TSP, BACHILLER/LICENCIADO, N° MATRIC., DD, MM, AA, HORA,
    DIRECCION URL, FIRMA, FECHA DEL DOC., ESCUELAS, AÑO). La columna N°
    va vacía: la numeración es del registro de la biblioteca.
    """

    filas: list[str] = Field(
        ..., description="Filas TSV (una por autor) con los valores separados por tabuladores"
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
    deposito: DepositoAPI = Field(
        default_factory=lambda: DepositoAPI(estado=EstadoDepositoAPI.SIN_SOLICITUD),
        description=(
            "Estado del depósito del documento en el repositorio "
            "institucional DSpace (actividad 10). Opt-in del operador "
            "(campo `depositar`): solo se intenta con semáforo verde y "
            "configuración completa en el servidor. El ítem queda en la "
            "cola de aprobación de la sede, no se publica directo."
        ),
    )
    ficha_deposito: FichaDeposito | None = Field(
        default=None,
        description=(
            "Ficha de depósito detectada (v1.7.0). SOLO materializa con "
            'semáforo "verde": en cualquier otro caso es null. Contiene los '
            "valores extraídos del DOCX (listos para que el operador los "
            "corrija) y los campos manuales que el operador debe llenar "
            "(matrícula, DNI, ORCID)."
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
                    "deposito": {"estado": "sin_solicitud", "detalle": None},
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
