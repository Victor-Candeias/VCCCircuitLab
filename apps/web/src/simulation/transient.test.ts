import { describe, expect, test } from 'vitest';
import type { TransientResult } from '../api/types';
import { chartRows, finalValues, plotOf, sampleIndices } from './transient';

const result: TransientResult = {
  analysis: 'transient',
  status: 'success',
  timeS: [0, 1, 2],
  nodeVoltagesV: { N1: [5, 5, 5], N2: [0, 3, 4] },
  components: {
    C1: { voltageV: [0, 3, 4], currentA: [5e-3, 2e-3, 1e-3], powerW: [0, 6e-3, 4e-3] },
  },
  warnings: [],
};

describe('transient', () => {
  test('sampleIndices devolve todos os índices ou no máximo `max`, com o primeiro e o último', () => {
    expect(sampleIndices(3, 5)).toEqual([0, 1, 2]);
    const sampled = sampleIndices(10_001, 1000);
    expect(sampled.length).toBeLessThanOrEqual(1000);
    expect(sampled[0]).toBe(0);
    expect(sampled.at(-1)).toBe(10_000);
    expect(sampled[1] - sampled[0]).toBe(sampled[2] - sampled[1]);
  });

  test('plotOf: tensões das redes, ou tensão/corrente de um componente', () => {
    expect(plotOf(result, 'nets')).toEqual({
      unit: 'V',
      series: [
        { key: 'N1', label: 'N1', values: [5, 5, 5] },
        { key: 'N2', label: 'N2', values: [0, 3, 4] },
      ],
    });
    expect(plotOf(result, 'current:C1')).toEqual({
      unit: 'A',
      series: [{ key: 'C1', label: 'I(C1)', values: [5e-3, 2e-3, 1e-3] }],
    });
    expect(plotOf(result, 'voltage:C1').series[0].label).toBe('V(C1)');
  });

  test('chartRows junta o tempo e as séries por instante', () => {
    expect(chartRows(result.timeS, plotOf(result, 'nets'))).toEqual([
      { t: 0, N1: 5, N2: 0 },
      { t: 1, N1: 5, N2: 3 },
      { t: 2, N1: 5, N2: 4 },
    ]);
  });

  test('finalValues usa o último instante', () => {
    expect(finalValues(result)).toEqual({
      nodeVoltagesV: { N1: 5, N2: 4 },
      components: { C1: { voltageV: 4, currentA: 1e-3, powerW: 4e-3 } },
    });
  });
});
