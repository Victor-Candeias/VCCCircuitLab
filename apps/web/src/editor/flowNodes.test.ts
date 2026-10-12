import { describe, expect, test } from 'vitest';
import { demoCircuit } from './demoCircuit';
import { toFlowNodes } from './flowNodes';

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
    expect(node).toMatchObject({ width: 40, height: 40 });
  });
});
