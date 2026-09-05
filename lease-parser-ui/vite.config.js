import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Fixed port matches what test.md documents for the backend's CORS-enabled
// demo endpoints to expect this origin from (see LEASE_ABSTRACTION_ENABLE_DEMO_UI).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
})
