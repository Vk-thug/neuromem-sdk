import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// During development we proxy /api → the FastAPI server on :7777 so the
// dev experience works like the production single-origin build.
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Use array form so Vite/Rollup hands the alias to the full
    // resolver pipeline (extension probing, index.ts, etc.). The
    // bare-string form sometimes fails on Linux CI when path
    // aliasing skips extension auto-resolution.
    alias: [
      { find: /^@\/(.*)$/, replacement: path.resolve(__dirname, 'src/$1') },
    ],
    extensions: ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json'],
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
