import type { ComponentCatalog, ComponentDefinition } from '@vcccircuitlab/circuit-schema';
import type { Size } from './geometry';

/**
 * Catálogo de componentes carregado em runtime de `GET /api/v1/components` (F2-11). A app chama
 * `setCatalog()` no arranque, antes de montar o editor; os consumidores continuam a ler
 * `catalog`/`GRID_SIZE`/`UNKNOWN_COMPONENT_SIZE` (live bindings ESM) e `getComponentDefinition`
 * de forma síncrona.
 */
const NOT_LOADED = 'Catálogo não carregado: chamar setCatalog() antes de usar o editor.';

const notLoaded = new Proxy({} as ComponentCatalog, {
  get() {
    throw new Error(NOT_LOADED);
  },
});

export let catalog: ComponentCatalog = notLoaded;

export let GRID_SIZE = Number.NaN;

/** Tamanho usado para tipos fora do catálogo (desenhados como marcador de erro). */
export let UNKNOWN_COMPONENT_SIZE: Size = { width: Number.NaN, height: Number.NaN };

let definitionsByType: Map<string, ComponentDefinition> | null = null;

export function setCatalog(next: ComponentCatalog): void {
  catalog = next;
  GRID_SIZE = next.gridSize;
  UNKNOWN_COMPONENT_SIZE = { width: 2 * GRID_SIZE, height: 2 * GRID_SIZE };
  definitionsByType = new Map(next.components.map((def) => [def.type, def]));
}

export const isCatalogLoaded = (): boolean => definitionsByType !== null;

export function getComponentDefinition(type: string): ComponentDefinition | undefined {
  if (!definitionsByType) throw new Error(NOT_LOADED);
  return definitionsByType.get(type);
}
