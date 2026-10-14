import { expect, test } from '@playwright/test';

/**
 * E4-05: desempenho com ~100 componentes (`Docs/arquitetura_simulador_circuitos.md` §12.11).
 * Fixture gerada em `e2e/fixtures/large-circuit.json` (100 componentes, 100 fios, série única).
 * Não é um benchmark preciso — só um limite generoso para detetar regressões óbvias de
 * desempenho (p. ex. um render O(n²) acidental).
 */
test('abre e desenha um circuito com ~100 componentes num tempo aceitável', async ({ page }) => {
  await page.goto('/');

  const fixture = new URL('./fixtures/large-circuit.json', import.meta.url).pathname;
  const start = Date.now();
  await page.getByLabel('Ficheiro de circuito (JSON)').setInputFiles(fixture);
  await expect(page.locator('.react-flow__node')).toHaveCount(100);
  const elapsedMs = Date.now() - start;

  expect(elapsedMs).toBeLessThan(10_000);
  await expect(page.locator('.project-notice.is-error')).toHaveCount(0);
});
