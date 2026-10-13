import { describe, expect, test } from 'vitest';
import { demoCircuit } from './demoCircuit';
import { toFlowEdges, toFlowNodes, toJunctionNodes } from './flowNodes';

describe('toFlowNodes', () => {
  test('um nó por componente, com tamanho do catálogo e posição pelo canto superior esquerdo', () => {
    const nodes = toFlowNodes(demoCircuit, new Set());
    expect(nodes.map((n) => n.id)).toEqual(['V1', 'R1', 'H1', 'GND1']);

    const resistor = nodes.find((n) => n.id === 'R1');
    expect(resistor).toMatchObject({
      type: 'component',
      width: 80,
      height: 20,
      position: { x: 200, y: 110 },
      selected: false,
    });
    expect(resistor?.data.definition?.type).toBe('resistor');
  });

  test('rotação de 90° troca as dimensões mantendo o centro na âncora', () => {
    const lamp = toFlowNodes(demoCircuit, new Set()).find((n) => n.id === 'H1');
    expect(lamp).toMatchObject({ width: 40, height: 80, position: { x: 340, y: 160 } });
  });

  test('marca os nós selecionados', () => {
    const nodes = toFlowNodes(demoCircuit, new Set(['V1', 'GND1']));
    expect(nodes.filter((n) => n.selected).map((n) => n.id)).toEqual(['V1', 'GND1']);
  });

  test('tipos fora do catálogo continuam visíveis, sem definição', () => {
    const circuit = {
      ...demoCircuit,
      components: [{ ...demoCircuit.components[0], id: 'X1', type: 'motor' }],
    };
    const [node] = toFlowNodes(circuit, new Set());
    expect(node.data.definition).toBeUndefined();
    expect(node.data.pins).toEqual([]);
    expect(node).toMatchObject({ width: 40, height: 40 });
  });

  test('pinos relativos ao canto superior esquerdo do nó, com a rotação aplicada', () => {
    const nodes = toFlowNodes(demoCircuit, new Set());
    expect(nodes.find((n) => n.id === 'R1')?.data.pins).toEqual([
      { id: 'a', x: 0, y: 10 },
      { id: 'b', x: 80, y: 10 },
    ]);
    expect(nodes.find((n) => n.id === 'H1')?.data.pins).toEqual([
      { id: 'a', x: 20, y: 0 },
      { id: 'b', x: 20, y: 80 },
    ]);
  });
});

describe('toJunctionNodes', () => {
  test('um nó centrado por junção, marcado se selecionado', () => {
    const circuit = { ...demoCircuit, junctions: [{ id: 'J1', position: { x: 320, y: 120 } }] };
    expect(toJunctionNodes(circuit, new Set(['J1']))).toEqual([
      expect.objectContaining({
        id: 'J1',
        type: 'junction',
        position: { x: 314, y: 114 },
        width: 12,
        height: 12,
        selected: true,
      }),
    ]);
    expect(toJunctionNodes(demoCircuit, new Set())).toEqual([]);
  });
});

describe('toFlowEdges', () => {
  test('uma aresta por fio, ligada ao pino ou à junção, com o traçado ortogonal', () => {
    const circuit = {
      ...demoCircuit,
      junctions: [{ id: 'J1', position: { x: 100, y: 280 } }],
      wires: [
        ...demoCircuit.wires,
        { id: 'W5', from: 'J1', to: 'GND1.gnd', waypoints: [] },
        { id: 'W6', from: 'J9', to: 'R1.a', waypoints: [] },
      ],
    };
    const edges = toFlowEdges(circuit);
    expect(edges.map((e) => e.id)).toEqual(['W1', 'W2', 'W3', 'W4', 'W5']);
    expect(edges[0]).toMatchObject({
      type: 'wire',
      source: 'V1',
      sourceHandle: 'positive',
      target: 'R1',
      targetHandle: 'a',
      data: {
        points: [
          { x: 100, y: 160 },
          { x: 100, y: 120 },
          { x: 200, y: 120 },
        ],
      },
    });
    expect(edges[4]).toMatchObject({
      source: 'J1',
      sourceHandle: 'junction',
      target: 'GND1',
      targetHandle: 'gnd',
    });
  });
});
