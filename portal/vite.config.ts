import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Portal 管理前端构建配置：
// - base: '/portal/' —— 由 FastAPI 静态挂载在 /portal 路径下
// - server.proxy：开发时把 /admin 代理到本机 18000 平台，避免跨域
export default defineConfig({
  plugins: [react()],
  base: '/portal/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/admin': {
        target: 'http://127.0.0.1:18000',
        changeOrigin: true,
      },
    },
  },
})
