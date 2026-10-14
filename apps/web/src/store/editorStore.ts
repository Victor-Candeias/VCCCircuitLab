import type { CircuitDocument, Point } from '@vcccircuitlab/circuit-schema';
import { create } from 'zustand';
import { GRID_SIZE } from '../editor/catalog';
import { demoCircuit } from '../editor/demoCircuit';
import {
  copyFragment,
  deleteElements,
  pasteFragment,
  type CircuitFragment,
} from '../editor/editing';
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
  /** Estados anteriores do documento (o mais recente no fim), para desfazer. */
  past: CircuitDocument[];
  /** Estados desfeitos, para refazer (o próximo no fim). */
  future: CircuitDocument[];
  /**
   * Documento no início de um gesto contínuo (arrastar): as alterações do gesto ficam numa
   * única entrada do histórico, registada em `endHistoryGroup`.
   */
  historyGroup: CircuitDocument | null;
  /** Elementos copiados e quantas vezes já foram colados (para deslocar cada cópia). */
  clipboard: { fragment: CircuitFragment; pastes: number } | null;
  /** Substitui o documento (abrir, novo, exemplo); limpa a seleção e o histórico. */
  loadCircuit: (circuit: CircuitDocument) => void;
  undo: () => void;
  redo: () => void;
  beginHistoryGroup: () => void;
  endHistoryGroup: () => void;
  /** Apaga os elementos selecionados e os fios ligados a eles. */
  deleteSelection: () => void;
  copySelection: () => void;
  cutSelection: () => void;
  /** Cola a última cópia com novos IDs, deslocada na diagonal, e seleciona-a. */
  paste: () => void;
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
  /**
   * Substitui as propriedades de um componente (painel de propriedades, E1-05). Regista uma
   * entrada própria no histórico (não faz parte de um gesto contínuo).
   */
  setComponentProperties: (id: string, properties: CircuitDocument['components'][number]['properties']) => void;
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

/** Número máximo de passos guardados para desfazer. */
export const HISTORY_LIMIT = 100;

/** Deslocamento de cada colagem sucessiva (duas células na diagonal). */
const PASTE_STEP = 2 * GRID_SIZE;

/**
 * Alteração do documento com registo no histórico (exceto dentro de um gesto, que é registado
 * no fim). Uma alteração nova descarta o que tinha sido desfeito.
 */
function record(state: EditorState, circuit: CircuitDocument): Partial<EditorState> {
  if (circuit === state.circuit) return {};
  if (state.historyGroup) return { circuit };
  return { circuit, past: [...state.past, state.circuit].slice(-HISTORY_LIMIT), future: [] };
}

/** IDs de componentes, junções e fios existentes (os elementos selecionáveis). */
const elementIds = (circuit: CircuitDocument) =>
  new Set([
    ...circuit.components.map((c) => c.id),
    ...(circuit.junctions ?? []).map((j) => j.id),
    ...circuit.wires.map((w) => w.id),
  ]);

/** Volta a um documento do histórico, mantendo só a seleção que ainda existe. */
function travel(state: EditorState, circuit: CircuitDocument): Partial<EditorState> {
  const known = elementIds(circuit);
  return {
    circuit,
    selectedIds: state.selectedIds.filter((id) => known.has(id)),
    wireDraft: null,
    historyGroup: null,
  };
}

