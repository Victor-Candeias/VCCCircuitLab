import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { describe, test } from 'node:test';
import Ajv2020 from 'ajv/dist/2020.js';
import { generateTypes, targets } from '../scripts/generate-types.mjs';

const readJson = async (url) => JSON.parse(await readFile(url, 'utf8'));

const schema = await readJson(new URL('../schema/circuit.schema.json', import.meta.url));
const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true });
const validate = ajv.compile(schema);

const validDir = new URL('./fixtures/valid/', import.meta.url);
const validFixtures = (await readdir(validDir)).filter((f) => f.endsWith('.json'));
const base = await readJson(new URL('fonte-resistencia.json', validDir));

const mutate = (fn) => {
  const doc = structuredClone(base);
  fn(doc);
  return doc;
};

describe('documentos válidos', () => {
  test('existem fixtures válidas', () => assert.ok(validFixtures.length > 0));

  for (const file of validFixtures) {
    test(file, async () => {
      const doc = await readJson(new URL(file, validDir));
      assert.ok(validate(doc), JSON.stringify(validate.errors, null, 2));
    });
  }

  test('nets e junctions são opcionais', () => {
    assert.ok(validate(mutate((d) => delete d.nets)), JSON.stringify(validate.errors));
  });
});

describe('documentos inválidos', () => {
  const cases = {
    'schemaVersion diferente de 1.0': (d) => (d.schemaVersion = '2.0'),
    'sem schemaVersion': (d) => delete d.schemaVersion,
    'units diferente de SI': (d) => (d.units = 'imperial'),
    'propriedade desconhecida na raiz': (d) => (d.extra = true),
    'ID de componente com ponto': (d) => (d.components[0].id = 'V.1'),
    'ID de componente a começar por dígito': (d) => (d.components[0].id = '1V'),
    'tipo de componente fora de snake_case': (d) => (d.components[0].type = 'DCVoltageSource'),
    'rotação não múltipla de 90': (d) => (d.components[0].rotation = 45),
    'propriedade com valor string': (d) => (d.components[1].properties.resistanceOhm = '100'),
    'nome de propriedade inválido': (d) => (d.components[1].properties['resistance-ohm'] = 100),
    'componente sem pinos': (d) => (d.components[0].pins = []),
    'pinos duplicados': (d) => (d.components[0].pins = ['a', 'a']),
    'posição sem y': (d) => delete d.components[0].position.y,
    'fio sem waypoints': (d) => delete d.wires[0].waypoints,
    'extremidade de fio com dois pontos': (d) => (d.wires[0].from = 'V1.positive.x'),
    'terminal de rede sem pino': (d) => (d.nets[0].terminals = ['V1']),
    'rede sem terminais': (d) => (d.nets[0].terminals = []),
    'junção sem posição': (d) => (d.junctions = [{ id: 'J1' }]),
  };

  for (const [name, fn] of Object.entries(cases)) {
    test(name, () => assert.equal(validate(mutate(fn)), false));
  }
});

describe('tipos gerados sincronizados com os schemas', () => {
  for (const target of targets) {
    test(target.name, async () => {
      const expected = await generateTypes(target);
      const actual = await readFile(target.typesUrl, 'utf8');
      assert.equal(
        actual.replace(/\r\n/g, '\n'),
        expected.replace(/\r\n/g, '\n'),
        'Executar: pnpm --filter @vcccircuitlab/circuit-schema generate',
      );
    });
  }
});
