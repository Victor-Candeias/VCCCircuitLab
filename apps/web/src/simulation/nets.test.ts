import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import paraleloJson from '@vcccircuitlab/circuit-schema/examples/paralelo-juncao.json';
import { describe, expect, test } from 'vitest';
import { netIds } from '../editor/connectivity';
import { circuitNets, netHighlight } from './nets';

const paralelo = paraleloJson as unknown as CircuitDocument;

describe('redes com os IDs da API', () => {
  test('circuitNets numera as redes N1… pela ordem do normalizador da API', () => {
    expect(circuitNets(paralelo)).toEqual([
      { id: 'N1', terminals: ['V1.positive', 'S1.a'] },
      { id: 'N2', terminals: ['V1.negative', 'R1.b', 'R2.b', 'GND1.gnd'] },
      { id: 'N3', terminals: ['S1.b', 'R1.a', 'R2.a'] },
    ]);
    expect(circuitNets(paralelo)).toBe(circuitNets(paralelo));
  });

  test('netIds salta IDs já usados no documento', () => {
    const circuit = {
      ...paralelo,
      components: [{ ...paralelo.components[0], id: 'N1' }, ...paralelo.components.slice(1)],
    };
    expect(netIds(circuit, 3)).toEqual(['N2', 'N3', 'N4']);
  });

  test('netHighlight devolve os fios, junções e terminais da rede', () => {
    expect(netHighlight(paralelo, 'N3')).toEqual({
      wires: new Set(['W2', 'W3', 'W4']),
      junctions: new Set(['J1']),
      terminals: new Set(['S1.b', 'R1.a', 'R2.a']),
    });
    expect(netHighlight(paralelo, null)).toBeNull();
    expect(netHighlight(paralelo, 'N9')).toBeNull();
  });
});
