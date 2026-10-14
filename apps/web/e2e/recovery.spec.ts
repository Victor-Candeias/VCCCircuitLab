import { expect, test } from './auth';

/**
 * E4-05: recuperação do projeto após um refresh da página (E4-02: autosave em IndexedDB).
 */
test('recuperação após refresh: o circuito é restaurado com uma mensagem a confirmar', async ({
  page,
}) => {
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto('/');

  await page.getByLabel('Abrir exemplo').selectOption({ label: 'Paralelo com junções' });
  await expect(page.getByTitle('Nome do circuito')).toHaveText(
    'Duas resistências em paralelo com junções explícitas',
  );

  // Espera a gravação automática (debounce de 800 ms) antes de recarregar a página.
  await page.waitForTimeout(1200);
  await page.reload();

  await expect(page.getByTitle('Nome do circuito')).toHaveText(
    'Duas resistências em paralelo com junções explícitas',
  );
  await expect(page.getByText(/recuperado automaticamente/i)).toBeVisible();
  await expect(page.locator('.react-flow__node[data-id="R1"]')).toBeVisible();
});
