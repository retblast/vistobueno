import { Outlet } from 'react-router-dom'

function Layout() {
  return (
    <div className="app">
      <header>
        <div className="izq">
          <div className="escudo">VB</div>
          <div>
            <h1>VistoBueno</h1>
            <div className="sub">FECyC · Universidad Nacional de Trujillo</div>
          </div>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer>
        Sistema VistoBueno — Practicante · Biblioteca FECyC · UNT
      </footer>
    </div>
  )
}

export default Layout