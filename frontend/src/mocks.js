// Datos mock que imitan la respuesta del backend (build_report).
// Se usan cuando el backend no está disponible (modo demo, siempre avisado).
// Campos alineados al contrato v1.5 (api_models.py: ValidarResponse):
//  - resultados[].aplicable (v1.5): una regla no aplicable trae paso=true
//    (no falló: no se evaluó) y aplicable=false; el reporte la excluye.
//  - resumen.total_evaluadas / reglas_no_aplicables (v1.5).
//  - metadatos (v1.5): archivo, versión del esquema y tipo de documento.
// El resumen se CALCULA de la lista: los números siempre cuadran con lo
// mostrado (evita KPIs incoherentes en la demo).
const MOCK_RESULTADOS = [
  { rule_id: 'papel_tamano', paso: true, severidad: 'error', aplicable: true, mensaje: 'El tamaño del papel debe ser A4', esperado: '210 x 297 mm', encontrado: 'cumple' },
  { rule_id: 'fuente_principal', paso: true, severidad: 'error', aplicable: true, mensaje: 'La fuente del cuerpo debe ser Times New Roman', esperado: 'Times New Roman', encontrado: 'cumple' },
  { rule_id: 'tamano_cuerpo', paso: true, severidad: 'error', aplicable: true, mensaje: 'El tamaño de letra del cuerpo debe ser 12pt', esperado: '12pt', encontrado: 'cumple' },
  { rule_id: 'interlineado', paso: true, severidad: 'error', aplicable: true, mensaje: 'El interlineado del cuerpo debe ser 1.5', esperado: '1.5 líneas', encontrado: 'cumple' },
  { rule_id: 'margen_superior', paso: true, severidad: 'error', aplicable: true, mensaje: 'El margen superior debe ser 2.5 cm', esperado: '2.5 cm', encontrado: 'cumple' },
  { rule_id: 'margen_izquierdo', paso: true, severidad: 'error', aplicable: true, mensaje: 'El margen izquierdo debe ser 3 cm', esperado: '3 cm', encontrado: 'cumple' },
  { rule_id: 'margen_derecho', paso: false, severidad: 'warning', aplicable: true, mensaje: 'El margen derecho debe ser 2.5 cm', esperado: '2.5 cm', encontrado: '2.5 cm aprox. (plantillas usan 708/709)', ubicacion: 'Manual UNT, sección márgenes' },
  { rule_id: 'sangria_parrafo', paso: false, severidad: 'warning', aplicable: true, mensaje: 'La sangría de primera línea debe ser 1.27 cm', esperado: '1.27 cm', encontrado: '1.25 cm (708 twips)', ubicacion: 'Manual UNT, sección sangrías' },
  { rule_id: 'numeracion_cuerpo_arabigo', paso: true, severidad: 'error', aplicable: true, mensaje: 'El cuerpo debe numerarse con arábigos desde la introducción', esperado: 'arábigos', encontrado: 'cumple' },
  { rule_id: 'numeracion_preliminares_romano', paso: false, severidad: 'error', aplicable: true, mensaje: 'Los preliminares deben numerarse en romanos', esperado: 'romanos (i, ii, iii...)', encontrado: 'arábigos en preliminares', ubicacion: 'Manual UNT, sección numeración' },
  { rule_id: 'caratula_universidad_negrita_mayusculas', paso: true, severidad: 'error', aplicable: true, mensaje: 'El nombre de la universidad debe ir en negrita y mayúsculas', esperado: 'negrita + MAYÚS', encontrado: 'cumple' },
  { rule_id: 'caratula_titulo_negrita_mixta', paso: false, severidad: 'error', aplicable: true, mensaje: 'El título del trabajo debe ir en negrita y mixta', esperado: 'negrita + mixta', encontrado: 'todo mayúsculas', ubicacion: 'Manual UNT, sección carátula' },
  { rule_id: 'estructura_tinv_cuantitativo', paso: true, severidad: 'error', aplicable: true, mensaje: 'Se deben incluir las secciones del diseño cuantitativo', esperado: 'secciones obligatorias', encontrado: 'cumple' },
  // No aplicable (contrato v1.5): regla de otro tipo de tesis. paso=true
  // porque no falló — no se evaluó — y aplicable=false la excluye del reporte.
  { rule_id: 'estructura_tinv_cualitativo', paso: true, severidad: 'error', aplicable: false, mensaje: 'Se deben incluir las secciones del diseño cualitativo', esperado: 'secciones obligatorias', encontrado: 'cumple (no evaluada)' },
]

const fallidosDe = (sev) => MOCK_RESULTADOS.filter((r) => !r.paso && r.aplicable !== false && r.severidad === sev).length
const errores = fallidosDe('error')

export const MOCK_REPORT = {
  // Semáforo calculado: rojo solo si hay errores bloqueantes (igual que el backend).
  semaforo: errores > 0 ? 'rojo' : 'verde',
  resumen: {
    total: MOCK_RESULTADOS.length,
    total_evaluadas: MOCK_RESULTADOS.filter((r) => r.aplicable !== false).length,
    reglas_no_aplicables: MOCK_RESULTADOS.filter((r) => r.aplicable === false).length,
    fallidos_error: errores,
    fallidos_warning: fallidosDe('warning'),
  },
  metadatos: {
    archivo_nombre: 'ejemplo-de-tesis.docx',
    archivo_tamano_bytes: 74565,
    reglas_evaluadas: MOCK_RESULTADOS.filter((r) => r.aplicable !== false).length,
    reglas_totales: MOCK_RESULTADOS.length,
    version_esquema: '2026-09-01',
    tipo_documento_declarado: null,
    tipo_documento_inferido: null,
    tipo_documento_estado: 'sin_determinar',
  },
  // Campo aditivo v1.3.0 (Contrato API): estado del envío de observaciones.
  // "enviado" permite demostrar el badge en modo demo; el detalle va en None.
  // Demo: nada se envió de verdad; no_solicitado ofrece la casilla (badge azul) sin mentir.
  notificacion: { estado: 'no_solicitado', detalle: null },
  // Campo aditivo v1.6.0 (Contrato API): depósito en DSpace. El mock es rojo
  // (con errores), así que sin_solicitud no pinta badge: solo con semáforo
  // verde se ofrece la casilla (misma lógica que badgeDeposito).
  deposito: { estado: 'sin_solicitud', detalle: null },
  resultados: MOCK_RESULTADOS,
  como_preguntar_a_una_ia: [
    { rule_id: 'margen_derecho', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: El margen derecho debe ser 2.5 cm\n- Valor esperado según el reglamento: 2.5 cm\n- Lo que encontró el validador: 2.5 cm aprox. (plantillas usan 708/709)\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
    { rule_id: 'sangria_parrafo', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: La sangría de primera línea debe ser 1.27 cm\n- Valor esperado según el reglamento: 1.27 cm\n- Lo que encontró el validador: 1.25 cm (708 twips)\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
    { rule_id: 'numeracion_preliminares_romano', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: Los preliminares deben numerarse en romanos\n- Valor esperado según el reglamento: romanos (i, ii, iii...)\n- Lo que encontró el validador: arábigos en preliminares\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
    { rule_id: 'caratula_titulo_negrita_mixta', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: El título del trabajo debe ir en negrita y mixta\n- Valor esperado según el reglamento: negrita + mixta\n- Lo que encontró el validador: todo mayúsculas\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
  ],
}