export const useEditorStore = create<EditorState>()((set, get) => ({
  circuit: demoCircuit,
  selectedIds: [],
  wireDraft: null,
  loadId: 0,
  past: [],
  future: [],
  historyGroup: null,
  clipboard: null,

  loadCircuit: (circuit) =>
    set((s) => ({
      circuit,
      selectedIds: [],
      wireDraft: null,
      loadId: s.loadId + 1,
      past: [],
      future: [],
      historyGroup: null,
    })),

  undo: () =>
    set((state) => {
      if (state.historyGroup || state.past.length === 0) return state;
      return {
        ...travel(state, state.past[state.past.length - 1]),
        past: state.past.slice(0, -1),
        future: [...state.future, state.circuit],
      };
    }),

  redo: () =>
    set((state) => {
      if (state.historyGroup || state.future.length === 0) return state;
      return {
        ...travel(state, state.future[state.future.length - 1]),
        past: [...state.past, state.circuit].slice(-HISTORY_LIMIT),
        future: state.future.slice(0, -1),
      };
    }),

  beginHistoryGroup: () =>
    set((state) => (state.historyGroup ? state : { historyGroup: state.circuit })),

  endHistoryGroup: () =>
    set((state) => {
      const start = state.historyGroup;
      if (!start) return state;
      if (start === state.circuit) return { historyGroup: null };
      return {
        historyGroup: null,
        past: [...state.past, start].slice(-HISTORY_LIMIT),
        future: [],
      };
    }),

  deleteSelection: () =>
    set((state) => {
      const circuit = deleteElements(state.circuit, state.selectedIds);
      return circuit === state.circuit ? state : { ...record(state, circuit), selectedIds: [] };
    }),

  copySelection: () =>
    set((state) => {
      const fragment = copyFragment(state.circuit, state.selectedIds);
      return fragment ? { clipboard: { fragment, pastes: 0 } } : state;
    }),

  cutSelection: () => {
    const fragment = copyFragment(get().circuit, get().selectedIds);
    if (!fragment) return;
    // A primeira colagem depois de cortar repõe os elementos no mesmo sítio.
    set({ clipboard: { fragment, pastes: -1 } });
    get().deleteSelection();
  },

  paste: () =>
    set((state) => {
      if (!state.clipboard) return state;
      const pastes = state.clipboard.pastes + 1;
      const offset = { x: pastes * PASTE_STEP, y: pastes * PASTE_STEP };
      const pasted = pasteFragment(state.circuit, state.clipboard.fragment, offset);
      return {
        ...record(state, pasted.circuit),
        selectedIds: pasted.ids,
        wireDraft: null,
        clipboard: { ...state.clipboard, pastes },
      };
    }),

  addComponent: (type, anchor) => {
    const state = get();
    const placed = placeComponent(state.circuit, type, anchor);
    if (!placed) return undefined;
    set({ ...record(state, placed.circuit), selectedIds: [placed.component.id] });
    return placed.component.id;
  },

  moveComponent: (id, anchor) =>
    set((state) => {
      const position = snapPoint(anchor, GRID_SIZE);
      const current = state.circuit.components.find((c) => c.id === id);
      if (!current || samePosition(current.position, position)) return state;
      return record(state, {
        ...state.circuit,
        components: state.circuit.components.map((c) => (c.id === id ? { ...c, position } : c)),
      });
    }),

  moveJunction: (id, point) =>
    set((state) => {
      const position = snapPoint(point, GRID_SIZE);
      const junctions = state.circuit.junctions ?? [];
      const current = junctions.find((j) => j.id === id);
      if (!current || samePosition(current.position, position)) return state;
      return record(state, {
        ...state.circuit,
        junctions: junctions.map((j) => (j.id === id ? { ...j, position } : j)),
      });
    }),

  rotateSelection: (step = 90) =>
    set((state) => {
      const circuit = rotateComponents(state.circuit, state.selectedIds, step);
      return circuit === state.circuit ? state : record(state, circuit);
    }),

  setComponentProperties: (id, properties) =>
    set((state) => {
      const current = state.circuit.components.find((c) => c.id === id);
      if (!current || current.properties === properties) return state;
      return record(state, {
        ...state.circuit,
        components: state.circuit.components.map((c) => (c.id === id ? { ...c, properties } : c)),
      });
    }),

  setSelection: (ids) =>
    set((state) => {
      const known = elementIds(state.circuit);
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
    const state = get();
    const next = state.wireDraft && commitWire(state.circuit, state.wireDraft, anchor);
    if (!next) return false;
    set({ ...record(state, next), wireDraft: null });
    return true;
  },

  cancelWire: () => set((state) => (state.wireDraft ? { wireDraft: null } : state)),

  clickWireAnchor: (anchor) => {
    if (get().wireDraft) get().finishWire(anchor);
    else get().startWire(anchor);
  },
}));
