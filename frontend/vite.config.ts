import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: process.env.TRACKER_API_URL || 'http://127.0.0.1:8000',
        rewrite: path => path.replace(/^\/api/, ''),
      },
    },
  },
})
