import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import paraleloJson from '@vcccircuitlab/circuit-schema/examples/paralelo-juncao.json';
import { describe, expect, test } from 'vitest';
import { demoCircuit } from './demoCircuit';
import { copyFragment, deleteElements, pasteFragment } from './editing';

const paralelo = paraleloJson as unknown as CircuitDocument;
const ids = (items: { id: string }[] | undefined) => (items ?? []).map((i) => i.id);

describe('deleteElements', () => {
  test('apagar um componente apaga os fios ligados aos seus terminais', () => {
    const next = deleteElements(demoCircuit, ['R1']);
    expect(ids(next.components)).toEqual(['V1', 'H1', 'GND1']);
    expect(ids(next.wires)).toEqual(['W3', 'W4']);
    expect(next).not.toHaveProperty('junctions');
  });

  test('apagar uma junção apaga os fios que nela terminam', () => {
    const next = deleteElements(paralelo, ['J1']);
    expect(ids(next.junctions)).toEqual(['J2']);
    expect(ids(next.wires)).toEqual(['W1', 'W5', 'W6', 'W7', 'W8']);
  });

  test('apagar só um fio mantém componentes e junções ainda usadas', () => {
    const next = deleteElements(paralelo, ['W4']);
    expect(ids(next.wires)).not.toContain('W4');
    expect(ids(next.junctions)).toEqual(['J1', 'J2']);
    expect(next.components).toEqual(paralelo.components);
  });

  test('junções que ficam sem fios são apagadas', () => {
    const next = deleteElements(paralelo, ['R1', 'R2']);
    // J1 continua ligada a W2 (S1.b); J2 continua ligada a W7 (V1.negative).
    expect(ids(next.junctions)).toEqual(['J1', 'J2']);
    const isolated = deleteElements(paralelo, ['W2', 'W3', 'W4']);
    expect(ids(isolated.junctions)).toEqual(['J2']);
  });

  test('sem nada para apagar devolve o mesmo documento', () => {
    expect(deleteElements(demoCircuit, [])).toBe(demoCircuit);
    expect(deleteElements(demoCircuit, ['X9'])).toBe(demoCircuit);
  });
});

describe('copyFragment', () => {
  test('copia os componentes e só os fios com as duas extremidades na seleção', () => {
    const fragment = copyFragment(demoCircuit, ['V1', 'R1', 'GND1']);
    expect(ids(fragment?.components)).toEqual(['V1', 'R1', 'GND1']);
    expect(ids(fragment?.wires)).toEqual(['W1', 'W4']);
    expect(fragment?.components[0]).not.toBe(demoCircuit.components[0]);
  });

  test('inclui junções selecionadas e os fios entre elas e os componentes', () => {
    const fragment = copyFragment(paralelo, ['J1', 'R1', 'R2']);
    expect(ids(fragment?.junctions)).toEqual(['J1']);
    expect(ids(fragment?.wires)).toEqual(['W3', 'W4']);
  });

  test('sem componentes nem junções não há nada para copiar', () => {
    expect(copyFragment(demoCircuit, [])).toBeUndefined();
    expect(copyFragment(demoCircuit, ['W1'])).toBeUndefined();
  });
});

describe('pasteFragment', () => {
  test('cola com novos IDs estáveis, deslocado, com os fios religados às cópias', () => {
    const fragment = copyFragment(paralelo, ['J1', 'R1', 'R2'])!;
    const { circuit, ids: pasted } = pasteFragment(paralelo, fragment, { x: 40, y: 40 });

    expect(pasted).toEqual(['R3', 'R4', 'J3']);
    expect(circuit.components.slice(-2)).toMatchObject([
      {
        id: 'R3',
        type: 'resistor',
        position: { x: 360, y: 240 },
        properties: { resistanceOhm: 220 },
      },
      { id: 'R4', position: { x: 480, y: 240 }, properties: { resistanceOhm: 330.5 } },
    ]);
    expect(circuit.junctions?.at(-1)).toEqual({ id: 'J3', position: { x: 360, y: 120 } });
    expect(circuit.wires.slice(-2)).toEqual([
      { id: 'W9', from: 'J3', to: 'R3.a', waypoints: [] },
      { id: 'W10', from: 'J3', to: 'R4.a', waypoints: [{ x: 480, y: 120 }] },
    ]);
    // O original não muda.
    expect(paralelo.components).toHaveLength(5);
  });

  test('colar várias vezes gera sempre IDs novos', () => {
    const fragment = copyFragment(demoCircuit, ['R1'])!;
    const first = pasteFragment(demoCircuit, fragment, { x: 40, y: 40 });
    const second = pasteFragment(first.circuit, fragment, { x: 80, y: 80 });
    expect(second.ids).toEqual(['R3']);
    expect(second.circuit).not.toHaveProperty('junctions');
  });

  test('as propriedades coladas são cópias independentes', () => {
    const fragment = copyFragment(demoCircuit, ['R1'])!;
    const { circuit } = pasteFragment(demoCircuit, fragment, { x: 0, y: 0 });
    expect(circuit.components.at(-1)!.properties).not.toBe(fragment.components[0].properties);
  });
});
