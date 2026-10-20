import type { CircuitDocument, ComponentCatalog } from '@vcccircuitlab/circuit-schema';
import { toCanonical } from '../project/circuitJson';
import type {
  Problem,
  SimulationResult,
  SpiceImportResult,
  TransientParameters,
  TransientResult,
  UserAccount,
  ValidationResult,
} from './types';

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

function isTransientResult(value: unknown): value is TransientResult {
  return (
    isRecord(value) &&
    value.status === 'success' &&
    value.analysis === 'transient' &&
    Array.isArray(value.timeS) &&
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

function isCircuitDocument(value: unknown): value is CircuitDocument {
  return (
    isRecord(value) &&
    value.schemaVersion === '1.0' &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    Array.isArray(value.components) &&
    Array.isArray(value.wires)
  );
}

export interface RequestOptions {
  signal?: AbortSignal;
  baseUrl?: string;
  timeoutMs?: number;
}

let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

/** Token de sessão enviado em `Authorization: Bearer` em todos os pedidos (`null` = nenhum). */
export function setAuthToken(token: string | null): void {
  authToken = token;
}

/** Chamado quando um pedido com token recebe 401 (sessão expirada ou terminada noutro lado). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

/** Aceita qualquer corpo (ex.: 204 sem conteúdo). */
function isAnything(value: unknown): value is unknown {
  void value;
  return true;
}

async function requestJson<T>(
  method: 'GET' | 'POST',
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
      const sentToken = authToken;
      const headers: Record<string, string> = {
        Accept: 'application/json, application/problem+json',
      };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      if (sentToken) headers.Authorization = `Bearer ${sentToken}`;
      response = await fetch(url, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      if (response.status === 401 && sentToken && sentToken === authToken) onUnauthorized?.();
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
      throw new ApiError(
        'http',
        `A API devolveu um erro (HTTP ${response.status}). Tente novamente mais tarde.`,
        { status: response.status },
      );
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
  return requestJson(
    'POST',
    '/api/v1/circuits/simulate',
    toCanonical(circuit),
    isSimulationResult,
    options,
  );
}

/** `POST /api/v1/circuits/simulate/transient` com o documento canónico e a duração/passo. */
export function simulateTransient(
  circuit: CircuitDocument,
  parameters: TransientParameters,
  options: RequestOptions = {},
): Promise<TransientResult> {
  return requestJson(
    'POST',
    '/api/v1/circuits/simulate/transient',
    { circuit: toCanonical(circuit), ...parameters },
    isTransientResult,
    options,
  );
}

/** `POST /api/v1/circuits/validate` com o documento canónico (sem `nets`). */
export function validateCircuit(
  circuit: CircuitDocument,
  options: RequestOptions = {},
): Promise<ValidationResult> {
  return requestJson(
    'POST',
    '/api/v1/circuits/validate',
    toCanonical(circuit),
    isValidationResult,
    options,
  );
}

/** Parâmetros de um template de geração (ver `GENERATE_TEMPLATES`); a API valida os valores. */
export type GenerateParameters = Record<string, number | boolean | number[]>;

/**
 * `POST /api/v1/circuits/generate`: devolve o documento canónico do template, já normalizado
 * (com `nets`); o chamador deve descartá-los com `toCanonical` antes de carregar no editor
 * (tal como os outros documentos importados — `nets` é sempre derivado, nunca fonte de verdade).
 */
export function generateCircuit(
  template: string,
  parameters: GenerateParameters,
  options: RequestOptions = {},
): Promise<CircuitDocument> {
  return requestJson(
    'POST',
    '/api/v1/circuits/generate',
    { template, parameters },
    isCircuitDocument,
    options,
  );
}

function isSpiceNetlist(value: unknown): value is { netlist: string } {
  return isRecord(value) && typeof value.netlist === 'string';
}

function isSpiceImportResult(value: unknown): value is SpiceImportResult {
  return (
    isRecord(value) &&
    isCircuitDocument(value.circuit) &&
    Array.isArray(value.warnings) &&
    Array.isArray(value.issues)
  );
}

/** `POST /api/v1/circuits/export/spice`: netlist SPICE do circuito (texto `.cir`). */
export async function exportSpice(
  circuit: CircuitDocument,
  options: RequestOptions = {},
): Promise<string> {
  const result = await requestJson(
    'POST',
    '/api/v1/circuits/export/spice',
    toCanonical(circuit),
    isSpiceNetlist,
    options,
  );
  return result.netlist;
}

/** `POST /api/v1/circuits/import/spice`: circuito traduzido da netlist, com avisos. */
export function importSpice(
  netlist: string,
  options: RequestOptions = {},
): Promise<SpiceImportResult> {
  return requestJson(
    'POST',
    '/api/v1/circuits/import/spice',
    { netlist },
    isSpiceImportResult,
    options,
  );
}

function isComponentCatalog(value: unknown): value is ComponentCatalog {
  return (
    isRecord(value) &&
    typeof value.catalogVersion === 'string' &&
    typeof value.gridSize === 'number' &&
    value.gridSize > 0 &&
    Array.isArray(value.components) &&
    value.components.length > 0 &&
    value.components.every(
      (c) =>
        isRecord(c) &&
        typeof c.type === 'string' &&
        Array.isArray(c.pins) &&
        isRecord(c.size) &&
        isRecord(c.properties),
    )
  );
}

/** `GET /api/v1/components`: catálogo de componentes (fonte: coleção `templates` do MongoDB). */
export function getComponents(options: RequestOptions = {}): Promise<ComponentCatalog> {
  return requestJson('GET', '/api/v1/components', undefined, isComponentCatalog, options);
}

function isUserAccount(value: unknown): value is UserAccount {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.email === 'string' &&
    (value.role === 'USER' || value.role === 'ADMIN') &&
    typeof value.createdAt === 'string'
  );
}

export interface NewUser {
  name: string;
  email: string;
  password: string;
  passwordConfirm: string;
}

/** `POST /api/v1/users`: cria a conta (a API guarda os dados encriptados e só o hash da password). */
export function createUser(user: NewUser, options: RequestOptions = {}): Promise<UserAccount> {
  return requestJson('POST', '/api/v1/users', user, isUserAccount, options);
}

export interface LoginResult {
  accessToken: string;
  tokenType: 'bearer';
  expiresAt: string;
  user: UserAccount;
}

function isLoginResult(value: unknown): value is LoginResult {
  return (
    isRecord(value) &&
    typeof value.accessToken === 'string' &&
    value.tokenType === 'bearer' &&
    typeof value.expiresAt === 'string' &&
    isUserAccount(value.user)
  );
}

/** `POST /api/v1/auth/login`: devolve o token de sessão e o utilizador. */
export function login(
  credentials: { email: string; password: string },
  options: RequestOptions = {},
): Promise<LoginResult> {
  return requestJson('POST', '/api/v1/auth/login', credentials, isLoginResult, options);
}

/** `GET /api/v1/auth/me`: utilizador da sessão atual (exige `setAuthToken`). */
export function getCurrentUser(options: RequestOptions = {}): Promise<UserAccount> {
  return requestJson('GET', '/api/v1/auth/me', undefined, isUserAccount, options);
}

/** `POST /api/v1/auth/logout`: termina a sessão atual no servidor. */
export async function logoutSession(options: RequestOptions = {}): Promise<void> {
  await requestJson('POST', '/api/v1/auth/logout', undefined, isAnything, options);
}

/** Converte qualquer falha numa `ApiError` (erros inesperados ficam como falha de rede). */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  // Erro verdadeiramente inesperado (bug, não uma falha de rede/HTTP já tratada acima): regista
  // os detalhes técnicos na consola, mas mostra ao utilizador uma mensagem genérica em PT-PT.
  console.error('Erro inesperado ao contactar a API:', error);
  return new ApiError('network', 'Ocorreu um erro inesperado. Tente novamente.');
}
