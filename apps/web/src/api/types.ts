/** Tipos do contrato da API (`Docs/arquitetura_simulador_circuitos.md` §8). */

import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';

/** Erro ou aviso de circuito: código estável, mensagem em português e elementos envolvidos. */
export interface CircuitIssue {
  code: string;
  message: string;
  /** IDs de componentes, junções, fios, terminais (`R1.a`) ou redes (`N1`). */
  refs: string[];
  /** JSON Pointer (RFC 6901) nos erros de esquema. */
  pointer?: string | null;
}

/** Resposta de erro `application/problem+json` (RFC 9457). */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail?: string | null;
  instance?: string | null;
  code: string;
  errors: CircuitIssue[];
}

/** Valores DC de um componente (convenção passiva: `powerW < 0` quando fornece energia). */
export interface ComponentValues {
  voltageV: number;
  currentA: number;
  powerW: number;
}

export interface SimulationResult {
  analysis: 'dc_operating_point';
  status: 'success';
  /** Tensão de cada rede (`N1`…) em relação à terra. */
  nodeVoltagesV: Record<string, number>;
  components: Record<string, ComponentValues>;
  warnings: CircuitIssue[];
}

/** Séries de um componente na análise transitória (um valor por instante de `timeS`). */
export interface ComponentSeries {
  voltageV: number[];
  currentA: number[];
  powerW: number[];
}

/** Resposta da análise transitória: degrau em t = 0 a partir das condições iniciais. */
export interface TransientResult {
  analysis: 'transient';
  status: 'success';
  /** Instantes (equidistantes), de 0 a `stopTimeS`. */
  timeS: number[];
  /** Série da tensão de cada rede (`N1`…) em relação à terra. */
  nodeVoltagesV: Record<string, number[]>;
  components: Record<string, ComponentSeries>;
  warnings: CircuitIssue[];
}

/** Parâmetros da análise transitória (segundos). */
export interface TransientParameters {
  stopTimeS: number;
  timeStepS: number;
}

export interface ValidationResult {
  valid: boolean;
  errors: CircuitIssue[];
  warnings: CircuitIssue[];
  nets: { id: string; terminals: string[] }[] | null;
}

/** Resposta de `POST /api/v1/circuits/import/spice` (F2-05). */
/** Resposta de `POST /api/v1/circuits/generate/text` (F2-06). */
export interface GenerateTextResult {
  /** Template escolhido pelo parser (ex.: `series_dc`). */
  template: string;
  title: string;
  /** Parâmetros do template, já validados pela API. */
  parameters: Record<string, unknown>;
  /** Resumo legível do circuito interpretado. */
  summary: string;
  /** Valores assumidos por omissão ou interpretações a confirmar. */
  assumptions: string[];
  /** Circuito gerado e validado (com `nets`). */
  circuit: CircuitDocument;
  /** Avisos do validador sobre o circuito gerado. */
  warnings: CircuitIssue[];
}

export interface SpiceImportResult {
  /** Documento canónico (sem `nets`). */
  circuit: CircuitDocument;
  /** Avisos da tradução (diretivas ignoradas, modelos aproximados…), com o número da linha. */
  warnings: CircuitIssue[];
  /** Erros e avisos do validador sobre o circuito importado. */
  issues: CircuitIssue[];
}

export type UserRole = 'USER' | 'ADMIN';

/** Conta devolvida pela API (a API nunca devolve a password). */
export interface UserAccount {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  createdAt: string;
}
