import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { describe, test } from 'node:test';
import Ajv2020 from 'ajv/dist/2020.js';

const readJson = async (url) => JSON.parse(await readFile(url, 'utf8'));

const catalogSchema = await readJson(new URL('../schema/catalog.schema.json', import.meta.url));
const catalog = await readJson(new URL('./fixtures/catalog.json', import.meta.url));
const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true });
const validateCatalog = ajv.compile(catalogSchema);

const MVP_TYPES = [
  'dc_voltage_source',
  'dc_current_source',
  'resistor',
  'switch',
  'lamp',
  'ground',
];

const byType = new Map(catalog.components.map((c) => [c.type, c]));

const CONSTRAINT_KEYS = ['type', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum'];
const constraintsOf = (prop) =>
  Object.fromEntries(Object.entries(prop).filter(([key]) => CONSTRAINT_KEYS.includes(key)));

describe('catálogo', () => {
  test('valida contra catalog.schema.json', () => {
    assert.ok(validateCatalog(catalog), JSON.stringify(validateCatalog.errors, null, 2));
  });

  test('contém os componentes do MVP', () => {
    assert.deepEqual([...byType.keys()].sort(), [...MVP_TYPES].sort());
  });

  test('tipos e prefixos de ID são únicos', () => {
    const prefixes = catalog.components.map((c) => c.idPrefix);
    assert.equal(byType.size, catalog.components.length);
    assert.equal(new Set(prefixes).size, prefixes.length);
  });

  for (const def of catalog.components) {
    describe(def.type, () => {
      test('pinos únicos e na grelha', () => {
        const ids = def.pins.map((p) => p.id);
        assert.equal(new Set(ids).size, ids.length);
        for (const { id, position } of def.pins) {
          assert.ok(position.x % catalog.gridSize === 0, `${id}.x fora da grelha`);
          assert.ok(position.y % catalog.gridSize === 0, `${id}.y fora da grelha`);
          assert.ok(Math.abs(position.x) <= def.size.width / 2, `${id}.x fora do símbolo`);
          assert.ok(Math.abs(position.y) <= def.size.height / 2, `${id}.y fora do símbolo`);
        }
      });

      test('valores por omissão respeitam as restrições', () => {
        for (const [name, prop] of Object.entries(def.properties)) {
          const valid = ajv.validate(constraintsOf(prop), prop.default);
          assert.ok(valid, `${name}: ${JSON.stringify(ajv.errors)}`);
        }
      });
    });
  }

  test('tipos de propriedade inválidos são rejeitados', () => {
    const broken = structuredClone(catalog);
    broken.components[0].properties.voltageV.type = 'string';
    assert.equal(validateCatalog(broken), false);
  });

  test('modelo de simulação desconhecido é rejeitado', () => {
    const broken = structuredClone(catalog);
    broken.components[0].simulationModel = 'transistor';
    assert.equal(validateCatalog(broken), false);
  });
});

describe('fixtures de circuito usam o catálogo', async () => {
  const dir = new URL('./fixtures/valid/', import.meta.url);
  const files = (await readdir(dir)).filter((f) => f.endsWith('.json'));

  for (const file of files) {
    test(file, async () => {
      const doc = await readJson(new URL(file, dir));
      for (const component of doc.components) {
        const def = byType.get(component.type);
        assert.ok(def, `${component.id}: tipo desconhecido ${component.type}`);
        assert.deepEqual(
          component.pins,
          def.pins.map((p) => p.id),
          `${component.id}: pinos diferentes do catálogo`,
        );
        for (const [name, value] of Object.entries(component.properties)) {
          const prop = def.properties[name];
          assert.ok(prop, `${component.id}: propriedade desconhecida ${name}`);
          assert.ok(ajv.validate(constraintsOf(prop), value), `${component.id}.${name} inválido`);
        }
      }
    });
  }
});
