import { useState, useEffect } from 'react'
import Upload from './components/Upload'
import Report from './components/Report'
import FichaDeposito from './components/FichaDeposito'

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
      {dark ? '☀️' : '🌙'}
    </button>
  )
}

function App() {
  const [reportData, setReportData] = useState(null)
  // Vista actual: 'carga' (subir archivo), 'reporte' o 'ficha' (semana 8).
  const [vista, setVista] = useState('carga')
  const volverACarga = () => {
    setReportData(null)
    setVista('carga')
  }
  const currentView = vista === 'ficha' && reportData ? (
    <FichaDeposito
      data={reportData}
      apiUrl={API_BASE_URL}
      onBack={() => setVista('reporte')}
    />
  ) : reportData ? (
    <Report
      data={reportData}
      onBack={volverACarga}
      onIrAFicha={() => setVista('ficha')}
    />

  ) : (
    <Upload onValidated={(data) => { setReportData(data); setVista('reporte') }} apiUrl={API_BASE_URL} />
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
      {currentView}
      <footer>
        Sistema VistoBueno — Practicante · Biblioteca FECyC · UNT
      </footer>
    </div>
  )
}

export default App
