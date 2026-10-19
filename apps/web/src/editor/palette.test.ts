import { describe, expect, test } from 'vitest';
import { catalog } from './catalog';
import { paletteGroups } from './palette';

const types = (query?: string) =>
  paletteGroups(query).flatMap((group) => group.items.map((item) => item.type));

describe('paletteGroups', () => {
  test('sem pesquisa, mostra todo o catálogo agrupado por categoria, pela ordem definida', () => {
    const groups = paletteGroups();
    expect(groups.map((g) => g.label)).toEqual([
      'Fontes',
      'Passivos',
      'Interruptores',
      'Cargas',
      'Referência',
    ]);
    expect(groups[0].items.map((d) => d.type)).toEqual(['dc_voltage_source', 'dc_current_source']);
    expect(types().sort()).toEqual(catalog.components.map((d) => d.type).sort());
  });

  test('pesquisa sem distinguir maiúsculas nem acentos', () => {
    expect(types('TENSAO')).toEqual(['dc_voltage_source', 'capacitor']);
    expect(types('lâmpada')).toEqual(['lamp']);
  });

  test('todas as palavras têm de ocorrer (nome, tipo, prefixo, descrição ou categoria)', () => {
    expect(types('fonte corrente')).toEqual(['dc_current_source']);
    expect(types('resistor')).toEqual(['resistor']);
    expect(types('gnd')).toEqual(['ground']);
    expect(types('fontes')).toEqual(['dc_voltage_source', 'dc_current_source']);
  });

  test('grupos sem resultados são omitidos', () => {
    expect(paletteGroups('interruptor').map((g) => g.category)).toEqual(['switch']);
    expect(paletteGroups('xyz')).toEqual([]);
  });
});
