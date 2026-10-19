import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import {
  ApiError,
  createUser,
  generateCircuit,
  getComponents,
  getCurrentUser,
  login,
  logoutSession,
  normalizeBaseUrl,
  setAuthToken,
  setUnauthorizedHandler,
  simulateCircuit,
  simulateTransient,
  toApiError,
  validateCircuit,
} from './client';
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
  setAuthToken(null);
  setUnauthorizedHandler(null);
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

  test('simulateTransient envia o circuito canónico com a duração e o passo', async () => {
    const transient = {
      analysis: 'transient',
      status: 'success',
      timeS: [0, 1e-3],
      nodeVoltagesV: { N1: [9, 9] },
      components: {},
      warnings: [],
    };
    fetchMock.mockResolvedValueOnce(json(transient)).mockResolvedValueOnce(json(result));
    const parameters = { stopTimeS: 1e-3, timeStepS: 1e-3 };

    await expect(simulateTransient(demoCircuit, parameters, { baseUrl: '' })).resolves.toEqual(
      transient,
    );
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/circuits/simulate/transient');
    const body = JSON.parse(String(init?.body));
    expect(body).toMatchObject(parameters);
    expect(body.circuit.components).toHaveLength(4);
    expect(body.circuit).not.toHaveProperty('nets');

    // Uma resposta DC não é um resultado transitório.
    expect(await failure(simulateTransient(demoCircuit, parameters))).toMatchObject({
      kind: 'invalid-response',
    });
  });

  test('validateCircuit usa /validate', async () => {
    fetchMock.mockResolvedValue(json({ valid: true, errors: [], warnings: [], nets: [] }));
    await expect(validateCircuit(demoCircuit, { baseUrl: '' })).resolves.toMatchObject({
      valid: true,
    });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/circuits/validate');
  });

  test('generateCircuit envia o template e os parâmetros por POST e devolve o documento', async () => {
    fetchMock.mockResolvedValue(json(demoCircuit));

    await expect(
      generateCircuit(
        'series_dc',
        { voltageV: 12, resistorsOhm: [100, 220] },
        { baseUrl: 'https://api.exemplo.pt' },
      ),
    ).resolves.toEqual(demoCircuit);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.exemplo.pt/api/v1/circuits/generate');
    expect(init?.method).toBe('POST');
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual({
      template: 'series_dc',
      parameters: { voltageV: 12, resistorsOhm: [100, 220] },
    });
  });

  test('generateCircuit rejeita uma resposta que não pareça um circuito', async () => {
    fetchMock.mockResolvedValue(json({ ok: true }));
    const error = await failure(generateCircuit('series_dc', { voltageV: 12 }));
    expect(error).toMatchObject({ kind: 'invalid-response' });
  });

  test('getComponents faz GET /api/v1/components e rejeita catálogos sem componentes', async () => {
    const body = {
      catalogVersion: '1.0',
      gridSize: 20,
      components: [{ type: 'resistor', pins: [], size: { width: 80, height: 40 }, properties: {} }],
    };
    fetchMock.mockResolvedValueOnce(json(body));
    await expect(getComponents({ baseUrl: '' })).resolves.toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/components');
    expect(init?.method).toBe('GET');

    fetchMock.mockResolvedValueOnce(json({ ...body, components: [] }));
    await expect(getComponents({ baseUrl: '' })).rejects.toMatchObject({
      kind: 'invalid-response',
    });
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

  test('createUser envia os dados por POST e devolve a conta criada', async () => {
    const account = {
      id: '1',
      name: 'Ana',
      email: 'ana@exemplo.pt',
      role: 'USER',
      createdAt: '2026-10-14T21:00:00Z',
    };
    fetchMock.mockResolvedValue(json(account, 201));
    const user = {
      name: 'Ana',
      email: 'ana@exemplo.pt',
      password: 'Abcdefg1!',
      passwordConfirm: 'Abcdefg1!',
    };

    await expect(createUser(user, { baseUrl: 'https://api.exemplo.pt' })).resolves.toEqual(account);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.exemplo.pt/api/v1/users');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual(user);
  });

  test('createUser expõe o problema 409 (email já registado)', async () => {
    const problem = {
      type: 'urn:vcccircuitlab:problem:email-already-registered',
      title: 'Email já registado',
      status: 409,
      code: 'EMAIL_ALREADY_REGISTERED',
      errors: [],
    };
    fetchMock.mockResolvedValue(json(problem, 409, 'application/problem+json'));

    const error = await failure(
      createUser({ name: 'A', email: 'a@b.pt', password: 'x', passwordConfirm: 'x' }),
    );

    expect(error.kind).toBe('problem');
    expect(error.status).toBe(409);
    expect(error.problem?.code).toBe('EMAIL_ALREADY_REGISTERED');
  });

  test('toApiError mantém ApiError e embrulha outros erros', () => {
    const original = new ApiError('http', 'x');
    expect(toApiError(original)).toBe(original);
    const wrapped = toApiError(new Error('boom'));
    expect(wrapped.kind).toBe('network');
    expect(wrapped.message).not.toContain('boom');
    expect(wrapped.message.length).toBeGreaterThan(0);
  });

  test('login envia as credenciais e devolve o token; sem token não há Authorization', async () => {
    const session = {
      accessToken: 'tok',
      tokenType: 'bearer',
      expiresAt: '2030-01-01T00:00:00Z',
      user: {
        id: '1',
        name: 'Ana',
        email: 'ana@exemplo.pt',
        role: 'USER',
        createdAt: '2026-10-14T21:00:00Z',
      },
    };
    fetchMock.mockResolvedValue(json(session));

    await expect(login({ email: 'ana@exemplo.pt', password: 'x' })).resolves.toEqual(session);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/auth/login');
    expect(init?.method).toBe('POST');
    expect(new Headers(init?.headers).has('Authorization')).toBe(false);
  });

  test('com token, os pedidos levam Authorization: Bearer (GET sem corpo)', async () => {
    const account = {
      id: '1',
      name: 'Ana',
      email: 'ana@exemplo.pt',
      role: 'USER',
      createdAt: '2026-10-14',
    };
    fetchMock.mockResolvedValue(json(account));
    setAuthToken('tok');

    await expect(getCurrentUser()).resolves.toEqual(account);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/auth/me');
    expect(init?.method).toBe('GET');
    expect(init?.body).toBeUndefined();
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer tok');
    expect(headers.has('Content-Type')).toBe(false);
  });

  test('logoutSession aceita a resposta 204 sem corpo', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    setAuthToken('tok');

    await expect(logoutSession()).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST');
  });

  test('401 com token chama o handler de sessão expirada', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    setAuthToken('tok');
    fetchMock.mockResolvedValue(
      json(
        { title: 'Autenticação necessária', code: 'NOT_AUTHENTICATED', errors: [] },
        401,
        'application/problem+json',
      ),
    );

    const error = await failure(simulateCircuit(demoCircuit));

    expect(error.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  test('401 sem token (login falhado) não chama o handler', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    fetchMock.mockResolvedValue(
      json({ title: 'Login inválido', code: 'INVALID_CREDENTIALS', errors: [] }, 401),
    );

    await failure(login({ email: 'a@b.pt', password: 'x' }));

    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
