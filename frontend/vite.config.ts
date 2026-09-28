import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@fixture/manifest': fileURLToPath(
        new URL('../fixtures/manifest.v1.json', import.meta.url),
      ),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
})
