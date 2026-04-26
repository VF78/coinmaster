import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/custom/',
  plugins: [react()],
  build: {
    outDir: 'dist-custom',
    emptyOutDir: true,
    rollupOptions: {
      input: 'index.custom.html',
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8787',
        changeOrigin: true,
      },
    },
  },
});
