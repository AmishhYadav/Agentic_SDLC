import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy /runs to Plan 01-01's FastAPI backend (default uvicorn port 8000)
    // so fetch calls from the browser hit the same origin as the dev server
    // and never need backend CORS configuration (backend files are not
    // modified by this plan).
    proxy: {
      '/runs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/team': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/codebase': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
