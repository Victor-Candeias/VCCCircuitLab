import type { ComponentCatalog, ComponentDefinition } from '@vcccircuitlab/circuit-schema';
import catalogJson from '@vcccircuitlab/circuit-schema/catalog.json';
import type { Size } from './geometry';

export const catalog = catalogJson as ComponentCatalog;

export const GRID_SIZE = catalog.gridSize;

/** Tamanho usado para tipos fora do catálogo (desenhados como marcador de erro). */
export const UNKNOWN_COMPONENT_SIZE: Size = { width: 2 * GRID_SIZE, height: 2 * GRID_SIZE };

const definitionsByType = new Map(catalog.components.map((def) => [def.type, def]));

export const getComponentDefinition = (type: string): ComponentDefinition | undefined =>
  definitionsByType.get(type);
