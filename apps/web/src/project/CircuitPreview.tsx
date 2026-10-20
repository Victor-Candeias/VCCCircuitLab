import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { ComponentSymbol } from '../components/symbols/ComponentSymbol';
import { getComponentDefinition } from '../editor/catalog';
import { rotatedSize } from '../editor/geometry';
import { pathToSvg, wirePath } from '../editor/wiring';

const MARGIN = 20;
const FALLBACK_SIZE = { width: 40, height: 40 };

/**
 * Pré-visualização estática (SVG) de um circuito, com os mesmos símbolos e traçados de fios do
 * editor, para o utilizador confirmar visualmente um circuito gerado antes de o abrir.
 */
export function CircuitPreview({ circuit, label }: { circuit: CircuitDocument; label: string }) {
  const components = circuit.components.map((component) => {
    const definition = getComponentDefinition(component.type);
    const size = definition?.size ?? FALLBACK_SIZE;
    return { component, definition, size, box: rotatedSize(size, component.rotation) };
  });
  const wires = circuit.wires.flatMap((wire) => {
    const points = wirePath(circuit, wire);
    return points ? [{ id: wire.id, points }] : [];
  });

  const xs: number[] = [];
  const ys: number[] = [];
  for (const { component, box } of components) {
    xs.push(component.position.x - box.width / 2, component.position.x + box.width / 2);
    ys.push(component.position.y - box.height / 2, component.position.y + box.height / 2);
  }
  for (const { points } of wires) {
    for (const p of points) {
      xs.push(p.x);
      ys.push(p.y);
    }
  }
  if (xs.length === 0) return null;
  const minX = Math.min(...xs) - MARGIN;
  const minY = Math.min(...ys) - MARGIN;
  const width = Math.max(...xs) - minX + MARGIN;
  const height = Math.max(...ys) - minY + MARGIN;

  return (
    <svg
      className="circuit-preview"
      role="img"
      aria-label={label}
      viewBox={`${minX} ${minY} ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
    >
      {wires.map(({ id, points }) => (
        <path key={id} className="circuit-preview__wire" d={pathToSvg(points)} />
      ))}
      {(circuit.junctions ?? []).map((junction) => (
        <circle
          key={junction.id}
          className="circuit-preview__junction"
          cx={junction.position.x}
          cy={junction.position.y}
          r={3}
        />
      ))}
      {components.map(({ component, definition, size, box }) => (
        <g
          key={component.id}
          data-component-id={component.id}
          transform={`translate(${component.position.x - box.width / 2} ${component.position.y - box.height / 2})`}
        >
          <ComponentSymbol
            symbol={definition?.symbol ?? ''}
            size={size}
            rotation={component.rotation}
            properties={component.properties}
          />
        </g>
      ))}
    </svg>
  );
}
