import { useState, useEffect } from 'react'
import Upload from './components/Upload'
import Report from './components/Report'
import ErrorBoundary from './components/ErrorBoundary'

// API base URL:
// - Default '' = mismo origen (funciona con el proxy de Vite en `npm run dev`).
// - En producción no hay proxy de Vite: definir VITE_API_URL en tiempo de build
//   (p.ej. VITE_API_URL=https://api.ejemplo.com) o servir el frontend detrás de un
//   reverse proxy (nginx/caddy) que enrute /validar al backend FastAPI.
//   Ver README.md → "Despliegue del frontend".
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

// Tema (claro/oscuro): la clase `.dark` en <html> es la ÚNICA fuente de verdad
// de las variables oscuras (el CSS ya no usa @media prefers-color-scheme para
// esto, porque desactivaba el botón cuando el SO estaba en oscuro).
// Prioridad: localStorage → preferencia del SO.
export function temaOscuroInicial() {
  const guardado = window.localStorage.getItem('vb-tema')
  if (guardado === 'oscuro') return true
  if (guardado === 'claro') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

// Iconos SVG inline (mismo criterio que la dropzone desde v7: sin emoji, se
// renderizan igual en todos los sistemas y en las capturas de evidencia).
const IconoSol = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
)
const IconoLuna = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
)

function DarkModeToggle() {
  const [dark, setDark] = useState(temaOscuroInicial)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    window.localStorage.setItem('vb-tema', dark ? 'oscuro' : 'claro')
  }, [dark])
  return (
    <button
      className="modo-oscuro-btn"
      onClick={() => setDark((d) => !d)}
      title={dark ? 'Modo claro' : 'Modo oscuro'}
      aria-label={dark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      aria-pressed={dark}
    >
      {dark ? <IconoSol /> : <IconoLuna />}
    </button>
  )
}

function App() {
  const [reportData, setReportData] = useState(null)
  const volverACarga = () => setReportData(null)
  const currentView = reportData ? (
    <Report data={reportData} onBack={volverACarga} />
  ) : (
    <Upload onValidated={(data) => setReportData(data)} apiUrl={API_BASE_URL} />
  )

  return (
    <div className="app">
      <header className="encabezado">
        <div className="izq">
          <div className="escudo">VB</div>
          <div>
            <h1>VistoBueno</h1>
            <div className="sub">FECyC · Universidad Nacional de Trujillo</div>
          </div>
        </div>
        <DarkModeToggle />
      </header>
      {/* Límite de error: un fallo de render (bug o payload inesperado) muestra
          un aviso con salida a la carga en vez de dejar la pantalla en blanco. */}
      <ErrorBoundary onReiniciar={volverACarga}>
        {currentView}
      </ErrorBoundary>
      <footer>
        Sistema VistoBueno — Practicante · Biblioteca FECyC · UNT
      </footer>
    </div>
  )
}

export default App
