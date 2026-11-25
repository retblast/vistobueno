// Lógica pura de la pantalla de carga (timeout y espera por límite de
// peticiones). Módulo sin React: las funciones se prueban con vitest
// (`npm test`) y la pantalla (components/Upload.jsx) las consume.
//
// Contexto (Arreglos.txt v9, Parte 1): con una tesis real la validación
// tarda más de 30 s y el navegador cortaba la petición aunque el servidor
// siguiera trabajando. Además, el backend responde 429 con la cabecera
// `Retry-After` (en segundos) cuando se acumulan validaciones: la espera
// real puede ser de varios minutos, así que la pantalla tiene que mostrar
// cuánto falta y en qué hora se puede reintentar.

// Hash SHA-256 del CONTENIDO del archivo. Sirve para identificar el
// documento del resguardo de la ficha: dos archivos con el mismo nombre no
// pueden compartir matrícula y DNI (F1). Si el navegador no expone
// `crypto.subtle` (contexto no seguro), se devuelve '' y la identidad cae al
// nombre + tamaño.
export const hashDeArchivo = async (file) => {
  try {
    const cripto = globalThis.crypto
    if (!cripto?.subtle || typeof file?.arrayBuffer !== 'function') return ''
    const buffer = await file.arrayBuffer()
    const digest = await cripto.subtle.digest('SHA-256', buffer)
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('')
  } catch {
    return ''
  }
}

// Minutos de espera del navegador antes de abortar la petición. Abortar la
// espera NO cancela el trabajo del servidor: solo deja de esperarlo.
export const TIMEOUT_VALIDACION_MINUTOS = 2

// Segundos que espera el backend antes de admitir otra validación (valor por
// defecto de la etiqueta Retry-After cuando la cabecera no es utilizable).
// NO se usa para inventar un plazo: si el servidor no manda la cabecera, la
// pantalla muestra su mensaje y nada más.
export const RETRY_AFTER_POR_DEFECTO = null

// Lee la cabecera `Retry-After` (segundos) de una respuesta. Devuelve null
// si no viene o si no es un número entero utilizable.
export const leerRetryAfter = (res) => {
  if (!res?.headers || typeof res.headers.get !== 'function') return null
  const bruto = res.headers.get('Retry-After')
  if (bruto === null || bruto === undefined || bruto === '') return null
  const valor = Number(String(bruto).trim())
  if (!Number.isFinite(valor) || valor <= 0) return null
  return Math.floor(valor)
}

// "2 min 14 s" / "45 s" / "3 min" (para el operador: la espera real).
export const formatearEspera = (segundos) => {
  const total = Math.max(0, Math.floor(Number(segundos) || 0))
  const minutos = Math.floor(total / 60)
  const resto = total % 60
  if (minutos === 0) return `${resto} s`
  if (resto === 0) return `${minutos} min`
  return `${minutos} min ${resto} s`
}

// Hora local en que se podrá reintentar (HH:MM, 24 h).
export const horaDeReintento = (momentoMs) => {
  const momento = new Date(momentoMs)
  if (Number.isNaN(momento.getTime())) return ''
  const hh = String(momento.getHours()).padStart(2, '0')
  const mm = String(momento.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

// Texto de la espera: cuánto falta y a qué hora se puede reintentar.
export const mensajeEspera = (segundos, ahoraMs = Date.now()) => {
  const total = Math.max(0, Math.floor(Number(segundos) || 0))
  const hasta = ahoraMs + total * 1000
  return {
    faltan: formatearEspera(total),
    hasta: horaDeReintento(hasta),
    restante: total,
    momentoHasta: hasta,
  }
}

// Mensaje completo del límite de peticiones: la espera real y la hora exacta.
export const textoEspera = (segundos, ahoraMs = Date.now()) => {
  const info = mensajeEspera(segundos, ahoraMs)
  return `Faltan ${info.faltan}. Podrá reintentar a las ${info.hasta}.`
}

// Lo mismo, pero tomando la hora límite ya calculada (la cuenta regresiva
// descuenta sobre el momento límite, no sobre "ahora + restante").
export const textoEsperaHasta = (momentoHasta, ahoraMs = Date.now()) => {
  const restante = Math.max(0, Math.ceil((momentoHasta - ahoraMs) / 1000))
  const info = mensajeEspera(restante, ahoraMs)
  return `Faltan ${info.faltan}. Podrá reintentar a las ${horaDeReintento(momentoHasta)}.`
}
