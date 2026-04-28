import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// During development we proxy /api → the FastAPI server on :7777 so the
// dev experience works like the production single-origin build.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7777',
        changeOrigin: true,
      },
    },
  },
})
