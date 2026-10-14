import { describe, expect, test } from 'vitest';
import { formatQuantity } from './format';

describe('formatQuantity', () => {
  test.each([
    [9, 'V', '9 V'],
    [0.04090909, 'A', '40,9 mA'],
    [-0.6132650254, 'W', '-613 mW'],
    [330.5, 'Ω', '331 Ω'],
    [1500, 'Ω', '1,5 kΩ'],
    [2.2e6, 'Ω', '2,2 MΩ'],
    [0.0000012, 'A', '1,2 µA'],
    [0.99996, 'A', '1 A'],
    [999.6, 'V', '1 kV'],
    [1e-15, 'A', '0 A'],
    [-0, 'V', '0 V'],
    [Number.NaN, 'V', '—'],
  ])('%s %s → %s', (value, unit, expected) => {
    expect(formatQuantity(value, unit)).toBe(expected);
  });
});
