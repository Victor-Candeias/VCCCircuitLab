import type { NodeProps } from '@xyflow/react';
import type { ComponentNode } from './flowNodes';

/** Marcador provisório do componente; os símbolos IEC chegam no E1-02. */
export function ComponentNodeView({ data, selected }: NodeProps<ComponentNode>) {
  const { component, definition } = data;
  const label = definition?.label ?? `Tipo desconhecido: ${component.type}`;
  const className = [
    'component-node',
    selected ? 'is-selected' : '',
    definition ? '' : 'is-unknown',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={className}
      title={`${component.id} — ${label}`}
      aria-label={`${component.id} (${label})`}
    >
      <span className="component-node__id">{component.id}</span>
    </div>
  );
}
