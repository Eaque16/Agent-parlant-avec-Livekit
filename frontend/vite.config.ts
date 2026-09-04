import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/static/',
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000', '/health': 'http://localhost:8000', '/ws': { target:'ws://localhost:8000', ws:true } } },
  build: { outDir: '../app/static', emptyOutDir: true },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
})
