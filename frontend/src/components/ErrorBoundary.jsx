import { Component } from 'react'

// Límite de error de React (React Docs: "Error Boundaries"): si el render de
// una vista falla (bug propio o payload inesperado del servidor), la app no
// se queda en pantalla blanca: muestra un aviso claro con una salida real
// («Volver a la pantalla de carga») y el detalle técnico plegado para el
// reporte del fallo. Solo captura errores de render de los hijos; los
// manejadores de eventos y los efectos asíncronos siguen su curso.
// Se prueba con tests de componente (día 3 del cierre); el E2E de flujo no
// puede provocar un fallo de render de forma controlada.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Solo consola: el MVP no tiene servicio de telemetría.
    console.error('ErrorBoundary capturó un fallo de render:', error, info?.componentStack)
  }

  // «Volver a la pantalla de carga»: se limpia el límite y el App descarta el
  // reporte actual, así el usuario retoma el flujo desde un estado conocido.
  volverACarga = () => {
    this.setState({ error: null })
    this.props.onReiniciar?.()
  }

  render() {
    if (this.state.error) {
      return (
        <main>
          <div className="card">
            <h2>Ocurrió un error inesperado</h2>
            <p className="intro">
              La pantalla dejó de responder por un fallo interno. Vuelva a la pantalla de
              carga e intente nuevamente; si el problema persiste, comparta el detalle
              técnico con el administrador.
            </p>
            <details className="error-detalle">
              <summary>Ver el detalle técnico</summary>
              <pre>{String(this.state.error?.message || this.state.error)}</pre>
            </details>
            <div className="acciones-form">
              <button className="btn-validar" onClick={this.volverACarga}>
                Volver a la pantalla de carga
              </button>
            </div>
          </div>
        </main>
      )
    }
    return this.props.children
  }
}
