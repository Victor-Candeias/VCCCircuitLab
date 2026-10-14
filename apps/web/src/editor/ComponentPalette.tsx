import type { ComponentDefinition } from '@vcccircuitlab/circuit-schema';
import { useReactFlow, useStoreApi } from '@xyflow/react';
import { useId, useMemo, useState, type DragEvent, type KeyboardEvent } from 'react';
import { ComponentSymbol } from '../components/symbols/ComponentSymbol';
import { useEditorStore } from '../store/editorStore';
import { PALETTE_DRAG_TYPE, paletteGroups } from './palette';

function PaletteItem({
  definition,
  onAdd,
}: {
  definition: ComponentDefinition;
  onAdd: (type: string) => void;
}) {
  const onDragStart = (event: DragEvent) => {
    event.dataTransfer.setData(PALETTE_DRAG_TYPE, definition.type);
    event.dataTransfer.setData('text/plain', definition.type);
    event.dataTransfer.effectAllowed = 'copy';
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onAdd(definition.type);
    }
  };

  // `div` com role="button": o Firefox não inicia o arrastamento a partir de <button>.
  return (
    <li>
      <div
        className="palette-item"
        role="button"
        tabIndex={0}
        draggable
        title={definition.description ?? definition.label}
        aria-label={`Adicionar ${definition.label}`}
        data-type={definition.type}
        onDragStart={onDragStart}
        onClick={() => onAdd(definition.type)}
        onKeyDown={onKeyDown}
      >
        <span className="palette-item__preview">
          <ComponentSymbol symbol={definition.symbol} size={definition.size} />
        </span>
        <span className="palette-item__label">{definition.label}</span>
      </div>
    </li>
  );
}

/**
 * Paleta de componentes do catálogo, pesquisável e agrupada por categoria. Cada componente
 * pode ser arrastado para o canvas (largado com snap à grelha) ou adicionado com clique/Enter
 * no centro da vista.
 */
export function ComponentPalette() {
  const [query, setQuery] = useState('');
  const groups = useMemo(() => paletteGroups(query), [query]);
  const { screenToFlowPosition } = useReactFlow();
  const flowStore = useStoreApi();
  const headingId = useId();

  const addAtViewCenter = (type: string) => {
    const rect = flowStore.getState().domNode?.getBoundingClientRect();
    const center = rect
      ? screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
      : { x: 0, y: 0 };
    useEditorStore.getState().addComponent(type, center);
  };

  return (
    <aside className="palette" aria-labelledby={headingId}>
      <h2 id={headingId} className="palette__title">
        Componentes
      </h2>
      <input
        className="palette__search"
        type="search"
        placeholder="Pesquisar…"
        aria-label="Pesquisar componentes"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <div className="palette__groups">
        {groups.map((group) => (
          <section key={group.category} className="palette__group" aria-label={group.label}>
            <h3 className="palette__group-title">{group.label}</h3>
            <ul className="palette__list">
              {group.items.map((definition) => (
                <PaletteItem
                  key={definition.type}
                  definition={definition}
                  onAdd={addAtViewCenter}
                />
              ))}
            </ul>
          </section>
        ))}
        {groups.length === 0 && <p className="palette__empty">Nenhum componente encontrado.</p>}
      </div>
      <p className="palette__hint">
        Arraste para o canvas ou clique para adicionar. <kbd>R</kbd> roda a seleção.
      </p>
    </aside>
  );
}
