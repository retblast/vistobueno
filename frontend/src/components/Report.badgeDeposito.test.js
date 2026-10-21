// Tests unitarios de badgeDeposito() — contrato v1.6: estado del depósito
// del documento en DSpace (opt-in del operador, solo con semáforo verde,
// best-effort: el ítem queda en la cola de aprobación de la sede).
// Runner: vitest (`npm test`).
import { describe, it, expect } from 'vitest'
import { badgeDeposito } from './Report.jsx'

const dep = (estado, detalle = null) => ({ estado, detalle })

describe('badgeDeposito', () => {
  it('sin deposito (null/undefined) o estado no string → null', () => {
    expect(badgeDeposito(null, 'verde')).toBeNull()
    expect(badgeDeposito(undefined, 'rojo')).toBeNull()
    expect(badgeDeposito({ detalle: 'x' }, 'verde')).toBeNull()
  })

  it('enviado → clase ok con el mensaje de cola de aprobación', () => {
    const b = badgeDeposito(dep('enviado', 'item 1234'), 'verde')
    expect(b.clase).toBe('ok')
    expect(b.texto).toContain('cola de aprobación')
    expect(b.detalle).toBeUndefined()
  })

  it('fallo → clase fail con el detalle técnico del servidor', () => {
    const b = badgeDeposito(dep('fallo', 'DSpace respondió 422: dc.title requerido'), 'verde')
    expect(b.clase).toBe('fail')
    expect(b.detalle).toContain('422')
  })

  it('fallo sin detalle → mensaje de reintento por defecto', () => {
    const b = badgeDeposito(dep('fallo'), 'verde')
    expect(b.detalle).toContain('reintente')
  })

  it('no_apto → clase warn: solo se depositan documentos verdes', () => {
    const b = badgeDeposito(dep('no_apto'), 'rojo')
    expect(b.clase).toBe('warn')
    expect(b.texto).toContain('semáforo verde')
  })

  it('deshabilitado → nota para administradores SOLO con detalle (contrato)', () => {
    expect(badgeDeposito(dep('deshabilitado'), 'verde')).toBeNull()
    const b = badgeDeposito(dep('deshabilitado', 'configure VISTOBUENO_DSPACE=1'), 'verde')
    expect(b.clase).toBe('info')
    expect(b.texto).toBe('Nota para administradores:')
    expect(b.detalle).toContain('VISTOBUENO_DSPACE')
  })

  it('sin_solicitud → con semáforo verde ofrece la casilla; con rojo, nada', () => {
    const b = badgeDeposito(dep('sin_solicitud'), 'verde')
    expect(b.clase).toBe('info')
    expect(b.texto).toContain('Depositar en el repositorio')
    expect(badgeDeposito(dep('sin_solicitud'), 'rojo')).toBeNull()
  })

  it('estado desconocido → null (fail-safe ante contratos futuros)', () => {
    expect(badgeDeposito(dep('algo_nuevo'), 'verde')).toBeNull()
  })
})
