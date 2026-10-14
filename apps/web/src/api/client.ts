import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { toCanonical } from '../project/circuitJson';
import type { Problem, SimulationResult, ValidationResult } from './types';

/** Tempo máximo de espera por uma resposta da API, em milissegundos. */
export const REQUEST_TIMEOUT_MS = 15_000;

/** URL base sem `/` final; vazio = mesma origem (o `vite dev` encaminha `/api` para o backend). */
export function normalizeBaseUrl(value: string | undefined): string {
  return (value ?? '').trim().replace(/\/+$/, '');
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

export type ApiErrorKind =
  'problem' | 'http' | 'network' | 'timeout' | 'aborted' | 'invalid-response';

/** Falha de um pedido à API, com a resposta `problem+json` quando existe. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly problem?: Problem;

  constructor(
    kind: ApiErrorKind,
    message: string,
    details: { status?: number; problem?: Problem } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = details.status;
    this.problem = details.problem;
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

function isProblem(value: unknown): value is Problem {
  return (
    isRecord(value) &&
    typeof value.title === 'string' &&
    typeof value.code === 'string' &&
    (value.errors === undefined || Array.isArray(value.errors))
  );
}

function isSimulationResult(value: unknown): value is SimulationResult {
  return (
    isRecord(value) &&
    value.status === 'success' &&
    isRecord(value.nodeVoltagesV) &&
    isRecord(value.components) &&
    Array.isArray(value.warnings)
  );
}

function isValidationResult(value: unknown): value is ValidationResult {
  return (
    isRecord(value) &&
    typeof value.valid === 'boolean' &&
    Array.isArray(value.errors) &&
    Array.isArray(value.warnings)
  );
}

export interface RequestOptions {
  signal?: AbortSignal;
  baseUrl?: string;
  timeoutMs?: number;
}

async function postJson<T>(
  path: string,
  body: unknown,
  isExpected: (value: unknown) => value is T,
  { signal, baseUrl = API_BASE_URL, timeoutMs = REQUEST_TIMEOUT_MS }: RequestOptions,
): Promise<T> {
  const url = `${baseUrl}${path}`;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', forwardAbort);

  try {
    let response: Response;
    let text: string;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json, application/problem+json',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      text = await response.text();
    } catch {
      if (timedOut) {
        throw new ApiError('timeout', `A API não respondeu em ${timeoutMs / 1000} s.`);
      }
      if (signal?.aborted) throw new ApiError('aborted', 'Pedido cancelado.');
      throw new ApiError(
        'network',
        `Não foi possível contactar a API (${url}). Verifique se o servidor está a correr.`,
      );
    }

    let data: unknown;
    try {
      data = text ? JSON.parse(text) : undefined;
    } catch {
      data = undefined;
    }

    if (!response.ok) {
      if (isProblem(data)) {
        const problem: Problem = { ...data, errors: data.errors ?? [] };
        throw new ApiError('problem', problem.detail || problem.title, {
          status: response.status,
          problem,
        });
      }
      throw new ApiError('http', `A API respondeu com o erro HTTP ${response.status}.`, {
        status: response.status,
      });
    }
    if (!isExpected(data)) {
      throw new ApiError('invalid-response', 'A API devolveu uma resposta inesperada.', {
        status: response.status,
      });
    }
    return data;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', forwardAbort);
  }
}

/** `POST /api/v1/circuits/simulate` com o documento canónico (sem `nets`). */
export function simulateCircuit(
  circuit: CircuitDocument,
  options: RequestOptions = {},
): Promise<SimulationResult> {
  return postJson('/api/v1/circuits/simulate', toCanonical(circuit), isSimulationResult, options);
}

/** `POST /api/v1/circuits/validate` com o documento canónico (sem `nets`). */
export function validateCircuit(
  circuit: CircuitDocument,
  options: RequestOptions = {},
): Promise<ValidationResult> {
  return postJson('/api/v1/circuits/validate', toCanonical(circuit), isValidationResult, options);
}

/** Converte qualquer falha numa `ApiError` (erros inesperados ficam como falha de rede). */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError('network', error instanceof Error ? error.message : String(error));
}
