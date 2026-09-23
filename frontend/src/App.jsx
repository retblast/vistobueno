import { useState, useEffect } from 'react'
import Upload from './components/Upload'
import Report from './components/Report'
import { MOCK_REPORT } from './mocks'

// API base URL:
// - Default '' = mismo origen (funciona con el proxy de Vite en `npm run dev`).
// - En producción no hay proxy de Vite: definir VITE_API_URL en tiempo de build
//   (p.ej. VITE_API_URL=https://api.ejemplo.com) o servir el frontend detrás de un
//   reverse proxy (nginx/caddy) que enrute /validar al backend FastAPI.
//   Ver README.md → "Despliegue del frontend".
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

function DarkModeToggle() {
  const [dark, setDark] = useState(() =>
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])
  return (
    <button
      className="modo-oscuro-btn"
      onClick={() => setDark((d) => !d)}
      title={dark ? 'Modo claro' : 'Modo oscuro'}
      aria-label={dark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
    >
      {dark ? '☀️' : '🌙'}
    </button>
  )
}

function App() {
  const [reportData, setReportData] = useState(null)
  const currentView = reportData ? (
    <Report data={reportData} onBack={() => setReportData(null)} />
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <DarkModeToggle />
          <button className="volver" onClick={() => setReportData(null)} style={{ display: reportData ? 'inline-block' : 'none' }}>
            ← Validar otro archivo
          </button>
        </div>
      </header>
      {currentView}
      <footer>
        Sistema VistoBueno — Practicante · Biblioteca FECyC · UNT
      </footer>
    </div>
  )
}

export default App
