import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { MouseEvent } from 'react';
import { useEditorStore } from '../store/editorStore';
import type { ComponentNode } from './flowNodes';

/** Marcador provisório do componente (os símbolos IEC chegam no E1-02), com pinos clicáveis. */
export function ComponentNodeView({ data, selected }: NodeProps<ComponentNode>) {
  const { component, definition, pins } = data;
  const label = definition?.label ?? `Tipo desconhecido: ${component.type}`;
  const className = [
    'component-node',
    selected ? 'is-selected' : '',
    definition ? '' : 'is-unknown',
  ]
    .filter(Boolean)
    .join(' ');

  const onPinClick = (event: MouseEvent, pinId: string) => {
    event.stopPropagation();
    useEditorStore
      .getState()
      .clickWireAnchor({ kind: 'terminal', ref: `${component.id}.${pinId}` });
  };

  return (
    <div
      className={className}
      title={`${component.id} — ${label}`}
      aria-label={`${component.id} (${label})`}
    >
      <span className="component-node__id">{component.id}</span>
      {pins.map((pin) => (
        <Handle
          key={pin.id}
          id={pin.id}
          type="source"
          position={Position.Top}
          isConnectable={false}
          isConnectableStart={false}
          isConnectableEnd={false}
          className="pin-handle"
          style={{ left: pin.x, top: pin.y }}
          title={`${component.id}.${pin.id}`}
          aria-label={`Terminal ${component.id}.${pin.id}`}
          role="button"
          onClick={(event) => onPinClick(event, pin.id)}
        />
      ))}
    </div>
  );
}
