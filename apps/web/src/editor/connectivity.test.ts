import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import ramificadoJson from '@vcccircuitlab/circuit-schema/examples/ramificado.json';
import { describe, expect, test } from 'vitest';
import { deriveConnectivity } from './connectivity';
import { demoCircuit } from './demoCircuit';
import { commitWire } from './wiring';

const ramificado = ramificadoJson as unknown as CircuitDocument;

describe('deriveConnectivity', () => {
  test('circuito ramificado: as mesmas redes, pela mesma ordem, que o normalizador da API', () => {
    expect(deriveConnectivity(ramificado).nets).toEqual([
      ['V1.positive', 'S1.a'],
      ['V1.negative', 'R1.b', 'H1.b', 'R3.b', 'R4.b', 'GND1.gnd'],
      ['S1.b', 'R1.a', 'R2.a', 'R3.a'],
      ['R2.b', 'H1.a', 'R4.a'],
    ]);
  });

  test('o cruzamento sem junção (W8 × W11) não liga as redes', () => {
    const { netOfWire } = deriveConnectivity(ramificado);
    expect(netOfWire.get('W8')).toBe(3);
    expect(netOfWire.get('W11')).toBe(1);
  });

  test('junções e fios ficam associados à rede que ligam', () => {
    const { netOfJunction, netOfWire } = deriveConnectivity(ramificado);
    expect(Object.fromEntries(netOfJunction)).toEqual({ J1: 2, J2: 2, J3: 1, J4: 1, J5: 1 });
    expect(netOfWire.get('W4')).toBe(2);
    expect(netOfWire.get('W13')).toBe(1);
    expect(netOfWire.size).toBe(ramificado.wires.length);
  });

  test('terminais sem fios são redes singulares', () => {
    const { nets, netOfTerminal } = deriveConnectivity({ ...demoCircuit, wires: [] });
    expect(nets).toHaveLength(7);
    expect(netOfTerminal.get('GND1.gnd')).toBe(6);
  });

  test('ligar um fio a meio de um ramo junta as redes através da nova junção', () => {
    // Ponte de R2.b (rede intermédia) a meio do fio W4 (rede depois do interruptor).
    const next = commitWire(
      ramificado,
      { start: { kind: 'terminal', ref: 'R2.b' }, waypoints: [] },
      { kind: 'wire', wireId: 'W4', point: { x: 360, y: 120 } },
    );
    const { nets, netOfJunction } = deriveConnectivity(next!);
    expect(nets).toHaveLength(3);
    expect(nets[2]).toEqual(['S1.b', 'R1.a', 'R2.a', 'R2.b', 'H1.a', 'R3.a', 'R4.a']);
    expect(netOfJunction.get('J6')).toBe(2);
  });

  test('ignora extremidades inexistentes e junções isoladas', () => {
    const { nets, netOfJunction, netOfWire } = deriveConnectivity({
      ...demoCircuit,
      junctions: [{ id: 'J9', position: { x: 0, y: 0 } }],
      wires: [...demoCircuit.wires, { id: 'W9', from: 'X1.a', to: 'J9', waypoints: [] }],
    });
    expect(nets).toHaveLength(3);
    expect(netOfJunction.has('J9')).toBe(false);
    expect(netOfWire.has('W9')).toBe(false);
  });
});
