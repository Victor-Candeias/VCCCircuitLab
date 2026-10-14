import { getNodesBounds, getViewportForBounds, type Node } from '@xyflow/react';
import { toPng, toSvg } from 'html-to-image';

/** Margem (em px do documento) à volta dos componentes, para não cortar os fios das bordas. */
const EXPORT_PADDING = 40;

/**
 * Gera uma imagem (PNG ou SVG) do canvas enquadrando exatamente os nós existentes, reutilizando
 * o viewport do React Flow (`.react-flow__viewport`) e as suas próprias ferramentas de
 * enquadramento (`getNodesBounds`/`getViewportForBounds`), independentemente do zoom/pan atual.
 */
async function captureCanvasDataUrl(format: 'png' | 'svg', nodes: Node[]): Promise<string> {
  const viewportEl = document.querySelector<HTMLElement>('.react-flow__viewport');
  if (!viewportEl || nodes.length === 0) {
    throw new Error('Não há nada para exportar: o circuito está vazio.');
  }
  const bounds = getNodesBounds(nodes);
  const width = Math.round(bounds.width + EXPORT_PADDING * 2);
  const height = Math.round(bounds.height + EXPORT_PADDING * 2);
  const viewport = getViewportForBounds(bounds, width, height, 0.1, 2, EXPORT_PADDING);
  const render = format === 'png' ? toPng : toSvg;
  return render(viewportEl, {
    backgroundColor: '#ffffff',
    width,
    height,
    style: {
      width: `${width}px`,
      height: `${height}px`,
      transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
    },
  });
}

function downloadDataUrl(dataUrl: string, fileName: string) {
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = fileName;
  link.click();
}

/** Exporta o canvas como ficheiro PNG ou SVG, com o nome do circuito. */
export async function exportCanvasImage(
  format: 'png' | 'svg',
  nodes: Node[],
  baseName: string,
): Promise<void> {
  const dataUrl = await captureCanvasDataUrl(format, nodes);
  downloadDataUrl(dataUrl, `${baseName}.${format}`);
}

/**
 * Abre uma janela só com a imagem do circuito e invoca a impressão do browser, para o utilizador
 * imprimir ou "Guardar como PDF" (não há geração de PDF no cliente: usa-se o diálogo do browser).
 */
export async function printCanvas(nodes: Node[], title: string): Promise<void> {
  const dataUrl = await captureCanvasDataUrl('png', nodes);
  const win = window.open('', '_blank', 'noopener');
  if (!win) throw new Error('O browser bloqueou a janela de impressão.');
  win.document.title = title;
  const img = win.document.createElement('img');
  img.src = dataUrl;
  img.style.maxWidth = '100%';
  img.onload = () => {
    win.focus();
    win.print();
  };
  win.document.body.style.margin = '0';
  win.document.body.style.display = 'flex';
  win.document.body.style.justifyContent = 'center';
  win.document.body.style.alignItems = 'center';
  win.document.body.style.minHeight = '100vh';
  win.document.body.appendChild(img);
}
