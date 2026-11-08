import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 部署在阿里云域名的 /iot/ 子路径下
export default defineConfig({
  base: '/iot/',
  plugins: [vue()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
