import type { ComponentCatalog } from '@vcccircuitlab/circuit-schema';
import catalogFixture from '@vcccircuitlab/circuit-schema/fixtures/catalog.json';
import { describe, expect, test, vi } from 'vitest';

const fixture = catalogFixture as ComponentCatalog;

/** Módulo novo, sem o catálogo injetado pelo `test/setup.ts`. */
async function freshCatalogModule() {
  vi.resetModules();
  return import('./catalog');
}

describe('catálogo carregado em runtime', () => {
  test('antes de setCatalog falha com uma mensagem clara', async () => {
    const mod = await freshCatalogModule();
    expect(mod.isCatalogLoaded()).toBe(false);
    expect(() => mod.getComponentDefinition('resistor')).toThrow('Catálogo não carregado');
    expect(() => mod.catalog.components).toThrow('Catálogo não carregado');
  });

  test('setCatalog atualiza catalog, GRID_SIZE, UNKNOWN_COMPONENT_SIZE e as definições', async () => {
    const mod = await freshCatalogModule();
    mod.setCatalog({ ...fixture, gridSize: 10 });
    expect(mod.isCatalogLoaded()).toBe(true);
    expect(mod.GRID_SIZE).toBe(10);
    expect(mod.UNKNOWN_COMPONENT_SIZE).toEqual({ width: 20, height: 20 });
    expect(mod.catalog.components).toHaveLength(fixture.components.length);
    expect(mod.getComponentDefinition('resistor')?.label).toBeTruthy();
    expect(mod.getComponentDefinition('inexistente')).toBeUndefined();
  });
});
