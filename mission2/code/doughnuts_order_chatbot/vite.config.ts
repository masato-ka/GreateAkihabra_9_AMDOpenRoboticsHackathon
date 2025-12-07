import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // 外部IPからアクセス可能にする
    port: 3000,
    open: true
  }
})

