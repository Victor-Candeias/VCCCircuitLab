import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { describe, expect, test } from 'vitest';
import fonteResistencia from '../../../../packages/circuit-schema/test/fixtures/valid/fonte-resistencia.json';
import paraleloJuncao from '../../../../packages/circuit-schema/test/fixtures/valid/paralelo-juncao.json';
import { demoCircuit } from '../editor/demoCircuit';
import {
  circuitFileName,
  MAX_IMPORT_BYTES,
  parseCircuit,
  readCircuitFile,
  serializeCircuit,
  toCanonical,
} from './circuitJson';

const fixtures = {
  demo: demoCircuit,
  'fonte-resistencia': fonteResistencia as unknown as CircuitDocument,
  'paralelo-juncao': paraleloJuncao as unknown as CircuitDocument,
};

const clone = (): CircuitDocument => structuredClone(demoCircuit);

const errorsOf = (circuit: unknown): string[] => {
  const result = parseCircuit(JSON.stringify(circuit));
  if (result.ok) throw new Error('esperava erros');
  return result.errors;
};

describe('circuitJson — round-trip', () => {
  test.each(Object.entries(fixtures))(
    'exportar → importar preserva topologia e parâmetros (%s)',
    (_, circuit) => {
      const text = serializeCircuit(circuit);
      const result = parseCircuit(text);
      expect(result.ok).toBe(true);
      if (!result.ok) return;
      // `toEqual` ignora propriedades `undefined`: compara tudo exceto o `nets` derivado.
      expect(result.circuit).toEqual({ ...circuit, nets: undefined });
      expect(result.circuit).not.toHaveProperty('nets');
      // Reexportar o importado dá exatamente o mesmo ficheiro (formato estável).
      expect(serializeCircuit(result.circuit)).toBe(text);
    },
  );

  test('o ficheiro é JSON indentado, com chaves na ordem canónica e nova linha final', () => {
    const shuffled = {
      wires: [],
      units: 'SI',
      components: [],
      name: 'X',
      id: 'x',
      schemaVersion: '1.0',
    };
    const text = serializeCircuit(shuffled as CircuitDocument);
    expect(text).toBe(
      '{\n  "schemaVersion": "1.0",\n  "id": "x",\n  "name": "X",\n  "units": "SI",\n' +
        '  "components": [],\n  "wires": []\n}\n',
    );
  });

  test('toCanonical omite junções vazias e o nets derivado', () => {
    const canonical = toCanonical({
      ...demoCircuit,
      junctions: [],
      nets: [{ id: 'N1', terminals: ['V1.positive'] }],
    });
    expect(canonical).not.toHaveProperty('junctions');
    expect(canonical).not.toHaveProperty('nets');
  });

  test('importar um ficheiro com nets avisa que foram ignoradas', () => {
    const result = parseCircuit(JSON.stringify(fonteResistencia));
    expect(result.ok && result.circuit.nets).toBeUndefined();
    expect(result.ok && result.warnings).toEqual([expect.stringMatching(/nets.*ignoradas/)]);
  });
});

describe('circuitJson — validação na importação', () => {
  test('JSON inválido', () => {
    const result = parseCircuit('{ "schemaVersion": ');
    expect(result).toEqual({ ok: false, errors: [expect.stringMatching(/^JSON inválido/)] });
  });

  test('erros de schema com caminho e mensagem em português', () => {
    const circuit = clone() as unknown as Record<string, unknown>;
    circuit.schemaVersion = '2.0';
    circuit.extra = true;
    delete circuit.wires;
    const errors = errorsOf(circuit);
    expect(errors).toContain('(raiz): propriedade não permitida "extra"');
    expect(errors).toContain('(raiz): falta a propriedade obrigatória "wires"');
    expect(errors).toContain('/schemaVersion: valor inválido (esperado "1.0")');
  });

  test('IDs duplicados entre tipos de elemento', () => {
    const circuit = clone();
    circuit.wires[0].id = 'R1';
    expect(errorsOf(circuit)).toContain(
      '/wires/0: ID duplicado "R1" (os IDs são únicos no documento)',
    );
  });

  test('tipo de componente e pinos fora do catálogo', () => {
    const circuit = clone();
    circuit.components[1] = { ...circuit.components[1], pins: ['a', 'x'] };
    circuit.wires = [];
    const errors = errorsOf(circuit);
    expect(errors).toContain('/components/1: pinos desconhecidos para resistor: x');
    expect(errors).toContain('/components/1: faltam pinos de resistor: b');

    const unknownType = clone();
    unknownType.components[0] = { ...unknownType.components[0], type: 'transformer' };
    expect(errorsOf(unknownType)).toContain(
      '/components/0: tipo de componente desconhecido "transformer"',
    );
  });

  test('extremidades de fios inexistentes e fio ligado a si próprio', () => {
    const circuit = clone();
    circuit.wires[0] = { ...circuit.wires[0], from: 'X9.a', to: 'J7' };
    circuit.wires[1] = { ...circuit.wires[1], from: 'R1.c', to: 'R1.c' };
    const errors = errorsOf(circuit);
    expect(errors).toEqual(
      expect.arrayContaining([
        '/wires/0: componente inexistente em "X9.a"',
        '/wires/0: junção inexistente "J7"',
        '/wires/1: pino inexistente "R1.c"',
        '/wires/1: o fio liga "R1.c" a si próprio',
      ]),
    );
  });

  test('limita a lista de erros apresentada', () => {
    const circuit = clone();
    circuit.wires = Array.from({ length: 30 }, (_, i) => ({
      id: `W${i + 10}`,
      from: `X${i}.a`,
      to: 'R1.a',
      waypoints: [],
    }));
    const errors = errorsOf(circuit);
    expect(errors).toHaveLength(21);
    expect(errors[20]).toBe('… e mais 10 erro(s).');
  });

  test('readCircuitFile lê o ficheiro e recusa ficheiros demasiado grandes', async () => {
    const ok = await readCircuitFile(new Blob([serializeCircuit(demoCircuit)]));
    expect(ok.ok).toBe(true);
    const big = new Blob([new Uint8Array(MAX_IMPORT_BYTES + 1)]);
    const result = await readCircuitFile(big);
    expect(result).toEqual({ ok: false, errors: [expect.stringMatching(/demasiado grande/)] });
  });
});

describe('circuitFileName', () => {
  test('usa o nome do circuito sem acentos nem espaços', () => {
    expect(circuitFileName({ ...demoCircuit, name: 'Circuito série — Lâmpada 1' })).toBe(
      'circuito-serie-lampada-1.json',
    );
  });

  test('recorre ao id quando o nome não tem caracteres utilizáveis', () => {
    expect(circuitFileName({ ...demoCircuit, id: 'demo', name: '***' })).toBe('demo.json');
  });
});
