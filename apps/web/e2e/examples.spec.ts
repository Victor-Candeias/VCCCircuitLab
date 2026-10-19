import { expect, test } from './auth';

/**
 * E5-06: cada exemplo do menu abre, o editor cabe no ecrã (sem scroll horizontal, com canvas
 * utilizável) e a simulação devolve resultados. Corre em todos os projetos do
 * `playwright.config.ts` — Chromium, Firefox, WebKit e tablets com toque — e também contra o
 * site publicado (`PLAYWRIGHT_BASE_URL`). Sem backend (`PLAYWRIGHT_SKIP_BACKEND=1`) não simula.
 */
const EXAMPLES = [
  'Série: fonte, resistência e lâmpada',
  'Fonte de 12 V e resistência',
  'Paralelo com junções',
  'Ramificado (ramos, ponte e cruzamento)',
  'Divisor de tensão (R1 e R2 em série)',
  'Interruptor e carga',
];

const skipBackend = process.env.PLAYWRIGHT_SKIP_BACKEND === '1';

test.beforeEach(async ({ page }) => {
  page.on('dialog', (dialog) => void dialog.accept());
  // `./` (e não `/`) para respeitar o caminho base do site publicado (`/VCCCircuitLab/`).
  await page.goto('./');
  await expect(page.locator('.react-flow')).toBeVisible();
});

for (const example of EXAMPLES) {
  test(`exemplo "${example}": abre, cabe no ecrã e simula`, async ({ page }) => {
    await page.getByLabel('Abrir exemplo').selectOption({ label: example });
    await expect(page.locator('.react-flow__node').first()).toBeVisible();
    await expect(page.locator('.project-notice.is-error')).toHaveCount(0);

    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(0);
    const canvas = await page.locator('.react-flow').boundingBox();
    expect(canvas?.width).toBeGreaterThanOrEqual(300);
    expect(canvas?.height).toBeGreaterThanOrEqual(250);
    for (const action of ['Novo', 'Guardar JSON', 'Gerar…', 'Simular']) {
      await expect(page.getByRole('button', { name: action, exact: true })).toBeVisible();
    }

    test.skip(skipBackend, 'simular precisa do backend');
    await page.getByRole('button', { name: 'Simular', exact: true }).click();
    const table = page.getByRole('table', { name: 'Resultados por componente' });
    await expect(table).toBeVisible();
    await expect(table.locator('tbody tr').first()).toContainText(/\d/);
    await expect(page.locator('.results__error')).toHaveCount(0);
  });
}

test('toque: selecionar um componente e adicionar outro pela paleta', async ({
  page,
  hasTouch,
}) => {
  test.skip(!hasTouch, 'só em dispositivos com toque (tablets)');
  await page.getByLabel('Abrir exemplo').selectOption({ label: 'Fonte de 12 V e resistência' });
  const nodes = page.locator('.react-flow__node');
  await expect(nodes.first()).toBeVisible();

  await page.locator('[aria-label^="R1 ("]').tap();
  await expect(page.getByRole('heading', { name: /Propriedades de .* \(R1\)/ })).toBeVisible();

  const before = await nodes.count();
  await page.getByRole('button', { name: 'Adicionar Resistência' }).tap();
  await expect(nodes).toHaveCount(before + 1);
});
