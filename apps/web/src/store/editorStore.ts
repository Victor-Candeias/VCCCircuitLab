import type { CircuitDocument, Point } from '@vcccircuitlab/circuit-schema';
import { create } from 'zustand';
import { GRID_SIZE } from '../editor/catalog';
import { demoCircuit } from '../editor/demoCircuit';
import { snapPoint } from '../editor/geometry';

/**
 * Estado do editor. O `circuit` é o documento canónico (modelo elétrico + geometria persistida);
 * o estado de vista (seleção) vive à parte e nunca é gravado no documento.
 */
export interface EditorState {
  circuit: CircuitDocument;
  selectedIds: string[];
  loadCircuit: (circuit: CircuitDocument) => void;
  /** Move a âncora de um componente, com snap à grelha. */
  moveComponent: (id: string, anchor: Point) => void;
  setSelection: (ids: readonly string[]) => void;
}

const sameIds = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((id, i) => id === b[i]);

export const useEditorStore = create<EditorState>()((set) => ({
  circuit: demoCircuit,
  selectedIds: [],

  loadCircuit: (circuit) => set({ circuit, selectedIds: [] }),

  moveComponent: (id, anchor) =>
    set((state) => {
      const position = snapPoint(anchor, GRID_SIZE);
      const current = state.circuit.components.find((c) => c.id === id);
      if (!current || (current.position.x === position.x && current.position.y === position.y)) {
        return state;
      }
      return {
        circuit: {
          ...state.circuit,
          components: state.circuit.components.map((c) => (c.id === id ? { ...c, position } : c)),
        },
      };
    }),

  setSelection: (ids) =>
    set((state) => {
      const known = new Set(state.circuit.components.map((c) => c.id));
      const next = [...new Set(ids)].filter((id) => known.has(id));
      return sameIds(next, state.selectedIds) ? state : { selectedIds: next };
    }),
}));
