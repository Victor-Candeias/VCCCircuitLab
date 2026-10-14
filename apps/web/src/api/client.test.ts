import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { ApiError, normalizeBaseUrl, simulateCircuit, toApiError, validateCircuit } from './client';
import type { SimulationResult } from './types';

const result: SimulationResult = {
  analysis: 'dc_operating_point',
  status: 'success',
  nodeVoltagesV: { N1: 9, N2: 0 },
  components: { R1: { voltageV: 9, currentA: 0.09, powerW: 0.81 } },
  warnings: [],
};

const json = (body: unknown, status = 200, type = 'application/json') =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': type } });

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const failure = (promise: Promise<unknown>) =>
  promise.then(
    () => {
      throw new Error('devia falhar');
    },
    (error: unknown) => error as ApiError,
  );

describe('cliente da API', () => {
  test('normalizeBaseUrl tira espaços e barras finais; vazio = mesma origem', () => {
    expect(normalizeBaseUrl(undefined)).toBe('');
    expect(normalizeBaseUrl(' https://api.exemplo.pt// ')).toBe('https://api.exemplo.pt');
  });

  test('simulateCircuit envia o documento canónico (sem nets) por POST e devolve o resultado', async () => {
    fetchMock.mockResolvedValue(json(result));
    const withNets: CircuitDocument = {
      ...demoCircuit,
      nets: [{ id: 'N9', terminals: ['V1.positive'] }],
    };

    await expect(simulateCircuit(withNets, { baseUrl: 'https://api.exemplo.pt' })).resolves.toEqual(
      result,
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.exemplo.pt/api/v1/circuits/simulate');
    expect(init?.method).toBe('POST');
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    const body = JSON.parse(String(init?.body));
    expect(body).not.toHaveProperty('nets');
    expect(body.components).toHaveLength(4);
  });

  test('validateCircuit usa /validate', async () => {
    fetchMock.mockResolvedValue(json({ valid: true, errors: [], warnings: [], nets: [] }));
    await expect(validateCircuit(demoCircuit, { baseUrl: '' })).resolves.toMatchObject({
      valid: true,
    });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/circuits/validate');
  });

  test('erros problem+json ficam disponíveis com código, estado e lista de erros', async () => {
    const problem = {
      type: 'urn:vcccircuitlab:problem:invalid-circuit',
      title: 'Circuito inválido',
      status: 422,
      detail: 'Sem caminho condutor até à terra.',
      code: 'FLOATING_NET',
      errors: [{ code: 'FLOATING_NET', message: 'Sem caminho…', refs: ['N1', 'R1.a'] }],
    };
    fetchMock.mockResolvedValue(json(problem, 422, 'application/problem+json'));

    const error = await failure(simulateCircuit(demoCircuit));
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: 'problem', status: 422, problem });
    expect(error.message).toBe('Sem caminho condutor até à terra.');
  });

  test('erro HTTP sem problem+json', async () => {
    fetchMock.mockResolvedValue(new Response('Bad gateway', { status: 502 }));
    const error = await failure(simulateCircuit(demoCircuit));
    expect(error).toMatchObject({ kind: 'http', status: 502 });
    expect(error.message).toContain('502');
  });

  test('resposta 200 com forma inesperada', async () => {
    fetchMock.mockResolvedValue(json({ ok: true }));
    expect(await failure(simulateCircuit(demoCircuit))).toMatchObject({
      kind: 'invalid-response',
    });
  });

  test('falha de rede indica a URL e sugere verificar o servidor', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await failure(simulateCircuit(demoCircuit, { baseUrl: 'http://x:8000' }));
    expect(error.kind).toBe('network');
    expect(error.message).toContain('http://x:8000/api/v1/circuits/simulate');
  });

  const hangingFetch = (_url: RequestInfo | URL, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('', 'AbortError')));
    });

  test('pedido sem resposta esgota o tempo', async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(hangingFetch);
    const pending = failure(simulateCircuit(demoCircuit, { timeoutMs: 1000 }));
    await vi.advanceTimersByTimeAsync(1000);
    const error = await pending;
    expect(error.kind).toBe('timeout');
    expect(error.message).toBe('A API não respondeu em 1 s.');
  });

  test('o pedido pode ser cancelado', async () => {
    fetchMock.mockImplementation(hangingFetch);
    const controller = new AbortController();
    const pending = failure(simulateCircuit(demoCircuit, { signal: controller.signal }));
    controller.abort();
    expect((await pending).kind).toBe('aborted');
  });

  test('toApiError mantém ApiError e embrulha outros erros', () => {
    const original = new ApiError('http', 'x');
    expect(toApiError(original)).toBe(original);
    expect(toApiError(new Error('boom'))).toMatchObject({ kind: 'network', message: 'boom' });
  });
});
