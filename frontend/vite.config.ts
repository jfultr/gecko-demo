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
    host: '0.0.0.0',
    port: 5173,
    proxy: process.env.VITE_API_TARGET
      ? {
          '/api': {
            target: process.env.VITE_API_TARGET,
            changeOrigin: true,
          },
        }
      : undefined,
  },
})
