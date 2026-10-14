import type { CircuitDocument, Point } from '@vcccircuitlab/circuit-schema';
import { describe, expect, test } from 'vitest';
import { GRID_SIZE } from '../editor/catalog';
import { toFlowEdges, toFlowNodes, toJunctionNodes } from '../editor/flowNodes';
import { endpointPosition } from '../editor/wiring';
import { parseCircuit, serializeCircuit } from './circuitJson';
import { CIRCUIT_EXAMPLES } from './examples';

const example = (id: string): CircuitDocument => CIRCUIT_EXAMPLES.find((e) => e.id === id)!.circuit;

/** Traçado tal como está no documento (sem os cantos acrescentados por `orthogonalize`). */
const storedPath = (circuit: CircuitDocument, wireId: string): Point[] => {
  const wire = circuit.wires.find((w) => w.id === wireId)!;
  return [
    endpointPosition(circuit, wire.from)!,
    ...wire.waypoints,
    endpointPosition(circuit, wire.to)!,
  ];
};

const segments = (points: Point[]) => points.slice(1).map((p, i) => [points[i], p] as const);

describe('CIRCUIT_EXAMPLES', () => {
  test.each(CIRCUIT_EXAMPLES.map((e) => [e.id, e.circuit] as const))(
    '%s é um documento válido, sem nets, que sobrevive ao round-trip',
    (_, circuit) => {
      expect(circuit).not.toHaveProperty('nets');
      const result = parseCircuit(serializeCircuit(circuit));
      expect(result).toEqual({ ok: true, circuit, warnings: [] });
    },
  );

  test('os IDs dos exemplos são únicos', () => {
    const ids = CIRCUIT_EXAMPLES.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('protótipo ramificado (§5.2)', () => {
  const circuit = example('ramificado');

  test('tem vários ramos, cinco junções (uma de quatro fios) e uma ponte', () => {
    expect(circuit.components.map((c) => c.id)).toEqual([
      'V1',
      'S1',
      'R1',
      'R2',
      'H1',
      'R3',
      'R4',
      'GND1',
    ]);
    expect(circuit.junctions).toHaveLength(5);
    const wiresAt = (id: string) => circuit.wires.filter((w) => w.from === id || w.to === id);
    expect(wiresAt('J3').map((w) => w.id)).toEqual(['W9', 'W14', 'W15', 'W16']);
  });

  test('desenho limpo: tudo na grelha e todos os troços já ortogonais', () => {
    const onGrid = (p: Point) => p.x % GRID_SIZE === 0 && p.y % GRID_SIZE === 0;
    for (const wire of circuit.wires) {
      const path = storedPath(circuit, wire.id);
      expect(path.every(onGrid), wire.id).toBe(true);
      for (const [a, b] of segments(path)) expect(a.x === b.x || a.y === b.y, wire.id).toBe(true);
    }
  });

  test('W8 cruza W11 em (540, 240), que não é extremidade de nenhum dos dois', () => {
    const [horizontal] = segments(storedPath(circuit, 'W8'));
    const [vertical] = segments(storedPath(circuit, 'W11'));
    expect(horizontal[0].y).toBe(240);
    expect(Math.min(horizontal[0].x, horizontal[1].x)).toBeLessThan(540);
    expect(Math.max(horizontal[0].x, horizontal[1].x)).toBeGreaterThan(540);
    expect(vertical[0].x).toBe(540);
    expect(Math.min(vertical[0].y, vertical[1].y)).toBeLessThan(240);
    expect(Math.max(vertical[0].y, vertical[1].y)).toBeGreaterThan(240);
  });

  test('o React Flow recebe um nó por componente e junção e uma aresta por fio', () => {
    expect(toFlowNodes(circuit, new Set())).toHaveLength(8);
    expect(toJunctionNodes(circuit, new Set())).toHaveLength(5);
    const edges = toFlowEdges(circuit);
    expect(edges).toHaveLength(16);
    expect(edges.find((e) => e.id === 'W14')).toMatchObject({ source: 'J4', target: 'J3' });
  });
});
