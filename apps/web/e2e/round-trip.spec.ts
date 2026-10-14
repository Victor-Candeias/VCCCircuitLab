import { expect, test } from './auth';

/**
 * E4-05, cenário "round-trip" (`Docs/arquitetura_simulador_circuitos.md` §12.9): abrir um
 * exemplo, guardar como JSON canónico, começar um circuito novo e reabrir o ficheiro guardado —
 * a topologia e os parâmetros devem ficar iguais.
 */
test('round-trip: guardar um exemplo e reabri-lo reproduz o mesmo circuito', async ({ page }) => {
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto('/');

  await page.getByLabel('Abrir exemplo').selectOption({ label: 'Fonte de 12 V e resistência' });
  await expect(page.getByTitle('Nome do circuito')).toHaveText('Fonte e resistência');
  const nodesBefore = await page.locator('.react-flow__node').count();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Guardar JSON' }).click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).toBeTruthy();

  // Novo circuito vazio (substitui o exemplo, com confirmação) antes de reabrir o ficheiro.
  await page.getByRole('button', { name: 'Novo' }).click();
  await expect(page.getByTitle('Nome do circuito')).toHaveText('Novo circuito');

  await page.getByLabel('Ficheiro de circuito (JSON)').setInputFiles(path!);

  await expect(page.getByTitle('Nome do circuito')).toHaveText('Fonte e resistência');
  await expect(page.locator('.react-flow__node')).toHaveCount(nodesBefore);
  // Reabrir não deve gerar avisos nem mensagens de erro.
  await expect(page.locator('.project-notice.is-error')).toHaveCount(0);
});
