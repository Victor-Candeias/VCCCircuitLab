import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { create } from 'zustand';
import { ApiError, simulateCircuit, simulateTransient, toApiError } from '../api/client';
import type { SimulationResult, TransientParameters, TransientResult } from '../api/types';

/** Ponto de funcionamento DC ou resposta no tempo (degrau em t = 0). */
export type AnalysisKind = 'dc' | 'transient';

/** Duração e passo iniciais da análise transitória: 10 ms com pontos a cada 10 µs. */
export const DEFAULT_TRANSIENT: TransientParameters = { stopTimeS: 10e-3, timeStepS: 10e-6 };

/** Estado da última simulação; `circuit` é o documento exato que foi enviado à API. */
export type SimulationState =
  | { status: 'idle' }
  | { status: 'running'; circuit: CircuitDocument }
  | { status: 'success'; circuit: CircuitDocument; result: SimulationResult | TransientResult }
  | { status: 'error'; circuit: CircuitDocument; error: ApiError };

export interface SimulationStore {
  simulation: SimulationState;
  /** Rede destacada no canvas (`N1`…), ou `null`. */
  highlightedNet: string | null;
  analysis: AnalysisKind;
  /** Parâmetros da transitória (`NaN` enquanto o campo é inválido). */
  transient: TransientParameters;
  /** Simula o circuito com a análise escolhida; um pedido anterior em curso é cancelado. */
  simulate: (circuit: CircuitDocument) => Promise<void>;
  setHighlightedNet: (netId: string | null) => void;
  /** Muda a análise; o resultado anterior deixa de corresponder e é descartado. */
  setAnalysis: (analysis: AnalysisKind) => void;
  /** Altera a duração e/ou o passo; o resultado anterior é descartado. */
  setTransient: (parameters: Partial<TransientParameters>) => void;
  reset: () => void;
}

let inFlight: AbortController | null = null;

const IDLE = { simulation: { status: 'idle' }, highlightedNet: null } as const;

function cancelInFlight() {
  inFlight?.abort();
  inFlight = null;
}

/** Os parâmetros da transitória são números finitos positivos (os limites ficam para a API). */
export const isValidTransient = ({ stopTimeS, timeStepS }: TransientParameters) =>
  Number.isFinite(stopTimeS) && stopTimeS > 0 && Number.isFinite(timeStepS) && timeStepS > 0;

export const useSimulationStore = create<SimulationStore>()((set, get) => ({
  simulation: { status: 'idle' },
  highlightedNet: null,
  analysis: 'dc',
  transient: DEFAULT_TRANSIENT,

  simulate: async (circuit) => {
    inFlight?.abort();
    const controller = new AbortController();
    inFlight = controller;
    const { analysis, transient } = get();
    set({ simulation: { status: 'running', circuit }, highlightedNet: null });
    try {
      const options = { signal: controller.signal };
      const result =
        analysis === 'transient'
          ? await simulateTransient(circuit, transient, options)
          : await simulateCircuit(circuit, options);
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

  setAnalysis: (analysis) => {
    if (analysis === get().analysis) return;
    cancelInFlight();
    set({ ...IDLE, analysis });
  },

  setTransient: (parameters) => {
    cancelInFlight();
    set((state) => ({ ...IDLE, transient: { ...state.transient, ...parameters } }));
  },

  reset: () => {
    cancelInFlight();
    set(IDLE);
  },
}));

/** A simulação corresponde ao circuito atual (sem alterações desde que foi pedida)? */
export const isCurrent = (simulation: SimulationState, circuit: CircuitDocument) =>
  simulation.status !== 'idle' && simulation.circuit === circuit;
