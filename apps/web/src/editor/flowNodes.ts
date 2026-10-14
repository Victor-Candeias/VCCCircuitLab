import type {
  CircuitDocument,
  Component,
  ComponentDefinition,
  Junction,
  Point,
  WireEndpoint,
} from '@vcccircuitlab/circuit-schema';
import type { Edge, Node } from '@xyflow/react';
import { getComponentDefinition, UNKNOWN_COMPONENT_SIZE } from './catalog';
import { anchorToTopLeft, rotatedSize } from './geometry';
import { parseTerminal, pinOffset, wirePath } from './wiring';

/** Elementos de uma rede destacada (resultados da simulação). */
export interface Highlight {
  wires: ReadonlySet<string>;
  junctions: ReadonlySet<string>;
  terminals: ReadonlySet<string>;
}

/** Pino com posição relativa ao canto superior esquerdo do nó (já rodado). */
export interface PinHandle {
  id: string;
  x: number;
  y: number;
}

export type ComponentNodeData = {
  component: Component;
  definition?: ComponentDefinition;
  pins: PinHandle[];
  /** Pinos que pertencem à rede destacada. */
  highlightedPins?: string[];
};

export type ComponentNode = Node<ComponentNodeData, 'component'>;

export type JunctionNodeData = { junction: Junction };

export type JunctionNode = Node<JunctionNodeData, 'junction'>;

export type CircuitNode = ComponentNode | JunctionNode;

export type WireEdgeData = { points: Point[] };

export type WireEdge = Edge<WireEdgeData, 'wire'>;

/** Diâmetro da caixa do nó de junção (centrada na posição da junção). */
export const JUNCTION_NODE_SIZE = 12;

/** ID do handle único de um nó de junção. */
export const JUNCTION_HANDLE_ID = 'junction';

/** Deriva os nós de componente do React Flow a partir do documento canónico e da seleção. */
export function toFlowNodes(
  circuit: CircuitDocument,
  selectedIds: ReadonlySet<string>,
  highlight?: Highlight | null,
): ComponentNode[] {
  return circuit.components.map((component) => {
    const definition = getComponentDefinition(component.type);
    const size = rotatedSize(definition?.size ?? UNKNOWN_COMPONENT_SIZE, component.rotation);
    const pins = component.pins.flatMap((pinId) => {
      const offset = pinOffset(component, pinId);
      return offset
        ? [{ id: pinId, x: offset.x + size.width / 2, y: offset.y + size.height / 2 }]
        : [];
    });
    return {
      id: component.id,
      type: 'component',
      position: anchorToTopLeft(component.position, size),
      width: size.width,
      height: size.height,
      selected: selectedIds.has(component.id),
      data: highlight
        ? {
            component,
            definition,
            pins,
            highlightedPins: component.pins.filter((p) =>
              highlight.terminals.has(`${component.id}.${p}`),
            ),
          }
        : { component, definition, pins },
    };
  });
}

/** Nós de junção: pontos de ligação explícitos, desenhados sobre os fios. */
export function toJunctionNodes(
  circuit: CircuitDocument,
  selectedIds: ReadonlySet<string>,
  highlight?: Highlight | null,
): JunctionNode[] {
  const size = { width: JUNCTION_NODE_SIZE, height: JUNCTION_NODE_SIZE };
  return (circuit.junctions ?? []).map((junction) => ({
    id: junction.id,
    type: 'junction',
    position: anchorToTopLeft(junction.position, size),
    ...size,
    selected: selectedIds.has(junction.id),
    className: highlight?.junctions.has(junction.id) ? 'is-net-highlighted' : undefined,
    zIndex: 1,
    data: { junction },
  }));
}

const endpointHandle = (endpoint: WireEndpoint): { node: string; handle: string } => {
  const terminal = parseTerminal(endpoint);
  return terminal
    ? { node: terminal.componentId, handle: terminal.pinId }
    : { node: endpoint, handle: JUNCTION_HANDLE_ID };
};

/**
 * Arestas do React Flow, uma por fio. O traçado ortogonal é calculado a partir do documento
 * (`data.points`); fios com extremidades por resolver não são desenhados. A seleção de fios
 * é gerida pelo editor (Alt + clique), não pelo React Flow.
 */
export function toFlowEdges(
  circuit: CircuitDocument,
  selectedIds: ReadonlySet<string> = new Set(),
  highlight?: Highlight | null,
): WireEdge[] {
  return circuit.wires.flatMap((wire) => {
    const points = wirePath(circuit, wire);
    if (!points) return [];
    const source = endpointHandle(wire.from);
    const target = endpointHandle(wire.to);
    return [
      {
        id: wire.id,
        type: 'wire',
        source: source.node,
        sourceHandle: source.handle,
        target: target.node,
        targetHandle: target.handle,
        selectable: false,
        selected: selectedIds.has(wire.id),
        className: highlight?.wires.has(wire.id) ? 'is-net-highlighted' : undefined,
        focusable: false,
        data: { points },
      },
    ];
  });
}
