import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { describe, expect, test } from 'vitest';
import { catalog } from './catalog';
import { demoCircuit } from './demoCircuit';
import {
  defaultProperties,
  freeAnchor,
  placeComponent,
  rotateBy,
  rotateComponents,
} from './placement';
import { terminalPosition } from './wiring';

const empty: CircuitDocument = { ...demoCircuit, components: [], wires: [], junctions: [] };

describe('placement', () => {
  test('rotateBy roda 90° e normaliza para 0/90/180/270', () => {
    expect(rotateBy(0, 90)).toBe(90);
    expect(rotateBy(270, 90)).toBe(0);
    expect(rotateBy(0, -90)).toBe(270);
    expect(rotateBy(90, -90)).toBe(0);
  });

  test('defaultProperties usa os valores por omissão do catálogo', () => {
    const lamp = catalog.components.find((d) => d.type === 'lamp');
    expect(lamp && defaultProperties(lamp)).toEqual({ ratedVoltageV: 12, ratedPowerW: 5 });
  });

  test('placeComponent cria uma instância do catálogo com snap, rotação 0 e pinos', () => {
    const placed = placeComponent(empty, 'switch', { x: 107, y: 52 });
    expect(placed?.component).toEqual({
      id: 'S1',
      type: 'switch',
      position: { x: 100, y: 60 },
      rotation: 0,
      properties: { closed: false },
      pins: ['a', 'b'],
    });
    expect(placed?.circuit.components).toHaveLength(1);
    expect(empty.components).toHaveLength(0);
  });

  test('cada tipo do catálogo pode ser colocado e os pinos ficam na grelha', () => {
    let circuit = empty;
    for (const definition of catalog.components) {
      const placed = placeComponent(circuit, definition.type, { x: 213, y: 187 });
      expect(placed).toBeDefined();
      circuit = placed!.circuit;
      for (const pin of placed!.component.pins) {
        const p = terminalPosition(circuit, `${placed!.component.id}.${pin}`);
        expect(p && p.x % catalog.gridSize).toBe(0);
        expect(p && p.y % catalog.gridSize).toBe(0);
      }
    }
  });

  test('os IDs usam o prefixo do catálogo e são únicos em todo o documento', () => {
    expect(placeComponent(demoCircuit, 'resistor', { x: 0, y: 0 })?.component.id).toBe('R2');
    expect(placeComponent(demoCircuit, 'ground', { x: 0, y: 0 })?.component.id).toBe('GND2');
    expect(placeComponent(demoCircuit, 'dc_current_source', { x: 0, y: 0 })?.component.id).toBe(
      'I1',
    );
  });

  test('tipos fora do catálogo e coordenadas não finitas são recusados', () => {
    expect(placeComponent(empty, 'motor', { x: 0, y: 0 })).toBeUndefined();
    expect(placeComponent(empty, 'lamp', { x: Number.NaN, y: 0 })).toBeUndefined();
  });

  test('freeAnchor desloca na diagonal quando a âncora já está ocupada', () => {
    // R1 está em (240, 120).
    expect(freeAnchor(demoCircuit, { x: 243, y: 118 })).toEqual({ x: 260, y: 140 });
    expect(freeAnchor(demoCircuit, { x: 500, y: 500 })).toEqual({ x: 500, y: 500 });
  });

  test('rotateComponents roda só os componentes indicados, em torno da âncora', () => {
    const rotated = rotateComponents(demoCircuit, ['R1', 'H1', 'J9'], 90);
    const byId = (id: string) => rotated.components.find((c) => c.id === id);
    expect(byId('R1')).toMatchObject({ rotation: 90, position: { x: 240, y: 120 } });
    expect(byId('H1')?.rotation).toBe(180);
    expect(byId('V1')).toBe(demoCircuit.components.find((c) => c.id === 'V1'));
    // Resistência vertical: pinos acima e abaixo da âncora.
    expect(terminalPosition(rotated, 'R1.a')).toEqual({ x: 240, y: 80 });
    expect(terminalPosition(rotated, 'R1.b')).toEqual({ x: 240, y: 160 });
  });

  test('rotateComponents devolve o mesmo documento sem componentes afetados', () => {
    expect(rotateComponents(demoCircuit, [], 90)).toBe(demoCircuit);
    expect(rotateComponents(demoCircuit, ['X9'], -90)).toBe(demoCircuit);
  });
});
