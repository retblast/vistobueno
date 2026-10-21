// Tests unitarios de fichaIncompleta() — contrato v1.6: DSpace exige título
// y autor para crear el ítem; el resto de la ficha es opcional. El cliente
// bloquea el envío de un depósito que fallaría en DSpace por ítem incompleto.
// Runner: vitest (`npm test`).
import { describe, it, expect } from 'vitest'
import { fichaIncompleta } from './Upload.jsx'

const ficha = (over = {}) => ({
  titulo: '',
  autores: '',
  asesor: '',
  resumen: '',
  palabrasClave: '',
  ...over,
})

describe('fichaIncompleta', () => {
  it('título y autores vacíos → incompleta', () => {
    expect(fichaIncompleta(ficha())).toBe(true)
  })

  it('con título y autores (aunque el resto falte) → completa', () => {
    expect(fichaIncompleta(ficha({ titulo: 'Una tesis', autores: 'Pérez, A.' }))).toBe(false)
  })

  it('solo el título (o solo los autores) → incompleta', () => {
    expect(fichaIncompleta(ficha({ titulo: 'Una tesis' }))).toBe(true)
    expect(fichaIncompleta(ficha({ autores: 'Pérez, A.' }))).toBe(true)
  })

  it('los espacios en blanco no cuentan y tolera valores ausentes', () => {
    expect(fichaIncompleta(ficha({ titulo: '   ', autores: '  ' }))).toBe(true)
    expect(fichaIncompleta(ficha({ titulo: ' Tesis ', autores: ' Pérez ' }))).toBe(false)
    expect(fichaIncompleta(null)).toBe(true)
    expect(fichaIncompleta(undefined)).toBe(true)
    expect(fichaIncompleta({})).toBe(true)
  })
})
