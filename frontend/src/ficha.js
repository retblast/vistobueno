// Lógica de la ficha de depósito (semana 8, contrato v1.7.0).
// Módulo sin React y sin estado: las funciones puras se prueban con vitest
// (`npm test`) y la pantalla (components/FichaDeposito.jsx) las consume.
//
// Reglas del flujo (docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md):
//  - la ficha solo existe con semáforo verde;
//  - `matricula` y `renati.author.dni` son listas alineadas por POSICIÓN con
//    los autores (una entrada por estudiante);
//  - el buzón tiene una sola ranura con TTL de 1 hora ("última gana");
//  - el título reportado por el userscript se coteja contra la ficha en vuelo
//    antes de usar el handle (nunca a ciegas).

export const CAMPO_TITULO = 'dc.title'
export const CAMPO_AUTORES = 'dc.contributor.author'
export const CAMPO_ADVISEOR = 'dc.contributor.advisor'
export const CAMPO_RESUMEN = 'dc.description.abstract'
export const CAMPO_PALABRAS = 'dc.subject'
export const CAMPO_ANIO = 'dc.date.issued'
export const CAMPO_ESCUELA = 'escuela'
export const CAMPO_JURADO = 'renati.juror'
export const CAMPO_MATRICULA = 'matricula'
export const CAMPO_DNI_AUTOR = 'renati.author.dni'
export const CAMPO_DNI_ASESOR = 'renati.advisor.dni'
export const CAMPO_ORCID_ASESOR = 'renati.advisor.orcid'

// Orden y tipo de cada campo en pantalla. `lista` = varios valores (uno por
// línea en el textarea); `lista-autor` = una entrada por autor, alineada por
// posición; `area` = texto largo.
export const CAMPOS_EXTRAIDOS = [
  { campo: CAMPO_TITULO, etiqueta: 'Título', tipo: 'texto' },
  { campo: CAMPO_AUTORES, etiqueta: 'Autores', tipo: 'lista' },
  { campo: CAMPO_ADVISEOR, etiqueta: 'Asesor', tipo: 'texto' },
  { campo: CAMPO_RESUMEN, etiqueta: 'Resumen', tipo: 'area' },
  { campo: CAMPO_PALABRAS, etiqueta: 'Palabras clave', tipo: 'lista' },
  { campo: CAMPO_ANIO, etiqueta: 'Año de emisión', tipo: 'texto' },
  { campo: CAMPO_ESCUELA, etiqueta: 'Escuela', tipo: 'texto' },
  { campo: CAMPO_JURADO, etiqueta: 'Jurado', tipo: 'texto' },
  {
    campo: CAMPO_ORCID_ASESOR,
    etiqueta: 'ORCID del asesor',
    tipo: 'texto',
    aviso:
      'Detectado en la carátula del documento: verifique que sea el ORCID del asesor y no el de un autor.',
    avisoSinDetectar:
      'No se detectó un ORCID válido en el documento: escríbalo a mano.',
  },
]

export const CAMPOS_MANUALES = [
  { campo: CAMPO_MATRICULA, etiqueta: 'Matrícula', tipo: 'lista-autor' },
  { campo: CAMPO_DNI_AUTOR, etiqueta: 'DNI del autor', tipo: 'lista-autor' },
  { campo: CAMPO_DNI_ASESOR, etiqueta: 'DNI del asesor', tipo: 'texto' },
]

