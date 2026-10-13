import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { describe, expect, test } from 'vitest';
import { demoCircuit } from './demoCircuit';
import {
  commitWire,
  endpointPosition,
  nearestPointOnPath,
  nextElementId,
  orthogonalize,
  pathToSvg,
  rotateOffset,
  routeTo,
  simplifyPath,
  terminalPosition,
  wirePath,
} from './wiring';

const withJunction: CircuitDocument = {
  ...demoCircuit,
  junctions: [{ id: 'J1', position: { x: 320, y: 120 } }],
};

const wire = (circuit: CircuitDocument, id: string) => circuit.wires.find((w) => w.id === id);

describe('posições de pinos e extremidades', () => {
  test('rotateOffset roda no sentido horário (eixo y para baixo)', () => {
    const up = { x: 0, y: -40 };
    expect(rotateOffset(up, 0)).toEqual({ x: 0, y: -40 });
    expect(rotateOffset(up, 90)).toEqual({ x: 40, y: 0 });
    expect(rotateOffset(up, 180)).toEqual({ x: 0, y: 40 });
    expect(rotateOffset(up, 270)).toEqual({ x: -40, y: 0 });
  });

  test('terminalPosition aplica a rotação do componente ao pino do catálogo', () => {
    expect(terminalPosition(demoCircuit, 'V1.positive')).toEqual({ x: 100, y: 160 });
    expect(terminalPosition(demoCircuit, 'R1.b')).toEqual({ x: 280, y: 120 });
    // H1 está rodada 90°: o pino `a` (à esquerda) passa para cima.
    expect(terminalPosition(demoCircuit, 'H1.a')).toEqual({ x: 360, y: 160 });
    expect(terminalPosition(demoCircuit, 'H1.b')).toEqual({ x: 360, y: 240 });
  });

  test('terminais inválidos não têm posição', () => {
    expect(terminalPosition(demoCircuit, 'R1.x')).toBeUndefined();
    expect(terminalPosition(demoCircuit, 'X9.a')).toBeUndefined();
    expect(terminalPosition(demoCircuit, 'R1')).toBeUndefined();
  });

  test('endpointPosition resolve terminais e junções', () => {
    expect(endpointPosition(withJunction, 'J1')).toEqual({ x: 320, y: 120 });
    expect(endpointPosition(withJunction, 'GND1.gnd')).toEqual({ x: 100, y: 300 });
    expect(endpointPosition(withJunction, 'J9')).toBeUndefined();
  });
});

describe('traçado ortogonal', () => {
  test('simplifyPath remove pontos repetidos e colineares', () => {
    expect(
      simplifyPath([
        { x: 0, y: 0 },
        { x: 0, y: 0 },
        { x: 20, y: 0 },
        { x: 40, y: 0 },
        { x: 40, y: 20 },
      ]),
    ).toEqual([
      { x: 0, y: 0 },
      { x: 40, y: 0 },
      { x: 40, y: 20 },
    ]);
  });

  test('routeTo insere um canto horizontal-primeiro só quando necessário', () => {
    expect(routeTo({ x: 0, y: 0 }, { x: 0, y: 40 })).toEqual([{ x: 0, y: 40 }]);
    expect(routeTo({ x: 0, y: 0 }, { x: 60, y: 40 })).toEqual([
      { x: 60, y: 0 },
      { x: 60, y: 40 },
    ]);
  });

  test('orthogonalize garante que todos os troços são horizontais ou verticais', () => {
    const path = orthogonalize([
      { x: 0, y: 0 },
      { x: 40, y: 20 },
      { x: 80, y: 20 },
    ]);
    expect(path).toEqual([
      { x: 0, y: 0 },
      { x: 40, y: 0 },
      { x: 40, y: 20 },
      { x: 80, y: 20 },
    ]);
    for (let i = 1; i < path.length; i++) {
      expect(path[i].x === path[i - 1].x || path[i].y === path[i - 1].y).toBe(true);
    }
  });

  test('wirePath segue os pinos e mantém o fio ortogonal depois de mover um componente', () => {
    const w1 = wire(demoCircuit, 'W1')!;
    expect(wirePath(demoCircuit, w1)).toEqual([
      { x: 100, y: 160 },
      { x: 100, y: 120 },
      { x: 200, y: 120 },
    ]);

    const moved = {
      ...demoCircuit,
      components: demoCircuit.components.map((c) =>
        c.id === 'R1' ? { ...c, position: { x: 240, y: 80 } } : c,
      ),
    };
    expect(wirePath(moved, w1)).toEqual([
      { x: 100, y: 160 },
      { x: 100, y: 120 },
      { x: 200, y: 120 },
      { x: 200, y: 80 },
    ]);
    expect(wirePath(moved, { ...w1, to: 'X9.a' })).toBeUndefined();
  });

  test('pathToSvg gera um caminho SVG', () => {
    expect(
      pathToSvg([
        { x: 0, y: 0 },
        { x: 20, y: 0 },
      ]),
    ).toBe('M 0 0 L 20 0');
  });

  test('nearestPointOnPath projeta no troço mais próximo e encaixa na grelha', () => {
    const path = wirePath(demoCircuit, wire(demoCircuit, 'W2')!)!;
    expect(nearestPointOnPath(path, { x: 321, y: 128 }, 20)).toEqual({
      point: { x: 320, y: 120 },
      segment: 0,
    });
    expect(nearestPointOnPath(path, { x: 371, y: 141 }, 20)).toEqual({
      point: { x: 360, y: 140 },
      segment: 1,
    });
    // Fora do troço: fica limitado à extremidade.
    expect(nearestPointOnPath(path, { x: 500, y: 300 }, 20)?.point).toEqual({ x: 360, y: 160 });
  });
});

