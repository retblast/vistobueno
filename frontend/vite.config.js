import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    // Proxy SOLO existe en `vite dev`. En `vite preview` o un build estático
    // no hay proxy: usar VITE_API_URL o un reverse proxy en despliegue.
    proxy: {
      '/validar': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})