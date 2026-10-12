import type { Point, Rotation } from '@vcccircuitlab/circuit-schema';

export interface Size {
  width: number;
  height: number;
}

/** Arredonda para o múltiplo de `grid` mais próximo (normaliza `-0` para `0`). */
export const snapToGrid = (value: number, grid: number): number =>
  Math.round(value / grid) * grid + 0;

export const snapPoint = (point: Point, grid: number): Point => ({
  x: snapToGrid(point.x, grid),
  y: snapToGrid(point.y, grid),
});

/** Caixa envolvente do símbolo depois da rotação (90°/270° trocam largura e altura). */
export const rotatedSize = (size: Size, rotation: Rotation): Size =>
  rotation === 90 || rotation === 270 ? { width: size.height, height: size.width } : size;

/** `Component.position` é o centro do símbolo; o React Flow posiciona nós pelo canto superior esquerdo. */
export const anchorToTopLeft = (anchor: Point, size: Size): Point => ({
  x: anchor.x - size.width / 2,
  y: anchor.y - size.height / 2,
});

export const topLeftToAnchor = (topLeft: Point, size: Size): Point => ({
  x: topLeft.x + size.width / 2,
  y: topLeft.y + size.height / 2,
});
