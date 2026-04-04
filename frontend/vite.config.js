import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/generate': 'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/download': 'http://localhost:8000',
      '/preview': 'http://localhost:8000',
      '/previews': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/slides': 'http://localhost:8000',
      '/regenerate-slide': 'http://localhost:8000',
      '/restyle-slides': 'http://localhost:8000',
      '/update-slide': 'http://localhost:8000',
      '/reorder-slides': 'http://localhost:8000',
      '/duplicate-slide': 'http://localhost:8000',
      '/delete-slide': 'http://localhost:8000',
      '/outputs': 'http://localhost:8000',
    },
  },
})
