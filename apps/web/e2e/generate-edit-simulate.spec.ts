import { expect, test } from './auth';

/**
 * E4-05, cenário "automático → manual" (`Docs/arquitetura_simulador_circuitos.md` §12.10): gerar
 * um circuito por template (API), editar uma propriedade no editor e simular — precisa do
 * backend (`uvicorn`), por isso fica de fora quando `PLAYWRIGHT_SKIP_BACKEND=1`.
 */
test.skip(process.env.PLAYWRIGHT_SKIP_BACKEND === '1', 'precisa do backend');

test('gerar → editar → simular: template série, editar R1 e ver os resultados', async ({
  page,
}) => {
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto('/');

  await page.getByRole('button', { name: 'Gerar…' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Gerar', exact: true }).click();
  await expect(dialog).toBeHidden();

  // O template "Série" por omissão gera V1, R1 e R2.
  await expect(page.locator('[aria-label^="R1 ("]')).toBeVisible();

  // Editar a resistência de R1 no painel de propriedades.
  await page.locator('[aria-label^="R1 ("]').click();
  await expect(page.getByRole('heading', { name: /Propriedades de .* \(R1\)/ })).toBeVisible();
  const resistanceInput = page.locator('input[id$="-resistanceOhm"]');
  await resistanceInput.fill('50');
  await resistanceInput.blur();
  await expect(page.locator('.properties__error')).toHaveCount(0);

  // Simular e conferir que há resultados numéricos por componente.
  await page.getByRole('button', { name: 'Simular' }).click();
  const table = page.getByRole('table', { name: 'Resultados por componente' });
  await expect(table).toBeVisible();
  const r1Row = table.locator('tr', { has: page.getByRole('button', { name: /^R1$/ }) });
  await expect(r1Row.locator('td').first()).toContainText(/\d/);

  // Guardar o circuito editado e simulado.
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Guardar JSON' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.json$/);
});
