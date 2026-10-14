import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { create } from 'zustand';
import { ApiError, simulateCircuit, toApiError } from '../api/client';
import type { SimulationResult } from '../api/types';

/** Estado da última simulação; `circuit` é o documento exato que foi enviado à API. */
export type SimulationState =
  | { status: 'idle' }
  | { status: 'running'; circuit: CircuitDocument }
  | { status: 'success'; circuit: CircuitDocument; result: SimulationResult }
  | { status: 'error'; circuit: CircuitDocument; error: ApiError };

export interface SimulationStore {
  simulation: SimulationState;
  /** Rede destacada no canvas (`N1`…), ou `null`. */
  highlightedNet: string | null;
  /** Simula o circuito; um pedido anterior ainda em curso é cancelado. */
  simulate: (circuit: CircuitDocument) => Promise<void>;
  setHighlightedNet: (netId: string | null) => void;
  reset: () => void;
}

let inFlight: AbortController | null = null;

export const useSimulationStore = create<SimulationStore>()((set) => ({
  simulation: { status: 'idle' },
  highlightedNet: null,

  simulate: async (circuit) => {
    inFlight?.abort();
    const controller = new AbortController();
    inFlight = controller;
    set({ simulation: { status: 'running', circuit }, highlightedNet: null });
    try {
      const result = await simulateCircuit(circuit, { signal: controller.signal });
      if (inFlight === controller) set({ simulation: { status: 'success', circuit, result } });
    } catch (error) {
      if (inFlight === controller) {
        set({ simulation: { status: 'error', circuit, error: toApiError(error) } });
      }
    } finally {
      if (inFlight === controller) inFlight = null;
    }
  },

  setHighlightedNet: (netId) =>
    set((state) => (state.highlightedNet === netId ? state : { highlightedNet: netId })),

  reset: () => {
    inFlight?.abort();
    inFlight = null;
    set({ simulation: { status: 'idle' }, highlightedNet: null });
  },
}));

/** A simulação corresponde ao circuito atual (sem alterações desde que foi pedida)? */
export const isCurrent = (simulation: SimulationState, circuit: CircuitDocument) =>
  simulation.status !== 'idle' && simulation.circuit === circuit;
