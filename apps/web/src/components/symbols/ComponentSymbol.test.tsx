import type { Point, Rotation } from '@vcccircuitlab/circuit-schema';
import { render } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { catalog } from '../../editor/catalog';
import { rotateOffset } from '../../editor/wiring';
import { ComponentSymbol } from './ComponentSymbol';
import { isSymbolId, SYMBOL_IDS } from './symbolIds';

const renderSymbol = (props: Parameters<typeof ComponentSymbol>[0]) =>
  render(<ComponentSymbol {...props} />).container.querySelector('svg') as SVGSVGElement;

/** Extremidades dos condutores (`symbol__lead`) em coordenadas locais, antes da rotação. */
const leadEnds = (svg: SVGSVGElement): Point[] =>
  [...svg.querySelectorAll('line.symbol__lead')].flatMap((line) => [
    { x: Number(line.getAttribute('x1')), y: Number(line.getAttribute('y1')) },
    { x: Number(line.getAttribute('x2')), y: Number(line.getAttribute('y2')) },
  ]);

describe('SYMBOL_IDS', () => {
  test('existe um símbolo para cada componente do catálogo, e só esses', () => {
    for (const def of catalog.components) {
      expect(isSymbolId(def.symbol), def.symbol).toBe(true);
    }
    // Componentes diferentes podem partilhar o desenho (ex.: `lamp` e `mains_lamp`).
    const symbols = [...new Set(catalog.components.map((def) => def.symbol))];
    expect([...SYMBOL_IDS].sort()).toEqual(symbols.sort());
  });

  test('identificadores desconhecidos não são símbolos', () => {
    expect(isSymbolId('desconhecido')).toBe(false);
    expect(isSymbolId('toString')).toBe(false);
  });
});

describe.each(catalog.components.map((def) => [def.type, def] as const))('símbolo %s', (_, def) => {
  test('cada pino do catálogo é a extremidade de um condutor do símbolo', () => {
    const ends = leadEnds(renderSymbol({ symbol: def.symbol, size: def.size }));
    for (const pin of def.pins) {
      expect(ends, `pino ${pin.id}`).toContainEqual(pin.position);
    }
  });

  test('o desenho fica dentro da caixa do catálogo', () => {
    const svg = renderSymbol({ symbol: def.symbol, size: def.size });
    const halfW = def.size.width / 2;
    const halfH = def.size.height / 2;
    for (const end of leadEnds(svg)) {
      expect(Math.abs(end.x)).toBeLessThanOrEqual(halfW);
      expect(Math.abs(end.y)).toBeLessThanOrEqual(halfH);
    }
    for (const circle of svg.querySelectorAll('circle')) {
      const r = Number(circle.getAttribute('r'));
      expect(r).toBeLessThanOrEqual(Math.min(halfW, halfH));
    }
  });
});

describe('ComponentSymbol', () => {
  const resistor = catalog.components.find((def) => def.type === 'resistor')!;

  test('viewBox centrado na âncora, com o tamanho do catálogo', () => {
    const svg = renderSymbol({ symbol: resistor.symbol, size: resistor.size });
    expect(svg).toHaveAttribute('width', '80');
    expect(svg).toHaveAttribute('height', '20');
    expect(svg).toHaveAttribute('viewBox', '-40 -10 80 20');
    expect(svg).toHaveAttribute('data-symbol', 'resistor_iec');
    expect(svg.querySelector('g')).not.toHaveAttribute('transform');
  });

  test.each<[Rotation, string, string]>([
    [90, '20', '80'],
    [180, '80', '20'],
    [270, '20', '80'],
  ])('rotação %i° roda o desenho e ajusta a caixa', (rotation, width, height) => {
    const svg = renderSymbol({ symbol: resistor.symbol, size: resistor.size, rotation });
    expect(svg).toHaveAttribute('width', width);
    expect(svg).toHaveAttribute('height', height);
    expect(svg.querySelector('g')).toHaveAttribute('transform', `rotate(${rotation})`);
  });

  test('a rotação SVG coincide com a rotação dos pinos (rotateOffset)', () => {
    // rotate(θ) no SVG (eixo y para baixo): (x, y) → (x·cosθ − y·sinθ, x·sinθ + y·cosθ).
    const svgRotate = (p: Point, deg: number): Point => {
      const rad = (deg * Math.PI) / 180;
      const round = (v: number) => Math.round(v) + 0;
      return {
        x: round(p.x * Math.cos(rad) - p.y * Math.sin(rad)),
        y: round(p.x * Math.sin(rad) + p.y * Math.cos(rad)),
      };
    };
    for (const def of catalog.components) {
      for (const pin of def.pins) {
        for (const rotation of [0, 90, 180, 270] as const) {
          expect(svgRotate(pin.position, rotation)).toEqual(rotateOffset(pin.position, rotation));
        }
      }
    }
  });

  test('o interruptor desenha o estado aberto/fechado', () => {
    const sw = catalog.components.find((def) => def.type === 'switch')!;
    const open = renderSymbol({ symbol: sw.symbol, size: sw.size, properties: { closed: false } });
    expect(open.querySelector('[data-state]')).toHaveAttribute('data-state', 'open');
    const closed = renderSymbol({ symbol: sw.symbol, size: sw.size, properties: { closed: true } });
    expect(closed.querySelector('[data-state]')).toHaveAttribute('data-state', 'closed');
  });

  test.each(['circuit_breaker', 'rcd'])('%s desenha o estado armado/aberto', (type) => {
    const def = catalog.components.find((d) => d.type === type)!;
    const armed = renderSymbol({ symbol: def.symbol, size: def.size, properties: {} });
    expect(armed.querySelector('[data-state]')).toHaveAttribute('data-state', 'closed');
    const open = renderSymbol({
      symbol: def.symbol,
      size: def.size,
      properties: { closed: false },
    });
    expect(open.querySelector('[data-state]')).toHaveAttribute('data-state', 'open');
  });

  test('o comutador desenha a posição da lâmina', () => {
    const sw = catalog.components.find((def) => def.type === 'changeover_switch')!;
    const l1 = renderSymbol({ symbol: sw.symbol, size: sw.size, properties: { toL2: false } });
    expect(l1.querySelector('[data-state]')).toHaveAttribute('data-state', 'l1');
    const l2 = renderSymbol({ symbol: sw.symbol, size: sw.size, properties: { toL2: true } });
    expect(l2.querySelector('[data-state]')).toHaveAttribute('data-state', 'l2');
  });

  test('os sinais de polaridade ficam na vertical com qualquer rotação', () => {
    const source = catalog.components.find((def) => def.type === 'dc_voltage_source')!;
    const upright = renderSymbol({ symbol: source.symbol, size: source.size });
    for (const mark of upright.querySelectorAll('.symbol__mark')) {
      expect(mark).not.toHaveAttribute('transform');
    }
    const rotated = renderSymbol({ symbol: source.symbol, size: source.size, rotation: 90 });
    const marks = [...rotated.querySelectorAll('.symbol__mark')];
    expect(marks.map((mark) => mark.getAttribute('transform'))).toEqual([
      'rotate(-90 12 -26)',
      'rotate(-90 12 26)',
    ]);
  });

  test('símbolo sem desenho registado mostra um marcador de erro', () => {
    const svg = renderSymbol({ symbol: 'motor_iec', size: { width: 40, height: 40 } });
    expect(svg.querySelector('.component-symbol__missing')).not.toBeNull();
  });
});
