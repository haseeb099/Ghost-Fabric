import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Override with GF_API_TARGET when port 8000 is taken by another local backend.
const apiTarget = process.env.GF_API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': apiTarget,
      '/ws': {
        target: apiTarget.replace(/^http/, 'ws'),
        ws: true,
      },
    },
  },
})
