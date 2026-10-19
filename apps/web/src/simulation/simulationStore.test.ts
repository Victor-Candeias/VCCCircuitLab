import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import type { SimulationResult } from '../api/types';
import { demoCircuit } from '../editor/demoCircuit';
import {
  DEFAULT_TRANSIENT,
  isCurrent,
  isValidTransient,
  useSimulationStore,
} from './simulationStore';

const initialState = useSimulationStore.getState();
const fetchMock = vi.fn<typeof fetch>();

const result = (voltage: number): SimulationResult => ({
  analysis: 'dc_operating_point',
  status: 'success',
  nodeVoltagesV: { N1: voltage },
  components: {},
  warnings: [],
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  useSimulationStore.setState(initialState, true);
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

const store = () => useSimulationStore.getState();

describe('simulationStore', () => {
  test('simulate passa por running e guarda o resultado com o circuito simulado', async () => {
    fetchMock.mockResolvedValue(json(result(9)));
    store().setHighlightedNet('N1');
    const pending = store().simulate(demoCircuit);
    expect(store().simulation).toEqual({ status: 'running', circuit: demoCircuit });
    expect(store().highlightedNet).toBeNull();
    await pending;
    expect(store().simulation).toEqual({
      status: 'success',
      circuit: demoCircuit,
      result: result(9),
    });
    expect(isCurrent(store().simulation, demoCircuit)).toBe(true);
    expect(isCurrent(store().simulation, { ...demoCircuit })).toBe(false);
  });

  test('erros da API ficam no estado', async () => {
    fetchMock.mockResolvedValue(json({ title: 'Circuito inválido', code: 'X', status: 422 }, 422));
    await store().simulate(demoCircuit);
    const { simulation } = store();
    expect(simulation.status).toBe('error');
    expect(simulation.status === 'error' && simulation.error.problem?.code).toBe('X');
  });

  test('uma nova simulação cancela a anterior e ignora a sua resposta', async () => {
    let resolveFirst: (response: Response) => void = () => {};
    fetchMock
      .mockImplementationOnce(
        (_url, init) =>
          new Promise((resolve, reject) => {
            resolveFirst = resolve;
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('', 'AbortError')),
            );
          }),
      )
      .mockResolvedValueOnce(json(result(5)));
    const first = store().simulate(demoCircuit);
    const changed = { ...demoCircuit };
    await store().simulate(changed);
    resolveFirst(json(result(1)));
    await first;
    expect(store().simulation).toMatchObject({ status: 'success', circuit: changed });
    expect(store().simulation.status === 'success' && store().simulation).toMatchObject({
      result: { nodeVoltagesV: { N1: 5 } },
    });
  });

  test('reset volta ao estado inicial e isCurrent é falso sem simulação', () => {
    store().setHighlightedNet('N2');
    store().reset();
    expect(store().simulation).toEqual({ status: 'idle' });
    expect(store().highlightedNet).toBeNull();
    expect(isCurrent(store().simulation, demoCircuit)).toBe(false);
  });

  test('na análise transitória chama /simulate/transient com os parâmetros escolhidos', async () => {
    fetchMock.mockResolvedValue(
      json({
        analysis: 'transient',
        status: 'success',
        timeS: [0],
        nodeVoltagesV: {},
        components: {},
        warnings: [],
      }),
    );
    store().setAnalysis('transient');
    store().setTransient({ stopTimeS: 0.02 });
    expect(store().transient).toEqual({ ...DEFAULT_TRANSIENT, stopTimeS: 0.02 });
    await store().simulate(demoCircuit);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/circuits\/simulate\/transient$/);
    expect(JSON.parse(String(init?.body))).toMatchObject({ stopTimeS: 0.02, timeStepS: 10e-6 });
    expect(store().simulation).toMatchObject({
      status: 'success',
      result: { analysis: 'transient' },
    });
  });

  test('mudar a análise ou os parâmetros descarta o resultado anterior', async () => {
    fetchMock.mockResolvedValue(json(result(9)));
    await store().simulate(demoCircuit);
    store().setAnalysis('dc');
    expect(store().simulation.status).toBe('success');
    store().setAnalysis('transient');
    expect(store().simulation).toEqual({ status: 'idle' });

    await store().simulate(demoCircuit);
    store().setTransient({ timeStepS: 1e-6 });
    expect(store().simulation).toEqual({ status: 'idle' });
  });

  test('isValidTransient exige números finitos positivos', () => {
    expect(isValidTransient(DEFAULT_TRANSIENT)).toBe(true);
    expect(isValidTransient({ stopTimeS: Number.NaN, timeStepS: 1 })).toBe(false);
    expect(isValidTransient({ stopTimeS: 1, timeStepS: 0 })).toBe(false);
    expect(isValidTransient({ stopTimeS: Infinity, timeStepS: 1 })).toBe(false);
  });
});
