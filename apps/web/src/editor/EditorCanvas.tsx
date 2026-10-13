import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  ViewportPortal,
  type EdgeMouseHandler,
  type EdgeTypes,
  type NodeChange,
  type NodeMouseHandler,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { Point } from '@vcccircuitlab/circuit-schema';
import { useCallback, useEffect, useMemo, useState, type MouseEvent } from 'react';
import { useEditorStore } from '../store/editorStore';
import { GRID_SIZE } from './catalog';
import { ComponentNodeView } from './ComponentNodeView';
import {
  toFlowEdges,
  toFlowNodes,
  toJunctionNodes,
  type CircuitNode,
  type WireEdge,
} from './flowNodes';
import { snapPoint, topLeftToAnchor } from './geometry';
import { JunctionNodeView } from './JunctionNodeView';
import { WireEdgeView } from './WireEdgeView';
import {
  anchorPosition,
  nearestPointOnPath,
  orthogonalize,
  pathToSvg,
  type WireAnchor,
} from './wiring';
import './editor.css';

const nodeTypes: NodeTypes = { component: ComponentNodeView, junction: JunctionNodeView };
const edgeTypes: EdgeTypes = { wire: WireEdgeView };

/** Posição do cursor (encaixada) associada ao início do fio em desenho. */
interface DraftCursor {
  start: WireAnchor;
  point: Point;
}

/** Pré-visualização do fio em desenho: troços fixados + troço ortogonal até ao cursor. */
function WireDraftPreview({ cursor }: { cursor: DraftCursor | null }) {
  const circuit = useEditorStore((s) => s.circuit);
  const draft = useEditorStore((s) => s.wireDraft);
  const start = draft && anchorPosition(circuit, draft.start);
  if (!draft || !start) return null;

  // Um cursor guardado durante um fio anterior não é usado.
  const end = cursor?.start === draft.start ? [cursor.point] : [];
  const points = orthogonalize([start, ...draft.waypoints, ...end]);
  return (
    <ViewportPortal>
      <svg className="wire-draft" aria-hidden="true">
        <path className="wire-draft__path" d={pathToSvg(points)} />
        {draft.waypoints.map((p, i) => (
          <circle key={i} className="wire-draft__waypoint" cx={p.x} cy={p.y} r={2.5} />
        ))}
      </svg>
    </ViewportPortal>
  );
}

/**
 * Canvas do editor: grelha, pan (arrastar o fundo), zoom (roda/controlos) e seleção
 * simples (clique), múltipla (Ctrl/⌘ + clique) ou por caixa (Shift + arrastar).
 * Ferramenta de fio: clique num terminal, junção ou fio para começar; cliques no fundo fixam
 * pontos intermédios ortogonais; clique noutro terminal, junção ou fio para terminar (num fio
 * cria uma junção explícita). Esc cancela; Backspace remove o último ponto.
 * Os nós e fios são derivados do documento canónico; as alterações voltam ao store.
 */
function EditorFlow() {
  const circuit = useEditorStore((s) => s.circuit);
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const draftStart = useEditorStore((s) => s.wireDraft?.start);
  const isWiring = draftStart !== undefined;
  const { moveComponent, moveJunction, setSelection, addWireWaypoint, clickWireAnchor } =
    useEditorStore.getState();
  const { screenToFlowPosition } = useReactFlow();
  const [cursor, setCursor] = useState<DraftCursor | null>(null);

  const nodes = useMemo<CircuitNode[]>(() => {
    const selected = new Set(selectedIds);
    return [...toFlowNodes(circuit, selected), ...toJunctionNodes(circuit, selected)];
  }, [circuit, selectedIds]);
  const edges = useMemo(() => toFlowEdges(circuit), [circuit]);

  const toFlowPoint = useCallback(
    (event: MouseEvent) => screenToFlowPosition({ x: event.clientX, y: event.clientY }),
    [screenToFlowPosition],
  );

  useEffect(() => {
    if (!isWiring) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        useEditorStore.getState().cancelWire();
      } else if (event.key === 'Backspace') {
        event.preventDefault();
        useEditorStore.getState().removeLastWireWaypoint();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isWiring]);

  const onNodesChange = useCallback(
    (changes: NodeChange<CircuitNode>[]) => {
      let selection: Set<string> | undefined;
      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          const node = nodes.find((n) => n.id === change.id);
          if (node?.width === undefined || node.height === undefined) continue;
          const anchor = topLeftToAnchor(change.position, {
            width: node.width,
            height: node.height,
          });
          if (node.type === 'junction') moveJunction(change.id, anchor);
          else moveComponent(change.id, anchor);
        } else if (change.type === 'select') {
          selection ??= new Set(useEditorStore.getState().selectedIds);
          if (change.selected) selection.add(change.id);
          else selection.delete(change.id);
        }
      }
      if (selection) setSelection([...selection]);
    },
    [nodes, moveComponent, moveJunction, setSelection],
  );

  const onNodeClick: NodeMouseHandler<CircuitNode> = useCallback(
    (_event, node) => {
      if (node.type === 'junction') clickWireAnchor({ kind: 'junction', id: node.id });
    },
    [clickWireAnchor],
  );

  const onEdgeClick: EdgeMouseHandler<WireEdge> = useCallback(
    (event, edge) => {
      const hit = edge.data && nearestPointOnPath(edge.data.points, toFlowPoint(event), GRID_SIZE);
      if (hit) clickWireAnchor({ kind: 'wire', wireId: edge.id, point: hit.point });
    },
    [clickWireAnchor, toFlowPoint],
  );

  const onPaneClick = useCallback(
    (event: MouseEvent) => {
      if (useEditorStore.getState().wireDraft) addWireWaypoint(toFlowPoint(event));
    },
    [addWireWaypoint, toFlowPoint],
  );

  const onPaneContextMenu = useCallback((event: MouseEvent | globalThis.MouseEvent) => {
    if (!useEditorStore.getState().wireDraft) return;
    event.preventDefault();
    useEditorStore.getState().cancelWire();
  }, []);

  const onMouseMove = useCallback(
    (event: MouseEvent) => {
      if (draftStart) {
        setCursor({ start: draftStart, point: snapPoint(toFlowPoint(event), GRID_SIZE) });
      }
    },
    [draftStart, toFlowPoint],
  );

  return (
    <ReactFlow<CircuitNode, WireEdge>
      aria-label="Canvas do editor de circuitos"
      className={isWiring ? 'is-wiring' : undefined}
      colorMode="system"
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onNodeClick={onNodeClick}
      onEdgeClick={onEdgeClick}
      onPaneClick={onPaneClick}
      onPaneContextMenu={onPaneContextMenu}
      onMouseMove={onMouseMove}
      connectionMode={ConnectionMode.Loose}
      nodesConnectable={false}
      connectOnClick={false}
      edgesFocusable={false}
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
      <WireDraftPreview cursor={cursor} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function EditorCanvas() {
  return (
    <ReactFlowProvider>
      <EditorFlow />
    </ReactFlowProvider>
  );
}
