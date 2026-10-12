import { describe, expect, test } from 'vitest';
import { anchorToTopLeft, rotatedSize, snapPoint, snapToGrid, topLeftToAnchor } from './geometry';

describe('geometria do editor', () => {
  test('snapToGrid arredonda ao múltiplo mais próximo', () => {
    expect(snapToGrid(29, 20)).toBe(20);
    expect(snapToGrid(31, 20)).toBe(40);
    expect(snapToGrid(-9, 20)).toBe(0);
    expect(Object.is(snapToGrid(-9, 20), -0)).toBe(false);
    expect(snapPoint({ x: 51, y: -49 }, 20)).toEqual({ x: 60, y: -40 });
  });

  test('rotação de 90°/270° troca largura e altura', () => {
    const size = { width: 80, height: 20 };
    expect(rotatedSize(size, 0)).toEqual(size);
    expect(rotatedSize(size, 180)).toEqual(size);
    expect(rotatedSize(size, 90)).toEqual({ width: 20, height: 80 });
    expect(rotatedSize(size, 270)).toEqual({ width: 20, height: 80 });
  });

  test('âncora (centro) ↔ canto superior esquerdo', () => {
    const size = { width: 80, height: 20 };
    const topLeft = anchorToTopLeft({ x: 240, y: 120 }, size);
    expect(topLeft).toEqual({ x: 200, y: 110 });
    expect(topLeftToAnchor(topLeft, size)).toEqual({ x: 240, y: 120 });
  });
});