describe('criação de fios e junções', () => {
  test('nextElementId devolve o próximo número livre em todo o documento', () => {
    expect(nextElementId(demoCircuit, 'W')).toBe('W5');
    expect(nextElementId(demoCircuit, 'J')).toBe('J1');
    expect(nextElementId(withJunction, 'J')).toBe('J2');
  });

  test('liga dois terminais com waypoints ortogonais', () => {
    const next = commitWire(
      demoCircuit,
      { start: { kind: 'terminal', ref: 'GND1.gnd' }, waypoints: [{ x: 200, y: 300 }] },
      { kind: 'terminal', ref: 'R1.b' },
    );
    expect(next?.wires.at(-1)).toEqual({
      id: 'W5',
      from: 'GND1.gnd',
      to: 'R1.b',
      waypoints: [{ x: 280, y: 300 }],
    });
    expect(next?.junctions).toBeUndefined();
  });

  test('rejeita ligar uma extremidade a si própria ou extremidades inexistentes', () => {
    const draft = { start: { kind: 'terminal', ref: 'R1.a' } as const, waypoints: [] };
    expect(commitWire(demoCircuit, draft, { kind: 'terminal', ref: 'R1.a' })).toBeUndefined();
    expect(commitWire(demoCircuit, draft, { kind: 'terminal', ref: 'R1.z' })).toBeUndefined();
    expect(commitWire(demoCircuit, draft, { kind: 'junction', id: 'J9' })).toBeUndefined();
  });

  test('terminar num fio cria uma junção explícita e divide o fio em dois', () => {
    const next = commitWire(
      demoCircuit,
      { start: { kind: 'terminal', ref: 'GND1.gnd' }, waypoints: [{ x: 320, y: 300 }] },
      { kind: 'wire', wireId: 'W2', point: { x: 320, y: 120 } },
    )!;

    expect(next.junctions).toEqual([{ id: 'J1', position: { x: 320, y: 120 } }]);
    expect(wire(next, 'W2')).toEqual({ id: 'W2', from: 'R1.b', to: 'J1', waypoints: [] });
    expect(wire(next, 'W5')).toEqual({
      id: 'W5',
      from: 'J1',
      to: 'H1.a',
      waypoints: [{ x: 360, y: 120 }],
    });
    expect(wire(next, 'W6')).toEqual({
      id: 'W6',
      from: 'GND1.gnd',
      to: 'J1',
      waypoints: [{ x: 320, y: 300 }],
    });
    // O traçado dos dois troços reproduz o fio original (a junção fica sobre ele).
    const halves = [...wirePath(next, wire(next, 'W2')!)!, ...wirePath(next, wire(next, 'W5')!)!];
    expect(simplifyPath(halves)).toEqual(wirePath(demoCircuit, wire(demoCircuit, 'W2')!));
  });

  test('um ponto na extremidade de um fio liga a essa extremidade, sem nova junção', () => {
    const next = commitWire(
      demoCircuit,
      { start: { kind: 'terminal', ref: 'GND1.gnd' }, waypoints: [] },
      { kind: 'wire', wireId: 'W2', point: { x: 280, y: 120 } },
    )!;
    expect(next.junctions).toBeUndefined();
    expect(wire(next, 'W5')).toMatchObject({ from: 'GND1.gnd', to: 'R1.b' });
  });

  test('começar e terminar em fios diferentes cria duas junções', () => {
    const next = commitWire(
      demoCircuit,
      { start: { kind: 'wire', wireId: 'W2', point: { x: 320, y: 120 } }, waypoints: [] },
      { kind: 'wire', wireId: 'W3', point: { x: 320, y: 260 } },
    )!;
    expect(next.junctions?.map((j) => j.id)).toEqual(['J1', 'J2']);
    expect(next.wires.at(-1)).toMatchObject({ from: 'J1', to: 'J2', waypoints: [] });
    expect(next.wires).toHaveLength(7);
  });

  test('não liga um fio a si próprio', () => {
    expect(
      commitWire(
        demoCircuit,
        { start: { kind: 'wire', wireId: 'W2', point: { x: 300, y: 120 } }, waypoints: [] },
        { kind: 'wire', wireId: 'W2', point: { x: 360, y: 140 } },
      ),
    ).toBeUndefined();
  });

  test('cruzar um fio sem junção não o liga: o fio existente fica intacto', () => {
    // GND1.gnd → (320, 300) → (320, 40) → R1.a cruza o fio W2 em (320, 120).
    const next = commitWire(
      demoCircuit,
      {
        start: { kind: 'terminal', ref: 'GND1.gnd' },
        waypoints: [
          { x: 320, y: 300 },
          { x: 320, y: 40 },
          { x: 200, y: 40 },
        ],
      },
      { kind: 'terminal', ref: 'R1.a' },
    )!;
    expect(next.junctions).toBeUndefined();
    expect(next.wires.slice(0, -1)).toEqual(demoCircuit.wires);
    expect(next.wires.at(-1)).toMatchObject({ from: 'GND1.gnd', to: 'R1.a' });
  });

  test('é imutável', () => {
    const before = structuredClone(demoCircuit);
    commitWire(
      demoCircuit,
      { start: { kind: 'terminal', ref: 'GND1.gnd' }, waypoints: [] },
      { kind: 'wire', wireId: 'W2', point: { x: 320, y: 120 } },
    );
    expect(demoCircuit).toEqual(before);
  });
});
