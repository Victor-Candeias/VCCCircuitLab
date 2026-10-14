import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { configDefaults } from 'vitest/config';

// Em desenvolvimento, `/api` é encaminhado para o backend (mesma origem: sem CORS e acessível
// fora da máquina). Com `VITE_API_BASE_URL` definido, o browser chama essa URL diretamente.
const apiProxy = {
  '/api': { target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000', changeOrigin: true },
};

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serve o site em /<repositório>/; usar BASE_PATH=/ com domínio próprio.
  base: process.env.BASE_PATH ?? '/VCCCircuitLab/',
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
});
