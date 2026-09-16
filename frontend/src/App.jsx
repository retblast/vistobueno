import { useState, useEffect } from 'react'
import Upload from './components/Upload'
import Report from './components/Report'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

// Datos mock que imitan la respuesta del backend (build_report).
// Se usan mientras el Integrante 1 no tenga el endpoint listo.
const MOCK_REPORT = {
  semaforo: 'rojo',
  resumen: { total: 31, fallidos_error: 3, fallidos_warning: 2 },
  resultados: [
    { rule_id: 'papel_tamano', passed: true, severity: 'error', message: 'El tamaño del papel debe ser A4', expected: '210 x 297 mm', found: 'cumple' },
    { rule_id: 'fuente_principal', passed: true, severity: 'error', message: 'La fuente del cuerpo debe ser Times New Roman', expected: 'Times New Roman', found: 'cumple' },
    { rule_id: 'tamano_cuerpo', passed: true, severity: 'error', message: 'El tamaño de letra del cuerpo debe ser 12pt', expected: '12pt', found: 'cumple' },
    { rule_id: 'interlineado', passed: true, severity: 'error', message: 'El interlineado del cuerpo debe ser 1.5', expected: '1.5 líneas', found: 'cumple' },
    { rule_id: 'margen_superior', passed: true, severity: 'error', message: 'El margen superior debe ser 2.5 cm', expected: '2.5 cm', found: 'cumple' },
    { rule_id: 'margen_izquierdo', passed: true, severity: 'error', message: 'El margen izquierdo debe ser 3 cm', expected: '3 cm', found: 'cumple' },
    { rule_id: 'margen_derecho', passed: false, severity: 'warning', message: 'El margen derecho debe ser 2.5 cm', expected: '2.5 cm', found: '2.5 cm aprox. (plantillas usan 708/709)' },
    { rule_id: 'sangria_parrafo', passed: false, severity: 'warning', message: 'La sangría de primera línea debe ser 1.27 cm', expected: '1.27 cm', found: '1.25 cm (708 twips)' },
    { rule_id: 'numeracion_cuerpo_arabigo', passed: true, severity: 'error', message: 'El cuerpo debe numerarse con arábigos desde la introducción', expected: 'arábigos', found: 'cumple' },
    { rule_id: 'numeracion_preliminares_romano', passed: false, severity: 'error', message: 'Los preliminares deben numerarse en romanos', expected: 'romanos (i, ii, iii...)', found: 'arábigos en preliminares' },
    { rule_id: 'caratula_universidad_negrita_mayusculas', passed: true, severity: 'error', message: 'El nombre de la universidad debe ir en negrita y mayúsculas', expected: 'negrita + MAYÚS', found: 'cumple' },
    { rule_id: 'caratula_titulo_negrita_mixta', passed: false, severity: 'error', message: 'El título del trabajo debe ir en negrita y mixta', expected: 'negrita + mixta', found: 'todo mayúsculas' },
    { rule_id: 'estructura_tinv_cuantitativo', passed: true, severity: 'error', message: 'Se deben incluir las secciones del diseño cuantitativo', expected: 'secciones obligatorias', found: 'cumple' }
  ],
  como_preguntar_a_una_ia: [
    { rule_id: 'margen_derecho', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: El margen derecho debe ser 2.5 cm\n- Valor esperado según el reglamento: 2.5 cm\n- Lo que encontró el validador: 2.5 cm aprox. (plantillas usan 708/709)\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
    { rule_id: 'sangria_parrafo', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: La sangría de primera línea debe ser 1.27 cm\n- Valor esperado según el reglamento: 1.27 cm\n- Lo que encontró el validador: 1.25 cm (708 twips)\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
    { rule_id: 'numeracion_preliminares_romano', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: Los preliminares deben numerarse en romanos\n- Valor esperado según el reglamento: romanos (i, ii, iii...)\n- Lo que encontró el validador: arábigos en preliminares\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' },
    { rule_id: 'caratula_titulo_negrita_mixta', prompt: 'Tengo un documento de tesis en Word (Universidad Nacional de Trujillo). Detecté un problema de formato:\n\n- Regla incumplida: El título del trabajo debe ir en negrita y mixta\n- Valor esperado según el reglamento: negrita + mixta\n- Lo que encontró el validador: todo mayúsculas\n\n¿Puedes darme instrucciones paso a paso para corregir esto en Microsoft Word, sin afectar el resto del formato del documento?' }
  ]
}

// Se exporta MOCK_REPORT para que Upload.jsx lo use como fallback cuando
// la API del backend no esté disponible (Integrante 1 aún no la termina).
export { MOCK_REPORT }

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
