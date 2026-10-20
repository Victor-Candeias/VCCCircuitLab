import type { ComponentCategory, ComponentDefinition } from '@vcccircuitlab/circuit-schema';
import { catalog } from './catalog';

/** Tipo MIME do `dataTransfer` ao arrastar um componente da paleta para o canvas. */
export const PALETTE_DRAG_TYPE = 'application/x-vcccircuitlab-component';

/** Grupos da paleta, pela ordem apresentada. */
export const CATEGORY_LABELS: Record<ComponentCategory, string> = {
  source: 'Fontes',
  passive: 'Passivos',
  switch: 'Interruptores',
  load: 'Cargas',
  instrument: 'Instrumentos',
  reference: 'Referência',
};

export interface PaletteGroup {
  category: ComponentCategory;
  label: string;
  items: ComponentDefinition[];
}

/** Minúsculas e sem acentos (`Tensão` → `tensao`). */
const fold = (text: string) =>
  text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();

const searchText = (definition: ComponentDefinition) =>
  fold(
    [
      definition.label,
      definition.type,
      definition.idPrefix,
      definition.description ?? '',
      CATEGORY_LABELS[definition.category],
    ].join(' '),
  );

/**
 * Componentes do catálogo agrupados por categoria e filtrados pela pesquisa: todas as
 * palavras têm de ocorrer no nome, tipo, prefixo, descrição ou categoria (sem distinguir
 * maiúsculas nem acentos). Grupos vazios são omitidos.
 */
export function paletteGroups(
  query = '',
  definitions: readonly ComponentDefinition[] = catalog.components,
): PaletteGroup[] {
  const terms = fold(query).split(/\s+/).filter(Boolean);
  const matches = definitions.filter((definition) => {
    const text = searchText(definition);
    return terms.every((term) => text.includes(term));
  });
  return (Object.keys(CATEGORY_LABELS) as ComponentCategory[]).flatMap((category) => {
    const items = matches.filter((definition) => definition.category === category);
    return items.length > 0 ? [{ category, label: CATEGORY_LABELS[category], items }] : [];
  });
}
