import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { MouseEvent } from 'react';
import { ComponentSymbol } from '../components/symbols/ComponentSymbol';
import { useEditorStore } from '../store/editorStore';
import type { ComponentNode } from './flowNodes';

/**
 * Componente desenhado com o símbolo IEC do catálogo, com pinos clicáveis. Tipos fora do
 * catálogo aparecem como um marcador de erro.
 */
export function ComponentNodeView({ data, selected, width, height }: NodeProps<ComponentNode>) {
  const { component, definition, pins } = data;
  const label = definition?.label ?? `Tipo desconhecido: ${component.type}`;
  // O ID fica acima de símbolos horizontais e à direita dos verticais, longe dos pinos.
  const horizontal = (width ?? 0) > (height ?? 0);
  const className = [
    'component-node',
    horizontal ? 'is-horizontal' : 'is-vertical',
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
      {definition && (
        <ComponentSymbol
          symbol={definition.symbol}
          size={definition.size}
          rotation={component.rotation}
          properties={component.properties}
        />
      )}
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
