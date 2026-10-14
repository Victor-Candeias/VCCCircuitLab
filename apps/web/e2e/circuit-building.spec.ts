import { expect, test, type Page } from './auth';

/**
 * E4-05, cenários 1-2 (`Docs/arquitetura_simulador_circuitos.md` §12): criar um circuito do
 * zero a partir da paleta (clique, sem arrastar — também acessível por teclado) e ligar os
 * terminais por clique, em série e em paralelo.
 */

/** Afasta um nó do ponto onde nasceu (todos no centro da vista, sobrepostos). */
async function moveNode(page: Page, id: string, x: number, y: number) {
  const node = page.locator(`[data-testid="rf__node-${id}"]`);
  const box = await node.boundingBox();
  if (!box) throw new Error(`nó ${id} não encontrado`);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(x, y, { steps: 5 });
  await page.mouse.up();
}

/**
 * Reduz o zoom (os componentes nascem todos no mesmo ponto, à escala inicial grande demais
 * para os afastar sem sobreposição) e depois afasta cada nó, do pintado por cima para baixo,
 * para que o arrasto de um nó ainda sobreposto não acerte sem querer noutro por mover.
 */
async function spreadOut(page: Page, idsTopToBottom: readonly string[], positions: [number, number][]) {
  for (let i = 0; i < 8; i++) {
    await page.locator('.react-flow__controls-zoomout').click();
  }
  for (let i = 0; i < idsTopToBottom.length; i++) {
    await moveNode(page, idsTopToBottom[i], positions[i][0], positions[i][1]);
  }
}

test('série: fonte, duas resistências e terra ligadas em cadeia', async ({ page }) => {
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto('/');
  // A app arranca com um circuito de demonstração; "Novo" dá um canvas vazio para construir.
  await page.getByRole('button', { name: 'Novo' }).click();

  await page.getByRole('button', { name: 'Adicionar Fonte de tensão DC' }).click();
  await page.getByRole('button', { name: 'Adicionar Resistência' }).click();
  await page.getByRole('button', { name: 'Adicionar Resistência' }).click();
  await page.getByRole('button', { name: 'Adicionar Terra' }).click();

  await spreadOut(
    page,
    ['GND1', 'R2', 'R1', 'V1'],
    [
      [700, 300],
      [580, 300],
      [420, 300],
      [260, 300],
    ],
  );

  const pin = (ref: string) => page.getByRole('button', { name: `Terminal ${ref}` });

  await pin('V1.positive').click();
  await pin('R1.a').click();
  await pin('R1.b').click();
  await pin('R2.a').click();
  await pin('R2.b').click();
  await pin('V1.negative').click();
  await pin('GND1.gnd').click();
  await pin('V1.negative').click();

  await expect(page.locator('path.wire-edge')).toHaveCount(4);
});

test('paralelo: duas resistências entre os mesmos dois terminais', async ({ page }) => {
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto('/');
  await page.getByRole('button', { name: 'Novo' }).click();

  await page.getByRole('button', { name: 'Adicionar Fonte de tensão DC' }).click();
  await page.getByRole('button', { name: 'Adicionar Resistência' }).click();
  await page.getByRole('button', { name: 'Adicionar Resistência' }).click();
  await page.getByRole('button', { name: 'Adicionar Terra' }).click();

  await spreadOut(
    page,
    ['GND1', 'R2', 'R1', 'V1'],
    [
      [680, 300],
      [480, 400],
      [480, 200],
      [260, 300],
    ],
  );

  const pin = (ref: string) => page.getByRole('button', { name: `Terminal ${ref}` });

  // R1 e R2 ligam-se entre os dois mesmos nós (positivo da fonte e negativo/terra): paralelo.
  await pin('V1.positive').click();
  await pin('R1.a').click();
  await pin('V1.positive').click();
  await pin('R2.a').click();
  await pin('R1.b').click();
  await pin('V1.negative').click();
  await pin('R2.b').click();
  await pin('V1.negative').click();
  await pin('GND1.gnd').click();
  await pin('V1.negative').click();

  await expect(page.locator('path.wire-edge')).toHaveCount(5);
});
