import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    headers: {
      // Content Security Policy - permite eval em desenvolvimento
      'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline' http://localhost:* ws://localhost:*; worker-src 'self' blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' http://localhost:* ws://localhost:* http://127.0.0.1:*; object-src 'none'; base-uri 'self';",
    },
  },
  build: {
    // Minificar sem usar eval
    minify: 'esbuild', // Usa esbuild em vez de terser (mais seguro)
    // Desabilitar source maps em produção se necessário para segurança
    sourcemap: true, // Manter em dev para debugging
  },
  // Desabilitar qualquer transformação que possa usar eval
  esbuild: {
    legalComments: 'none',
  },
})
