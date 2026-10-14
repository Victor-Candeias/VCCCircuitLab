/** Tipos do contrato da API (`Docs/arquitetura_simulador_circuitos.md` §8). */

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

export interface ValidationResult {
  valid: boolean;
  errors: CircuitIssue[];
  warnings: CircuitIssue[];
  nets: { id: string; terminals: string[] }[] | null;
}

/** Conta criada por `POST /api/v1/users` (a API nunca devolve a password). */
export interface UserAccount {
  id: string;
  name: string;
  email: string;
  createdAt: string;
}
