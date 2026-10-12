import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type NodeChange,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCallback, useMemo } from 'react';
import { useEditorStore } from '../store/editorStore';
import { GRID_SIZE } from './catalog';
import { ComponentNodeView } from './ComponentNodeView';
import { toFlowNodes, type ComponentNode } from './flowNodes';
import { topLeftToAnchor } from './geometry';
import './editor.css';

const nodeTypes: NodeTypes = { component: ComponentNodeView };

/**
 * Canvas do editor: grelha, pan (arrastar o fundo), zoom (roda/controlos) e seleção
 * simples (clique), múltipla (Ctrl/⌘ + clique) ou por caixa (Shift + arrastar).
 * Os nós são derivados do documento canónico; as alterações voltam ao store.
 */
export function EditorCanvas() {
  const circuit = useEditorStore((s) => s.circuit);
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const moveComponent = useEditorStore((s) => s.moveComponent);
  const setSelection = useEditorStore((s) => s.setSelection);

  const nodes = useMemo(() => toFlowNodes(circuit, new Set(selectedIds)), [circuit, selectedIds]);

  const onNodesChange = useCallback(
    (changes: NodeChange<ComponentNode>[]) => {
      let selection: Set<string> | undefined;
      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          const node = nodes.find((n) => n.id === change.id);
          if (node?.width !== undefined && node.height !== undefined) {
            moveComponent(
              change.id,
              topLeftToAnchor(change.position, { width: node.width, height: node.height }),
            );
          }
        } else if (change.type === 'select') {
          selection ??= new Set(useEditorStore.getState().selectedIds);
          if (change.selected) selection.add(change.id);
          else selection.delete(change.id);
        }
      }
      if (selection) setSelection([...selection]);
    },
    [nodes, moveComponent, setSelection],
  );

  return (
    <ReactFlow<ComponentNode>
      aria-label="Canvas do editor de circuitos"
      colorMode="system"
      nodes={nodes}
      edges={[]}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      nodesConnectable={false}
      deleteKeyCode={null}
      selectionKeyCode="Shift"
      multiSelectionKeyCode={['Control', 'Meta']}
      minZoom={0.25}
      maxZoom={4}
      fitView
      fitViewOptions={{ padding: 0.2 }}
    >
      <Background
        id="grid-minor"
        variant={BackgroundVariant.Dots}
        gap={GRID_SIZE}
        size={1.5}
        color="var(--grid-dot)"
      />
      <Background
        id="grid-major"
        variant={BackgroundVariant.Lines}
        gap={GRID_SIZE * 5}
        lineWidth={0.5}
        color="var(--grid-line)"
        bgColor="transparent"
      />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
