import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import type { SimulationResult } from '../api/types';
import { demoCircuit } from '../editor/demoCircuit';
import { isCurrent, useSimulationStore } from './simulationStore';

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
});
