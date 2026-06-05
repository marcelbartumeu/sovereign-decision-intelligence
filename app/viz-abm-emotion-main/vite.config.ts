import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  base: '/andorra/',
  plugins: [react()],
  define: {
    'process.env': {}
  },
  server: {
    port: 3001,
    open: true
  },
  build: {
    rollupOptions: {
      external: ['@deck.gl/mesh-layers']
    }
  }
})
