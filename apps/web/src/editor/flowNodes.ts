import type {
  CircuitDocument,
  Component,
  ComponentDefinition,
} from '@vcccircuitlab/circuit-schema';
import type { Node } from '@xyflow/react';
import { getComponentDefinition, UNKNOWN_COMPONENT_SIZE } from './catalog';
import { anchorToTopLeft, rotatedSize } from './geometry';

export type ComponentNodeData = {
  component: Component;
  definition?: ComponentDefinition;
};

export type ComponentNode = Node<ComponentNodeData, 'component'>;

/** Deriva os nós do React Flow a partir do documento canónico e da seleção. */
export function toFlowNodes(
  circuit: CircuitDocument,
  selectedIds: ReadonlySet<string>,
): ComponentNode[] {
  return circuit.components.map((component) => {
    const definition = getComponentDefinition(component.type);
    const size = rotatedSize(definition?.size ?? UNKNOWN_COMPONENT_SIZE, component.rotation);
    return {
      id: component.id,
      type: 'component',
      position: anchorToTopLeft(component.position, size),
      width: size.width,
      height: size.height,
      selected: selectedIds.has(component.id),
      data: { component, definition },
    };
  });
}
