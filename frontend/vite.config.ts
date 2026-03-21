import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('/vue/') || id.includes('vue-router') || id.includes('pinia') || id.includes('@vue/')) {
              return 'vue-vendor'
            }
            if (id.includes('vue-i18n') || id.includes('@intlify/')) {
              return 'vue-i18n'
            }
            if (id.includes('@tiptap/') || id.includes('prosemirror')) {
              return 'tiptap'
            }
            if (id.includes('lucide')) {
              return 'lucide'
            }
          }
        },
      },
    },
  },
  server: {
    // DEV_PORT / DEV_HOST are set by docker-compose.override.yml when running in Docker.
    // Fall back to local defaults so `npm run dev` on the host still works unchanged.
    port: parseInt(process.env.DEV_PORT ?? '15173'),
    host: process.env.DEV_HOST ?? 'localhost',
    // When nginx proxies the browser to Vite, HMR WebSocket must connect back to
    // nginx's port (3000) rather than Vite's internal port (5173).
    hmr: process.env.HMR_CLIENT_PORT
      ? { clientPort: parseInt(process.env.HMR_CLIENT_PORT) }
      : undefined,
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:18000',
        changeOrigin: true,
      },
      '/api/v1/ws': {
        target: process.env.WS_PROXY_TARGET ?? 'ws://127.0.0.1:18000',
        ws: true,
      },
    },
  },
})
