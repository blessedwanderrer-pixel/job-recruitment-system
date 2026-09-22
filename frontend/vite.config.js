import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

function extraAllowedHosts(mode) {
  const env = loadEnv(mode, process.cwd(), '')
  return (env.VITE_ALLOWED_HOST || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => value.replace(/^https?:\/\//i, '').replace(/\/.*$/, '').split(':')[0].toLowerCase())
    .filter((host) => host && host !== '*' && host !== 'true')
}

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: extraAllowedHosts(mode),
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
}))
