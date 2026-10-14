import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  Panel,
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
import { useCallback, useEffect, useMemo, useState, type DragEvent, type MouseEvent } from 'react';
import { useEditorStore } from '../store/editorStore';
import { netHighlight } from '../simulation/nets';
import { SimulationPanel } from '../simulation/SimulationPanel';
import { isCurrent, useSimulationStore } from '../simulation/simulationStore';
import { getComponentDefinition, GRID_SIZE } from './catalog';
import { ComponentNodeView } from './ComponentNodeView';
import { ComponentPalette } from './ComponentPalette';
import {
  toFlowEdges,
  toFlowNodes,
  toJunctionNodes,
  type CircuitNode,
  type WireEdge,
} from './flowNodes';
import { snapPoint, topLeftToAnchor } from './geometry';
import { JunctionNodeView } from './JunctionNodeView';
import { PALETTE_DRAG_TYPE } from './palette';
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

/** Teclas de atalho não se aplicam enquanto se escreve num campo. */
const isEditableTarget = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));

const isWireId = (circuit: { wires: { id: string }[] }, id: string) =>
  circuit.wires.some((w) => w.id === id);

/**
 * Atalhos de edição: Delete/Backspace apagam; Ctrl/⌘ + Z desfaz; Ctrl/⌘ + Y ou
 * Ctrl/⌘ + Shift + Z refaz; Ctrl/⌘ + C / X / V copiam, cortam e colam.
 */
function editShortcut(event: KeyboardEvent): (() => void) | undefined {
  const state = useEditorStore.getState();
  const mod = event.ctrlKey || event.metaKey;
  if (!mod && !event.altKey && (event.key === 'Delete' || event.key === 'Backspace')) {
    return state.deleteSelection;
  }
  if (!mod || event.altKey) return undefined;
  const key = event.key.toLowerCase();
  if (key === 'z') return event.shiftKey ? state.redo : state.undo;
  if (event.shiftKey) return undefined;
  if (key === 'y') return state.redo;
  // Com texto selecionado na página, Ctrl+C/X mantêm o comportamento nativo.
  const hasTextSelection = Boolean(window.getSelection()?.toString());
  if (key === 'c' && !hasTextSelection) return state.copySelection;
  if (key === 'x' && !hasTextSelection) return state.cutSelection;
  if (key === 'v') return state.paste;
  return undefined;
}

/** Ícones SVG da barra (não dependem de fontes de emoji). */
const TOOL_ICONS = {
  copy: 'M9 9h10v10H9z M5 15V5h10',
  paste: 'M8 4h8v3H8z M6 6H5v15h14V6h-1 M9 12h6 M9 16h6',
  delete: 'M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13 M10 11v6 M14 11v6',
} as const;

function ToolIcon({ name }: { name: keyof typeof TOOL_ICONS }) {
  return (
    <svg
      className="editor-toolbar__icon"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={TOOL_ICONS[name]} />
    </svg>
  );
}

/** Barra de edição: desfazer/refazer, copiar/colar, apagar e rodar. */
function EditToolbar() {
  const canUndo = useEditorStore((s) => s.past.length > 0);
  const canRedo = useEditorStore((s) => s.future.length > 0);
  const canPaste = useEditorStore((s) => s.clipboard !== null);
  const hasSelection = useEditorStore((s) => s.selectedIds.length > 0);
  const canCopy = useEditorStore((s) => s.selectedIds.some((id) => !isWireId(s.circuit, id)));
  const canRotate = useEditorStore((s) => {
    const selected = new Set(s.selectedIds);
    return s.circuit.components.some((c) => selected.has(c.id));
  });
  const { undo, redo, copySelection, paste, deleteSelection, rotateSelection } =
    useEditorStore.getState();
  return (
    <Panel position="top-right" className="editor-toolbar">
      <button
        type="button"
        disabled={!canUndo}
        title="Desfazer (Ctrl+Z)"
        aria-label="Desfazer"
        onClick={undo}
      >
        ↶
      </button>
      <button
        type="button"
        disabled={!canRedo}
        title="Refazer (Ctrl+Y)"
        aria-label="Refazer"
        onClick={redo}
      >
        ↷
      </button>
      <span className="editor-toolbar__separator" />
      <button
        type="button"
        disabled={!canCopy}
        title="Copiar (Ctrl+C)"
        aria-label="Copiar"
        onClick={copySelection}
      >
        <ToolIcon name="copy" />
      </button>
      <button
        type="button"
        disabled={!canPaste}
        title="Colar (Ctrl+V)"
        aria-label="Colar"
        onClick={paste}
      >
        <ToolIcon name="paste" />
      </button>
      <button
        type="button"
        disabled={!hasSelection}
        title="Apagar (Delete)"
        aria-label="Apagar seleção"
        onClick={deleteSelection}
      >
        <ToolIcon name="delete" />
      </button>
      <span className="editor-toolbar__separator" />
      <button
        type="button"
        disabled={!canRotate}
        title="Rodar 90° no sentido anti-horário (Shift+R)"
        aria-label="Rodar 90° no sentido anti-horário"
        onClick={() => rotateSelection(-90)}
      >
        ⟲
      </button>
      <button
        type="button"
        disabled={!canRotate}
        title="Rodar 90° no sentido horário (R)"
        aria-label="Rodar 90° no sentido horário"
        onClick={() => rotateSelection(90)}
      >
        ⟳
      </button>
    </Panel>
  );
}

