import { describe, expect, test } from 'vitest';
import {
  defaultGenerateValues,
  GENERATE_TEMPLATES,
  parseGenerateParameters,
} from './generateTemplates';

const seriesDc = GENERATE_TEMPLATES.find((t) => t.id === 'series_dc')!;
const switchCircuit = GENERATE_TEMPLATES.find((t) => t.id === 'switch_circuit')!;

describe('generateTemplates', () => {
  test('existem os 4 templates conhecidos pela API', () => {
    expect(GENERATE_TEMPLATES.map((t) => t.id)).toEqual([
      'series_dc',
      'parallel_dc',
      'voltage_divider',
      'switch_circuit',
    ]);
  });

  test('defaultGenerateValues devolve os valores por omissão de cada campo', () => {
    expect(defaultGenerateValues(seriesDc)).toEqual({ voltageV: '12', resistorsOhm: '100, 220' });
  });

  test('parseGenerateParameters converte números e listas de resistências', () => {
    const result = parseGenerateParameters(seriesDc, {
      voltageV: '9',
      resistorsOhm: '100, 220, 330',
    });
    expect(result).toEqual({
      ok: true,
      parameters: { voltageV: 9, resistorsOhm: [100, 220, 330] },
    });
  });

  test('parseGenerateParameters converte o checkbox "closed" para booleano', () => {
    const result = parseGenerateParameters(switchCircuit, {
      voltageV: '12',
      loadOhm: '100',
      closed: 'true',
    });
    expect(result).toEqual({
      ok: true,
      parameters: { voltageV: 12, loadOhm: 100, closed: true },
    });

    const open = parseGenerateParameters(switchCircuit, {
      voltageV: '12',
      loadOhm: '100',
      closed: 'false',
    });
    expect(open).toMatchObject({ ok: true, parameters: { closed: false } });
  });

  test('parseGenerateParameters rejeita um número inválido', () => {
    const result = parseGenerateParameters(seriesDc, { voltageV: 'abc', resistorsOhm: '100' });
    expect(result).toMatchObject({ ok: false });
  });

  test('parseGenerateParameters rejeita uma lista de resistências vazia ou malformada', () => {
    expect(parseGenerateParameters(seriesDc, { voltageV: '12', resistorsOhm: '' })).toMatchObject({
      ok: false,
    });
    expect(
      parseGenerateParameters(seriesDc, { voltageV: '12', resistorsOhm: '100, abc' }),
    ).toMatchObject({ ok: false });
  });
});
