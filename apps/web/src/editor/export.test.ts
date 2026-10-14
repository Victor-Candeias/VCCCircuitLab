import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import type { Node } from '@xyflow/react';

const toPng = vi.fn(async () => 'data:image/png;base64,PNG');
const toSvg = vi.fn(async () => 'data:image/svg+xml;base64,SVG');
vi.mock('html-to-image', () => ({ toPng, toSvg }));

const { exportCanvasImage, printCanvas } = await import('./export');

const node = (id: string, x: number, y: number): Node => ({
  id,
  type: 'component',
  position: { x, y },
  data: {},
  width: 40,
  height: 40,
  measured: { width: 40, height: 40 },
});

describe('export', () => {
  beforeEach(() => {
    toPng.mockClear();
    toSvg.mockClear();
    document.body.innerHTML = '<div class="react-flow__viewport"></div>';
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('exportCanvasImage(png) descarrega um ficheiro .png', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await exportCanvasImage('png', [node('R1', 0, 0)], 'circuito-serie');

    expect(toPng).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    const link = click.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toBe('circuito-serie.png');
    expect(link.href).toBe('data:image/png;base64,PNG');
  });

  test('exportCanvasImage(svg) descarrega um ficheiro .svg', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await exportCanvasImage('svg', [node('R1', 0, 0)], 'circuito-serie');

    expect(toSvg).toHaveBeenCalledOnce();
    const link = click.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toBe('circuito-serie.svg');
  });

  test('sem componentes, rejeita com um erro claro', async () => {
    await expect(exportCanvasImage('png', [], 'vazio')).rejects.toThrow(/vazio/i);
  });

  test('printCanvas abre uma janela e imprime quando a imagem carrega', async () => {
    const print = vi.fn();
    const focus = vi.fn();
    const fakeDoc = document.implementation.createHTMLDocument();
    const fakeWindow = { document: fakeDoc, focus, print } as unknown as Window;
    vi.spyOn(window, 'open').mockReturnValue(fakeWindow);

    await printCanvas([node('R1', 0, 0)], 'circuito-serie');

    const img = fakeDoc.body.querySelector('img');
    expect(img).not.toBeNull();
    img?.onload?.(new Event('load'));
    expect(focus).toHaveBeenCalledOnce();
    expect(print).toHaveBeenCalledOnce();
  });
});