// Normaliza para comparar: minúsculas, sin acentos y sin espacios dobles.
export const normalizar = (texto) =>
  String(texto ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()

// Valor de un campo (extraído o manual) de la ficha; null si no existe.
export const valorDe = (ficha, campo) => {
  const lista = Array.isArray(ficha?.extraidos) ? ficha.extraidos : []
  const manual = Array.isArray(ficha?.manuales) ? ficha.manuales : []
  const encontrado = [...lista, ...manual].find((c) => c?.campo === campo)
  return encontrado?.valor ?? null
}

// Sección del catálogo a la que pertenece un campo ('extraidos' o
// 'manuales'). Null si el campo no está en el catálogo.
export const seccionDeCampo = (campo) => {
  if (CAMPOS_EXTRAIDOS.some((f) => f.campo === campo)) return 'extraidos'
  if (CAMPOS_MANUALES.some((f) => f.campo === campo)) return 'manuales'
  return null
}

// Devuelve una ficha nueva con el campo actualizado (no muta la original).
// El valor editado se publica SIEMPRE en la sección del catálogo que le
// corresponde: con el contrato v1.15.0 el ORCID del asesor es un campo
// extraído, así que aunque llegue en `manuales` (contrato anterior) su valor
// editado se publica en `extraidos`.
export const establecerValor = (ficha, campo, valor) => {
  const base = { extraidos: [], manuales: [], ...ficha }
  const seccionCatalogo = seccionDeCampo(campo)
  for (const seccion of ['extraidos', 'manuales']) {
    const items = Array.isArray(base[seccion]) ? base[seccion] : []
    const indice = items.findIndex((c) => c?.campo === campo)
    if (indice < 0) continue
    const actual = { ...items[indice], valor }
    if (seccionCatalogo && seccionCatalogo !== seccion) {
      // El campo cambió de sección (p. ej. el ORCID): se traslada con su valor.
      const otras = items.filter((c) => c?.campo !== campo)
      const destino = { ...base, [seccionCatalogo]: [...(base[seccionCatalogo] || []), actual] }
      destino[seccion] = otras
      return destino
    }
    return { ...base, [seccion]: items.map((c, i) => (i === indice ? actual : c)) }
  }
  // El servidor puede no traer un campo (ficha sin ese dato): se agrega en la
  // sección que le toca según el catálogo.
  const seccion = seccionCatalogo ?? 'manuales'
  return { ...base, [seccion]: [...(base[seccion] || []), { campo, valor }] }
}

// Autores detectados: lista (o texto con saltos de línea) → arreglo limpio.
export const autoresDe = (ficha) => {
  const valor = valorDe(ficha, CAMPO_AUTORES)
  if (Array.isArray(valor)) return valor.map((v) => String(v ?? '').trim()).filter(Boolean)
  if (typeof valor === 'string') {
    return valor
      .split(/[\n;]+/)
      .map((v) => v.trim())
      .filter(Boolean)
  }
  return []
}

export const tituloDe = (ficha) => {
  const valor = valorDe(ficha, CAMPO_TITULO)
  if (Array.isArray(valor)) return valor.map((v) => String(v ?? '').trim()).filter(Boolean).join('; ')
  return typeof valor === 'string' ? valor.trim() : ''
}

// Una lista alineada por autor (matrícula, DNI del autor) viene como arreglo;
// si llega como texto, se parte por saltos de línea.
export const listaDe = (ficha, campo) => {
  const valor = valorDe(ficha, campo)
  if (Array.isArray(valor)) return valor.map((v) => String(v ?? '').trim())
  if (typeof valor === 'string') {
    return valor
      .split(/\n+/)
      .map((v) => v.trim())
  }
  return []
}

// Cotejo de títulos: igualdad normalizada. La inclusión no identifica una
// tesis: "Educación" también es parte de "Educación y cultura en otra
// institución". Si falta alguno de los dos, no se puede cotejar.
export const tituloCoincide = (preparado, recibido) => {
  const a = normalizar(preparado)
  const b = normalizar(recibido)
  if (!a || !b) return false
  return a === b
}

// La pantalla de ficha SOLO existe con semáforo verde y ficha en la respuesta
// (invariante del contrato v1.7: en rojo `ficha_deposito` es null).
export const debeMostrarFicha = (data) =>
  data?.semaforo === 'verde' &&
  data?.ficha_deposito != null &&
  Array.isArray(data?.ficha_deposito?.extraidos)

// Un timestamp de depósito debe ser una fecha ISO válida. La API aplica la
// zona de Perú al convertirla; la SPA solo decide si puede habilitar el
// papeleo.
export const timestampEsValido = (iso) => {
  if (typeof iso !== 'string') return false
  const iso8601 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$/
  if (!iso8601.test(iso)) return false
  const momento = new Date(iso)
  return !Number.isNaN(momento.getTime())
}

// Resultado del sondeo del buzón.
// 404 = todavía no hay depósito (NO es un error: se sigue esperando en silencio).
// Un depósito de otro trámite se ignora. Uno vencido o incompleto no habilita
// el papeleo.
export const interpretarSondeo = (status, cuerpo, tramite = {}) => {
  const tramiteId = tramite.tramiteId ?? ''
  const venceEn = tramite.venceEn ?? ''
  const fin = venceEn ? new Date(venceEn).getTime() : Number.NaN
  if (!venceEn || Number.isNaN(fin)) {
    return {
      estado: 'invalido',
      mensaje: 'El servidor no devolvió un vencimiento válido para este trámite.',
    }
  }
  if (fin <= Date.now()) {
    return {
      estado: 'expirado',
      mensaje: 'El trámite de la ficha expiró. Vuelve a preparar el depósito.',
    }
  }
  if (status === 404) return { estado: 'esperando' }
  if (status >= 200 && status < 300) {
    const tramiteRecibido = cuerpo?.tramite_id ?? ''
    if (!tramiteId || tramiteRecibido !== tramiteId) {
      return {
        estado: 'ajeno',
        mensaje: 'El depósito pertenece a otro trámite y se ignoró.',
      }
    }
    if (!cuerpo?.handle || !timestampEsValido(cuerpo?.timestamp)) {
      return {
        estado: 'invalido',
        mensaje: 'El depósito no tiene handle o timestamp válido; no se habilitó el papeleo.',
      }
    }
    return {
      estado: 'recibido',
      tramiteId: tramiteRecibido,
      handle: cuerpo.handle,
      titulo: cuerpo.titulo_observado ?? cuerpo.titulo ?? null,
      timestamp: cuerpo.timestamp,
    }
  }
  const detalle = cuerpo?.detail ?? cuerpo?.message
  return {
    estado: 'error',
    mensaje: detalle
      ? `El servidor respondió HTTP ${status}: ${detalle}`
      : `El servidor respondió HTTP ${status} al consultar el buzón.`,
  }
}

// Comprobación de los datos que el servidor exige (contrato v1.7): título,
// autores y las listas alineadas por autor. Es una ayuda de pantalla; la
// respuesta 422 del backend sigue siendo la autoridad.
//
// El ORCID del asesor NO entra aquí: con el contrato v1.15.0 es un campo
// extraído y no bloquea «Preparar depósito».
export const faltantesDe = (ficha) => {
  const faltantes = []
  if (!tituloDe(ficha)) faltantes.push('Falta el título del trabajo.')
  const autores = autoresDe(ficha)
  if (autores.length === 0) faltantes.push('Faltan los autores.')
  for (const campo of [CAMPO_MATRICULA, CAMPO_DNI_AUTOR]) {
    const etiqueta = campo === CAMPO_MATRICULA ? 'matrícula(s)' : 'DNI(s) de autor'
    const valores = listaDe(ficha, campo).filter(Boolean)
    if (valores.length === 0) {
      faltantes.push(`Faltan ${etiqueta}.`)
    } else if (autores.length > 0 && valores.length !== autores.length) {
      faltantes.push(
        `Faltan ${etiqueta}: hay ${autores.length} autor(es) y ${valores.length} valor(es) (una por autor).`
      )
    }
  }
  return faltantes
}

// ── Resguardo local de la ficha editada ───────────────────────────────
// La ficha editada no debe perderse si el operador recarga la página a
// mitad del trámite. Tres reglas (Arreglos.txt v9, Parte 3):
//  - versión: un resguardo de una versión anterior de la pantalla NO se
//    restaura (trae el ORCID en `manuales` y la pantalla nueva lo ignoraría
//    en silencio);
//  - identidad: el resguardo pertenece a un documento concreto; se identifica
//    por el CONTENIDO del archivo (hash), no por su nombre: dos archivos con
//    el mismo nombre no pueden compartir matrícula y DNI (F1);
//  - caducidad: el resguardo caduca (mismo TTL que el buzón: 1 hora) y, al
//    restaurarlo, se verifica que sea del documento actual (F5).
export const VERSION_RESGUARDO = 2
export const CLAVE_RESGUARDO = 'vb-ficha-deposito'
export const CADUCIDAD_RESGUARDO_MS = 60 * 60 * 1000

// Identidad del documento: hash del contenido cuando está disponible; si no,
// se recurre a nombre + tamaño (menos precisa, pero nunca mezcla documentos
// de tamaños distintos).
export const identidadDeArchivo = (archivo) => {
  if (!archivo) return 'sin-archivo'
  const hash = archivo.hash ?? ''
  if (hash) return `hash:${hash}`
  return `archivo:${archivo.nombre ?? ''}|${archivo.tamano ?? ''}`
}

export const guardarResguardo = (almacen, identidad, ficha, ahoraMs = Date.now()) => {
  try {
    almacen.setItem(
      CLAVE_RESGUARDO,
      JSON.stringify({ version: VERSION_RESGUARDO, identidad, creado: ahoraMs, ficha })
    )
    return true
  } catch {
    // Sin localStorage (modo privado, cuota llena): la ficha sigue en memoria.
    return false
  }
}

// Devuelve { ficha, motivo }. `motivo` explica por qué NO se restauró:
// 'version' | 'identidad' | 'caducado' | 'ilegible'.
export const leerResguardo = (almacen, identidad, ahoraMs = Date.now()) => {
  let guardado = null
  try {
    const crudo = almacen.getItem(CLAVE_RESGUARDO)
    if (!crudo) return { ficha: null, motivo: null }
    guardado = JSON.parse(crudo)
  } catch {
    return { ficha: null, motivo: 'ilegible' }
  }
  if (!guardado) return { ficha: null, motivo: null }
  if (guardado.version !== VERSION_RESGUARDO) return { ficha: null, motivo: 'version' }
  if (guardado.identidad !== identidad) return { ficha: null, motivo: 'identidad' }
  const creado = Number(guardado.creado)
  if (!Number.isFinite(creado) || ahoraMs - creado > CADUCIDAD_RESGUARDO_MS) {
    return { ficha: null, motivo: 'caducado' }
  }
  return { ficha: guardado.ficha ?? null, motivo: null }
}

export const borrarResguardo = (almacen) => {
  try {
    almacen.removeItem(CLAVE_RESGUARDO)
  } catch {
    // sin localStorage no hay resguardo que borrar
  }
}

// Explicación para el operador cuando el resguardo no se restauró.
export const mensajeDeDescarte = (motivo) => {
  switch (motivo) {
    case 'version':
      return 'El resguardo guardado por la versión anterior de la pantalla no se restauró.'
    case 'identidad':
      return 'El resguardo guardado pertenecía a otro documento: se descartó.'
    case 'caducado':
      return 'El resguardo guardado había caducado: se descartó.'
    case 'ilegible':
      return 'El resguardo guardado estaba dañado: se descartó.'
    default:
      return null
  }
}

// ── Configuración de papeleo (contrato propuesto, pendiente de Int1) ───
// El nombre del responsable se usa en la columna FIRMA del registro y la
// plantilla oficial Modelo B la usa la API para generar las constancias.
// Estos helpers implementan el contrato propuesto `GET/POST /papeleo-config`
// (documentado en docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md); mientras la API
// no lo exponga, la pantalla degrada con un aviso y no rompe el trámite.
export const ESTADO_PAPELEO = {
  desconocido: 'desconocido',
  listo: 'listo',
  incompleto: 'incompleto',
  noSoportado: 'no-soportado',
}

// Traduce la respuesta del servidor a un estado visible para el operador.
export const estadoPapeleoDe = (respuesta) => {
  if (!respuesta) return { estado: ESTADO_PAPELEO.desconocido, problemas: [] }
  const nombre = (respuesta.nombre_responsable ?? '').trim()
  const plantilla = Boolean(respuesta.plantilla_configurada)
  const problemas = []
  if (!nombre) problemas.push('Falta el nombre del responsable (columna FIRMA del registro).')
  if (!plantilla) problemas.push('Falta la plantilla oficial Modelo B (.docx).')
  const estado = problemas.length === 0 ? ESTADO_PAPELEO.listo : ESTADO_PAPELEO.incompleto
  return {
    estado,
    problemas,
    nombre,
    plantilla,
    plantillaNombre: respuesta.plantilla_nombre ?? null,
    detalle: respuesta.detalle ?? null,
  }
}

// Fecha y hora (DD/MM/AA y HH:MM, 24 h) a partir del ISO 8601 del clic
// "Depositar" que reporta el userscript.
export const formatearTimestamp = (iso) => {
  if (!iso) return { fecha: '', hora: '' }
  const momento = new Date(iso)
  if (Number.isNaN(momento.getTime())) return { fecha: '', hora: '' }
  const dd = String(momento.getDate()).padStart(2, '0')
  const mm = String(momento.getMonth() + 1).padStart(2, '0')
  const aa = String(momento.getFullYear()).slice(-2)
  const hh = String(momento.getHours()).padStart(2, '0')
  const mi = String(momento.getMinutes()).padStart(2, '0')
  return { fecha: `${dd}/${mm}/${aa}`, hora: `${hh}:${mi}` }
}

// Plan de descargas: una constancia por autor (el registro oficial exige una
// fila y una constancia POR ESTUDIANTE).
export const planDeDescargas = (ficha) => {
  const autores = autoresDe(ficha)
  return {
    total: autores.length,
    constancias: autores.map((autor, indice) => ({ indice, autor })),
  }
}

export const construirCuerpoConstancia = (
  ficha,
  handle,
  timestamp,
  indiceAutor,
  tramiteId
) => ({
  ficha,
  tramite_id: tramiteId,
  handle,
  timestamp,
  indice_autor: indiceAutor,
})

export const construirCuerpoFilaRegistro = (ficha, handle, timestamp, tramiteId) => ({
  ficha,
  tramite_id: tramiteId,
  handle,
  timestamp,
})

const detalleDe = async (res) => {
  try {
    const cuerpo = await res.json()
    const detalle = cuerpo?.detail ?? cuerpo?.message
    if (Array.isArray(detalle)) {
      return detalle.map((d) => (typeof d === 'string' ? d : d?.msg ?? JSON.stringify(d))).join('; ')
    }
    return typeof detalle === 'string' ? detalle : null
  } catch {
    return null
  }
}

// Token compartido del buzón (opcional). El backend (PR #66) admite
// `VISTOBUENO_API_TOKEN` y, cuando está definido, exige el header
// `X-VistoBueno-Token` en los endpoints del buzón. El loopback no lo exige
// (la SPA y el userscript corren en la misma máquina), así que el header solo
// se envía si hay token configurado en el build (VITE_API_TOKEN).
export const cabecerasBuzon = (token, extra = {}) => ({
  ...extra,
  ...(token ? { 'X-VistoBueno-Token': token } : {}),
})

// Publica la ficha editada en el buzón (POST /ficha-pendiente, 201).
// Devuelve el trámite y su vencimiento: ambos identifican esta ficha.
export const publicarFicha = async (apiUrl, ficha, token = '') => {
  const res = await fetch(`${apiUrl}/ficha-pendiente`, {
    method: 'POST',
    headers: cabecerasBuzon(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(ficha),
  })
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor rechazó la ficha (HTTP ${res.status}).`)
  }
  let cuerpo = null
  try {
    cuerpo = await res.json()
  } catch {
    cuerpo = null
  }
  if (!cuerpo?.tramite_id || !cuerpo?.vence_en) {
    throw new Error('El servidor no devolvió la identidad del trámite; publica la ficha de nuevo.')
  }
  return cuerpo
}

// Sondeo del buzón (GET /deposito): 404 = aún no hay depósito.
export const sondearDeposito = async (apiUrl, token = '', tramite = {}) => {
  const res = await fetch(`${apiUrl}/deposito`, { headers: cabecerasBuzon(token) })
  let cuerpo = null
  try {
    cuerpo = await res.json()
  } catch {
    cuerpo = null
  }
  return interpretarSondeo(res.status, cuerpo, tramite)
}

const nombreDeDescarga = (res, porDefecto) => {
  const cabecera = res.headers.get('Content-Disposition') || ''
  const coincidencia = /filename="?([^";]+)"?/.exec(cabecera)
  return coincidencia ? coincidencia[1] : porDefecto
}

const dispararDescarga = (blob, nombre) => {
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}

// Descarga de la constancia de UN autor (formato=docx) o del paquete por
// autor (formato=zip: constancia + registro.csv del mismo estudiante).
export const descargarConstancia = async (apiUrl, cuerpo, formato = 'docx', token = '') => {
  const res = await fetch(`${apiUrl}/constancia?formato=${formato}`, {
    method: 'POST',
    headers: cabecerasBuzon(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(cuerpo),
  })
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor no pudo generar la constancia (HTTP ${res.status}).`)
  }
  const blob = await res.blob()
  const porDefecto = formato === 'zip' ? 'constancia.zip' : 'constancia.docx'
  dispararDescarga(blob, nombreDeDescarga(res, porDefecto))
  return true
}