/**
 * Canvas do editor: grelha, pan (arrastar o fundo), zoom (roda/controlos) e seleção
 * simples (clique), múltipla (Ctrl/⌘ + clique) ou por caixa (Shift + arrastar).
 * Ferramenta de fio: clique num terminal, junção ou fio para começar; cliques no fundo fixam
 * pontos intermédios ortogonais; clique noutro terminal, junção ou fio para terminar (num fio
 * cria uma junção explícita). Esc cancela; Backspace remove o último ponto.
 * Componentes largados a partir da paleta ficam com a âncora encaixada na grelha; `R` roda a
 * seleção 90° no sentido horário e `Shift+R` no sentido anti-horário.
 * Os nós e fios são derivados do documento canónico; as alterações voltam ao store.
 */
function EditorFlow() {
  const circuit = useEditorStore((s) => s.circuit);
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const draftStart = useEditorStore((s) => s.wireDraft?.start);
  const isWiring = draftStart !== undefined;
  const {
    moveComponent,
    moveJunction,
    setSelection,
    addWireWaypoint,
    clickWireAnchor,
    beginHistoryGroup,
    endHistoryGroup,
  } = useEditorStore.getState();
  const loadId = useEditorStore((s) => s.loadId);
  const { screenToFlowPosition, fitView } = useReactFlow();
  const [cursor, setCursor] = useState<DraftCursor | null>(null);

  const highlightedNet = useSimulationStore((s) =>
    isCurrent(s.simulation, circuit) ? s.highlightedNet : null,
  );
  const highlight = useMemo(() => netHighlight(circuit, highlightedNet), [circuit, highlightedNet]);
  const nodes = useMemo<CircuitNode[]>(() => {
    const selected = new Set(selectedIds);
    return [
      ...toFlowNodes(circuit, selected, highlight),
      ...toJunctionNodes(circuit, selected, highlight),
    ];
  }, [circuit, selectedIds, highlight]);
  const edges = useMemo(
    () => toFlowEdges(circuit, new Set(selectedIds), highlight),
    [circuit, selectedIds, highlight],
  );

  const toFlowPoint = useCallback(
    (event: MouseEvent) => screenToFlowPosition({ x: event.clientX, y: event.clientY }),
    [screenToFlowPosition],
  );

  useEffect(() => {
    // Ao abrir outro circuito, enquadra-o (o `fitView` inicial só corre na montagem).
    if (loadId > 0) requestAnimationFrame(() => void fitView({ padding: 0.2 }));
  }, [loadId, fitView]);

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

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'r' || event.repeat || event.defaultPrevented) return;
      if (event.ctrlKey || event.metaKey || event.altKey || isEditableTarget(event.target)) return;
      event.preventDefault();
      useEditorStore.getState().rotateSelection(event.shiftKey ? -90 : 90);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || isEditableTarget(event.target)) return;
      // Durante o desenho de um fio, Backspace remove o último ponto (atalho próprio).
      if (useEditorStore.getState().wireDraft) return;
      const action = editShortcut(event);
      if (!action) return;
      event.preventDefault();
      action();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const onDragOver = useCallback((event: DragEvent) => {
    if (!event.dataTransfer.types.includes(PALETTE_DRAG_TYPE)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      const type = event.dataTransfer.getData(PALETTE_DRAG_TYPE);
      if (!type || !getComponentDefinition(type)) return;
      event.preventDefault();
      useEditorStore.getState().addComponent(type, toFlowPoint(event));
    },
    [toFlowPoint],
  );

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

  /** Retira os fios da seleção (o React Flow só gere a seleção de nós). */
  const deselectWires = useCallback(() => {
    const { circuit, selectedIds } = useEditorStore.getState();
    setSelection(selectedIds.filter((id) => !isWireId(circuit, id)));
  }, [setSelection]);

  const onNodeClick: NodeMouseHandler<CircuitNode> = useCallback(
    (event, node) => {
      if (!event.ctrlKey && !event.metaKey) deselectWires();
      if (node.type === 'junction') clickWireAnchor({ kind: 'junction', id: node.id });
    },
    [clickWireAnchor, deselectWires],
  );

  const onEdgeClick: EdgeMouseHandler<WireEdge> = useCallback(
    (event, edge) => {
      // Alt + clique seleciona o fio (com Ctrl/⌘, acrescenta ou retira da seleção).
      if (event.altKey && !useEditorStore.getState().wireDraft) {
        const { selectedIds } = useEditorStore.getState();
        if (!event.ctrlKey && !event.metaKey) setSelection([edge.id]);
        else if (selectedIds.includes(edge.id)) {
          setSelection(selectedIds.filter((id) => id !== edge.id));
        } else setSelection([...selectedIds, edge.id]);
        return;
      }
      const hit = edge.data && nearestPointOnPath(edge.data.points, toFlowPoint(event), GRID_SIZE);
      if (hit) clickWireAnchor({ kind: 'wire', wireId: edge.id, point: hit.point });
    },
    [clickWireAnchor, setSelection, toFlowPoint],
  );

  const onPaneClick = useCallback(
    (event: MouseEvent) => {
      if (useEditorStore.getState().wireDraft) addWireWaypoint(toFlowPoint(event));
      else deselectWires();
    },
    [addWireWaypoint, deselectWires, toFlowPoint],
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
      onNodeDragStart={beginHistoryGroup}
      onNodeDragStop={endHistoryGroup}
      onSelectionDragStart={beginHistoryGroup}
      onSelectionDragStop={endHistoryGroup}
      onEdgeClick={onEdgeClick}
      onPaneClick={onPaneClick}
      onPaneContextMenu={onPaneContextMenu}
      onMouseMove={onMouseMove}
      onDragOver={onDragOver}
      onDrop={onDrop}
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
      <EditToolbar />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function EditorCanvas() {
  return (
    <ReactFlowProvider>
      <div className="editor">
        <ComponentPalette />
        <div className="editor__canvas">
          <EditorFlow />
        </div>
        <SimulationPanel />
      </div>
    </ReactFlowProvider>
  );
}
