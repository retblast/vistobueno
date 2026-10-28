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
]

export const CAMPOS_MANUALES = [
  { campo: CAMPO_MATRICULA, etiqueta: 'Matrícula', tipo: 'lista-autor' },
  { campo: CAMPO_DNI_AUTOR, etiqueta: 'DNI del autor', tipo: 'lista-autor' },
  { campo: CAMPO_DNI_ASESOR, etiqueta: 'DNI del asesor', tipo: 'texto' },
  { campo: CAMPO_ORCID_ASESOR, etiqueta: 'ORCID del asesor', tipo: 'texto' },
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

// Devuelve una ficha nueva con el campo actualizado (no muta la original).
export const establecerValor = (ficha, campo, valor) => {
  const base = { extraidos: [], manuales: [], ...ficha }
  const secciones = ['extraidos', 'manuales']
  for (const seccion of secciones) {
    const items = Array.isArray(base[seccion]) ? base[seccion] : []
    const indice = items.findIndex((c) => c?.campo === campo)
    if (indice >= 0) {
      const copia = items.map((c, i) => (i === indice ? { ...c, valor } : c))
      return { ...base, [seccion]: copia }
    }
  }
  // El servidor puede no traer un campo (ficha sin ese dato): se agrega.
  return { ...base, manuales: [...(base.manuales || []), { campo, valor }] }
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

// Cotejo de títulos: comparación por inclusión (el título del ítem puede traer
// ediciones menores). Si falta alguno de los dos, no se puede cotejar.
export const tituloCoincide = (preparado, recibido) => {
  const a = normalizar(preparado)
  const b = normalizar(recibido)
  if (!a || !b) return false
  return b.includes(a) || a.includes(b)
}

// La pantalla de ficha SOLO existe con semáforo verde y ficha en la respuesta
// (invariante del contrato v1.7: en rojo `ficha_deposito` es null).
export const debeMostrarFicha = (data) =>
  data?.semaforo === 'verde' &&
  data?.ficha_deposito != null &&
  Array.isArray(data?.ficha_deposito?.extraidos)

// Resultado del sondeo del buzón.
// 404 = todavía no hay depósito (NO es un error: se sigue esperando en silencio).
export const interpretarSondeo = (status, cuerpo) => {
  if (status === 404) return { estado: 'esperando' }
  if (status >= 200 && status < 300) {
    return {
      estado: 'recibido',
      handle: cuerpo?.handle ?? '',
      titulo: cuerpo?.titulo ?? null,
      timestamp: cuerpo?.timestamp ?? '',
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

export const construirCuerpoConstancia = (ficha, handle, timestamp, indiceAutor) => ({
  ficha,
  handle,
  timestamp,
  indice_autor: indiceAutor,
})

export const construirCuerpoFilaRegistro = (ficha, handle, timestamp) => ({
  ficha,
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

// Publica la ficha editada en el buzón (POST /ficha-pendiente, 204).
export const publicarFicha = async (apiUrl, ficha) => {
  const res = await fetch(`${apiUrl}/ficha-pendiente`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ficha),
  })
  if (!res.ok) {
    const detalle = await detalleDe(res)
    throw new Error(detalle ?? `El servidor rechazó la ficha (HTTP ${res.status}).`)
  }
  return true
}

// Sondeo del buzón (GET /deposito): 404 = aún no hay depósito.
export const sondearDeposito = async (apiUrl) => {
  const res = await fetch(`${apiUrl}/deposito`)
  let cuerpo = null
  try {
    cuerpo = await res.json()
  } catch {
    cuerpo = null
  }
  return interpretarSondeo(res.status, cuerpo)
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
export const descargarConstancia = async (apiUrl, cuerpo, formato = 'docx') => {
  const res = await fetch(`${apiUrl}/constancia?formato=${formato}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
export const generarFilaRegistro = async (apiUrl, cuerpo, formato = 'json') => {
  const res = await fetch(`${apiUrl}/fila-registro?formato=${formato}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
