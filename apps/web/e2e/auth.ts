import { expect, test as base } from '@playwright/test';
import catalogFixture from '@vcccircuitlab/circuit-schema/fixtures/catalog.json' with { type: 'json' };

/**
 * Sem sessão a aplicação só mostra o ecrã de login (E5-09). Este `test` inicia sessão antes de
 * cada teste e injeta o token no `sessionStorage`, para os cenários começarem já no editor.
 *
 * Com o backend, regista (uma vez) e autentica um utilizador de teste na API — precisa do
 * MongoDB configurado no `.env`. Com `PLAYWRIGHT_SKIP_BACKEND=1` simula `GET /api/v1/auth/me` e
 * `GET /api/v1/components` (catálogo da fixture de `circuit-schema`).
 *
 * Contra o site publicado (E5-06): `PLAYWRIGHT_API_URL` é a URL base da API (a mesma do
 * `VITE_API_BASE_URL`; por omissão, a origem do `baseURL`) e `E2E_EMAIL`/`E2E_PASSWORD` permitem
 * usar uma conta já existente em vez da conta de teste.
 */
export const SESSION_STORAGE_KEY = 'vcccircuitlab.session';
export const E2E_USER = {
  name: 'Utilizador E2E',
  email: process.env.E2E_EMAIL || 'e2e@vcccircuitlab.test',
  password: process.env.E2E_PASSWORD || 'E2e-Teste-2025!',
};

const skipBackend = process.env.PLAYWRIGHT_SKIP_BACKEND === '1';
const API_URL = (process.env.PLAYWRIGHT_API_URL ?? '').trim().replace(/\/+$/, '');

/** URL de um endpoint da API (relativo ao `baseURL` quando `PLAYWRIGHT_API_URL` não existe). */
export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export const test = base.extend<{ session: string }>({
  session: [
    async ({ page, request }, use) => {
      let token = 'e2e-token';
      if (skipBackend) {
        await page.route('**/api/v1/auth/me', (route) =>
          route.fulfill({
            json: {
              id: 'e2e',
              name: E2E_USER.name,
              email: E2E_USER.email,
              role: 'USER',
              createdAt: '2025-01-01T00:00:00Z',
            },
          }),
        );
        await page.route('**/api/v1/components', (route) =>
          route.fulfill({ json: catalogFixture }),
        );
      } else {
        const created = await request.post(apiUrl('/api/v1/users'), {
          data: { ...E2E_USER, passwordConfirm: E2E_USER.password },
        });
        expect([201, 409]).toContain(created.status());
        const login = await request.post(apiUrl('/api/v1/auth/login'), {
          data: { email: E2E_USER.email, password: E2E_USER.password },
        });
        expect(login.status(), await login.text()).toBe(200);
        token = (await login.json()).accessToken;
      }
      await page.addInitScript(([key, value]) => window.sessionStorage.setItem(key, value), [
        SESSION_STORAGE_KEY,
        token,
      ] as const);
      await use(token);
    },
    { auto: true },
  ],
});

export { expect };
export type { Page } from '@playwright/test';
