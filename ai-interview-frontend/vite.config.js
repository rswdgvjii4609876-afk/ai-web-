import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devProxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8006'
  const base = env.VITE_APP_BASE || '/'

  return {
    plugins: [vue()],
    base,
    server: {
      host: '0.0.0.0',
      port: 3000,
      proxy: {
        '/api': {
          target: devProxyTarget,
          changeOrigin: true
        },
        '/uploads': {
          target: devProxyTarget,
          changeOrigin: true
        }
      }
    },
    preview: {
      host: '0.0.0.0',
      port: 4173
    }
  }
})
