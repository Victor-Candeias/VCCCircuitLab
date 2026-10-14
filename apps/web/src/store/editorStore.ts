import type { CircuitDocument, Point } from '@vcccircuitlab/circuit-schema';
import { create } from 'zustand';
import { GRID_SIZE } from '../editor/catalog';
import { demoCircuit } from '../editor/demoCircuit';
import { snapPoint } from '../editor/geometry';
import { placeComponent, rotateComponents, type RotationStep } from '../editor/placement';
import {
  anchorPosition,
  commitWire,
  orthogonalize,
  type WireAnchor,
  type WireDraft,
} from '../editor/wiring';

/**
 * Estado do editor. O `circuit` é o documento canónico (modelo elétrico + geometria persistida);
 * o estado de vista (seleção, fio em desenho) vive à parte e nunca é gravado no documento.
 */
export interface EditorState {
  circuit: CircuitDocument;
  selectedIds: string[];
  /** Fio a ser desenhado (ferramenta de fio); `null` fora do modo de desenho. */
  wireDraft: WireDraft | null;
  /** Incrementado sempre que um circuito é carregado (a vista reenquadra-se). */
  loadId: number;
  loadCircuit: (circuit: CircuitDocument) => void;
  /**
   * Acrescenta um componente do catálogo com a âncora em `anchor` (snap à grelha; se a posição
   * estiver ocupada, desloca-o na diagonal) e seleciona-o. Devolve o novo ID, ou `undefined`
   * para tipos fora do catálogo.
   */
  addComponent: (type: string, anchor: Point) => string | undefined;
  /** Move a âncora de um componente, com snap à grelha. */
  moveComponent: (id: string, anchor: Point) => void;
  /** Move uma junção, com snap à grelha. */
  moveJunction: (id: string, position: Point) => void;
  /** Roda 90° os componentes selecionados, cada um em torno da própria âncora. */
  rotateSelection: (step?: RotationStep) => void;
  setSelection: (ids: readonly string[]) => void;
  /** Começa um fio num terminal, numa junção ou num ponto de um fio existente. */
  startWire: (anchor: WireAnchor) => void;
  /** Fixa um ponto intermédio (encaixado na grelha), com canto ortogonal se necessário. */
  addWireWaypoint: (point: Point) => void;
  removeLastWireWaypoint: () => void;
  /** Termina o fio; devolve `false` (e mantém o rascunho) se a ligação for inválida. */
  finishWire: (anchor: WireAnchor) => boolean;
  cancelWire: () => void;
  /** Clique numa âncora com a ferramenta de fio: começa um fio ou termina o que está em desenho. */
  clickWireAnchor: (anchor: WireAnchor) => void;
}

const sameIds = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((id, i) => id === b[i]);

const samePosition = (a: Point, b: Point) => a.x === b.x && a.y === b.y;

export const useEditorStore = create<EditorState>()((set, get) => ({
  circuit: demoCircuit,
  selectedIds: [],
  wireDraft: null,
  loadId: 0,

  loadCircuit: (circuit) =>
    set((s) => ({ circuit, selectedIds: [], wireDraft: null, loadId: s.loadId + 1 })),

  addComponent: (type, anchor) => {
    const placed = placeComponent(get().circuit, type, anchor);
    if (!placed) return undefined;
    set({ circuit: placed.circuit, selectedIds: [placed.component.id] });
    return placed.component.id;
  },

  moveComponent: (id, anchor) =>
    set((state) => {
      const position = snapPoint(anchor, GRID_SIZE);
      const current = state.circuit.components.find((c) => c.id === id);
      if (!current || samePosition(current.position, position)) return state;
      return {
        circuit: {
          ...state.circuit,
          components: state.circuit.components.map((c) => (c.id === id ? { ...c, position } : c)),
        },
      };
    }),

  moveJunction: (id, point) =>
    set((state) => {
      const position = snapPoint(point, GRID_SIZE);
      const junctions = state.circuit.junctions ?? [];
      const current = junctions.find((j) => j.id === id);
      if (!current || samePosition(current.position, position)) return state;
      return {
        circuit: {
          ...state.circuit,
          junctions: junctions.map((j) => (j.id === id ? { ...j, position } : j)),
        },
      };
    }),

  rotateSelection: (step = 90) =>
    set((state) => {
      const circuit = rotateComponents(state.circuit, state.selectedIds, step);
      return circuit === state.circuit ? state : { circuit };
    }),

  setSelection: (ids) =>
    set((state) => {
      const known = new Set([
        ...state.circuit.components.map((c) => c.id),
        ...(state.circuit.junctions ?? []).map((j) => j.id),
      ]);
      const next = [...new Set(ids)].filter((id) => known.has(id));
      return sameIds(next, state.selectedIds) ? state : { selectedIds: next };
    }),

  startWire: (anchor) =>
    set((state) =>
      anchorPosition(state.circuit, anchor)
        ? { wireDraft: { start: anchor, waypoints: [] } }
        : state,
    ),

  addWireWaypoint: (point) =>
    set((state) => {
      const draft = state.wireDraft;
      const start = draft && anchorPosition(state.circuit, draft.start);
      if (!draft || !start) return state;
      const path = orthogonalize([start, ...draft.waypoints, snapPoint(point, GRID_SIZE)]);
      return { wireDraft: { ...draft, waypoints: path.slice(1) } };
    }),

  removeLastWireWaypoint: () =>
    set((state) =>
      state.wireDraft && state.wireDraft.waypoints.length > 0
        ? { wireDraft: { ...state.wireDraft, waypoints: state.wireDraft.waypoints.slice(0, -1) } }
        : state,
    ),

  finishWire: (anchor) => {
    const { circuit, wireDraft } = get();
    const next = wireDraft && commitWire(circuit, wireDraft, anchor);
    if (!next) return false;
    set({ circuit: next, wireDraft: null });
    return true;
  },

  cancelWire: () => set((state) => (state.wireDraft ? { wireDraft: null } : state)),

  clickWireAnchor: (anchor) => {
    if (get().wireDraft) get().finishWire(anchor);
    else get().startWire(anchor);
  },
}));
