import { expect, test } from '@playwright/test';
import { E2E_USER } from './auth';

/** E5-09: sem sessão só se vê o ecrã de login; com credenciais válidas entra-se no editor. */
test('sem sessão mostra apenas o ecrã de login', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Iniciar sessão' })).toBeVisible();
  await expect(page.locator('.react-flow')).toHaveCount(0);
});

test('login pela interface abre o editor e "Terminar sessão" volta ao login', async ({
  page,
  request,
}) => {
  test.skip(process.env.PLAYWRIGHT_SKIP_BACKEND === '1', 'precisa do backend');
  const created = await request.post('/api/v1/users', {
    data: { ...E2E_USER, passwordConfirm: E2E_USER.password },
  });
  expect([201, 409]).toContain(created.status());

  await page.goto('/');
  await page.getByLabel('Email').fill(E2E_USER.email);
  await page.getByLabel('Password').fill('password-errada');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('alert')).toHaveText('Email ou password incorretos.');

  await page.getByLabel('Password').fill(E2E_USER.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByText(E2E_USER.name)).toBeVisible();
  await expect(page.locator('.react-flow')).toBeVisible();

  await page.reload();
  await expect(page.getByText(E2E_USER.name)).toBeVisible();

  await page.getByRole('button', { name: 'Terminar sessão' }).click();
  await expect(page.getByRole('heading', { name: 'Iniciar sessão' })).toBeVisible();
});
