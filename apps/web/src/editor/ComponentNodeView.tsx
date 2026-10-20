import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { KeyboardEvent, MouseEvent } from 'react';
import { ComponentSymbol } from '../components/symbols/ComponentSymbol';
import { formatReading, instrumentModel, instrumentReading } from '../simulation/instruments';
import { useSimulationStore } from '../simulation/simulationStore';
import { useEditorStore } from '../store/editorStore';
import type { ComponentNode } from './flowNodes';

/**
 * Componente desenhado com o símbolo IEC do catálogo, com pinos clicáveis. Tipos fora do
 * catálogo aparecem como um marcador de erro.
 */
export function ComponentNodeView({ data, selected, width, height }: NodeProps<ComponentNode>) {
  const { component, definition, pins, highlightedPins } = data;
  const reading = useInstrumentReading(component);
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

  // Enter/Espaço ativam o terminal tal como um clique (navegação só por teclado).
  const onPinKeyDown = (event: KeyboardEvent, pinId: string) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
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
      {reading && (
        <span className="component-node__reading" aria-label={`Leitura de ${component.id}`}>
          {reading}
        </span>
      )}
      {pins.map((pin) => (
        <Handle
          key={pin.id}
          id={pin.id}
          type="source"
          position={Position.Top}
          isConnectable={false}
          isConnectableStart={false}
          isConnectableEnd={false}
          className={
            highlightedPins?.includes(pin.id) ? 'pin-handle is-net-highlighted' : 'pin-handle'
          }
          style={{ left: pin.x, top: pin.y }}
          title={`${component.id}.${pin.id}`}
          aria-label={`Terminal ${component.id}.${pin.id}`}
          role="button"
          tabIndex={0}
          onClick={(event) => onPinClick(event, pin.id)}
          onKeyDown={(event) => onPinKeyDown(event, pin.id)}
        />
      ))}
    </div>
  );
}

/**
 * Texto da leitura de um instrumento virtual, se a última simulação (com sucesso) corresponder
 * ao circuito atual; `null` para os restantes componentes (que não subscrevem o circuito).
 */
function useInstrumentReading(component: ComponentNode['data']['component']): string | null {
  const instrument = instrumentModel(component.type) !== null;
  const circuit = useEditorStore((s) => (instrument ? s.circuit : null));
  return useSimulationStore((s) => {
    const simulation = s.simulation;
    if (!circuit || simulation.status !== 'success' || simulation.circuit !== circuit) return null;
    const reading = instrumentReading(circuit, simulation.result, component);
    if (!reading) return null;
    const scope = reading.model === 'oscilloscope';
    return reading.values.map((v) => (scope ? `${v.label} ` : '') + formatReading(v)).join(' · ');
  });
}
