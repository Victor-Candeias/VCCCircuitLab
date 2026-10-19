import { defineConfig, devices } from '@playwright/test';

/**
 * Testes E2E (E4-05): arrancam o backend (FastAPI, `apps/api`) e o frontend (`vite dev`, que
 * encaminha `/api` para o backend — ver `vite.config.ts`) e correm os cenários do
 * `Docs/arquitetura_simulador_circuitos.md` §12 que precisam do browser real: criar um
 * circuito, ligações, round-trip JSON, gerar → editar → simular, recuperação após refresh e
 * desempenho com ~100 componentes.
 *
 * `PLAYWRIGHT_SKIP_BACKEND=1` permite correr os testes que não precisam da API (sem o `uvicorn`
 * do backend, p. ex. numa máquina sem o ambiente Python preparado).
 */
const skipBackend = process.env.PLAYWRIGHT_SKIP_BACKEND === '1';
const PORT = 4173;
const API_PORT = 8000;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}/`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'node_modules/.bin/vite dev --host 127.0.0.1 --port 4173 --strictPort',
      url: `http://127.0.0.1:${PORT}/`,
      reuseExistingServer: !process.env.CI,
      env: { BASE_PATH: '/', API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
      timeout: 60_000,
    },
    ...(skipBackend
      ? []
      : [
          {
            command: `../api/.venv/bin/uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port ${API_PORT}`,
            url: `http://127.0.0.1:${API_PORT}/health`,
            // Cada teste regista/inicia sessão a partir do mesmo IP (E5-04).
            env: { AUTH_RATE_LIMIT_PER_MINUTE: '1000', RATE_LIMIT_PER_MINUTE: '0' },
            reuseExistingServer: !process.env.CI,
            timeout: 60_000,
          },
        ]),
  ],
});
