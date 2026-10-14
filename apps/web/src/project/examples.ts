import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import fonteResistencia from '@vcccircuitlab/circuit-schema/examples/fonte-resistencia.json';
import paraleloJuncao from '@vcccircuitlab/circuit-schema/examples/paralelo-juncao.json';
import ramificado from '@vcccircuitlab/circuit-schema/examples/ramificado.json';
import { demoCircuit } from '../editor/demoCircuit';
import { toCanonical } from './circuitJson';

export interface CircuitExample {
  id: string;
  label: string;
  circuit: CircuitDocument;
}

// Os JSON importados têm tipos literais largos (string, number[]); os documentos são validados
// pelos testes do pacote e por `examples.test.ts`.
const doc = (json: unknown) => toCanonical(json as CircuitDocument);

/** Circuitos de exemplo do menu Projeto (fixtures válidas de `@vcccircuitlab/circuit-schema`). */
export const CIRCUIT_EXAMPLES: readonly CircuitExample[] = [
  { id: 'demo', label: 'Série: fonte, resistência e lâmpada', circuit: demoCircuit },
  { id: 'fonte-resistencia', label: 'Fonte de 12 V e resistência', circuit: doc(fonteResistencia) },
  { id: 'paralelo-juncao', label: 'Paralelo com junções', circuit: doc(paraleloJuncao) },
  { id: 'ramificado', label: 'Ramificado (ramos, ponte e cruzamento)', circuit: doc(ramificado) },
];
