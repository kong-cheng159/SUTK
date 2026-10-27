import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  base: './',
  plugins: [
    vue(),
    Components({ resolvers: [NaiveUiResolver()] }),
  ],
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // 与 Tauri 一致；仅 npm run dev 时需另开 desktop/server.py --port 8765，或 npm run dev:full
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.VITE_API_PORT || 8765}`,
        changeOrigin: true,
      },
    },
  },
})