// Fila del registro: json (lista TSV para copiar/pegar) o archivo descargable
// (tsv/csv/xlsx). La app NUNCA escribe el XLSX oficial de la biblioteca.
export const generarFilaRegistro = async (apiUrl, cuerpo, formato = 'json', token = '') => {
  const res = await fetch(`${apiUrl}/fila-registro?formato=${formato}`, {
    method: 'POST',
    headers: cabecerasBuzon(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(cuerpo),
  })
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor no pudo generar la fila del registro (HTTP ${res.status}).`)
  }
  if (formato === 'json') {
    const cuerpoJson = await res.json()
    return Array.isArray(cuerpoJson?.filas) ? cuerpoJson.filas : []
  }
  const blob = await res.blob()
  const porDefecto = `registro_vistobueno.${formato}`
  dispararDescarga(blob, nombreDeDescarga(res, porDefecto))
  return []
}

// ── Configuración de papeleo (contrato propuesto, pendiente de Int1) ───
// GET /papeleo-config → { nombre_responsable, plantilla_configurada,
// plantilla_nombre, detalle }. Un 404 significa que el servidor todavía no
// expone el endpoint: la pantalla lo dice y sigue funcionando.
export const consultarPapeleo = async (apiUrl, token = '') => {
  const res = await fetch(`${apiUrl}/papeleo-config`, { headers: cabecerasBuzon(token) })
  if (res.status === 404) {
    return {
      estado: ESTADO_PAPELEO.noSoportado,
      problemas: [],
      detalle:
        'Este servidor todavía no expone la configuración de papeleo: el nombre del responsable y la ' +
        'plantilla se configuran en el servidor.',
    }
  }
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor no pudo informar la configuración de papeleo (HTTP ${res.status}).`)
  }
  let cuerpo = null
  try {
    cuerpo = await res.json()
  } catch {
    cuerpo = null
  }
  return estadoPapeleoDe(cuerpo)
}

// POST /papeleo-config (JSON) → guarda el nombre del responsable.
export const guardarNombreResponsable = async (apiUrl, nombre, token = '') => {
  const res = await fetch(`${apiUrl}/papeleo-config`, {
    method: 'POST',
    headers: cabecerasBuzon(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ nombre_responsable: nombre ?? '' }),
  })
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor no pudo guardar el nombre del responsable (HTTP ${res.status}).`)
  }
  let cuerpo = null
  try {
    cuerpo = await res.json()
  } catch {
    cuerpo = null
  }
  return estadoPapeleoDe(cuerpo)
}

// POST /papeleo-config/plantilla (multipart) → sube la plantilla Modelo B.
export const subirPlantillaPapeleo = async (apiUrl, archivo, token = '') => {
  const form = new FormData()
  form.append('plantilla', archivo)
  const res = await fetch(`${apiUrl}/papeleo-config/plantilla`, {
    method: 'POST',
    headers: cabecerasBuzon(token),
    body: form,
  })
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor no pudo guardar la plantilla (HTTP ${res.status}).`)
  }
  let cuerpo = null
  try {
    cuerpo = await res.json()
  } catch {
    cuerpo = null
  }
  return estadoPapeleoDe(cuerpo)
}
