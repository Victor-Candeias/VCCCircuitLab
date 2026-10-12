import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages serve o site em /<repositório>/; usar BASE_PATH=/ com domínio próprio.
  base: process.env.BASE_PATH ?? '/VCCCircuitLab/',
  plugins: [react()],
})
