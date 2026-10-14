import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { parseTerminal } from './wiring';

/** Conectividade derivada de `wires` + `junctions` (a fonte de verdade; `nets` é ignorado). */
export interface Connectivity {
  /**
   * Redes com pelo menos um terminal, pela ordem do primeiro terminal (ordem dos componentes e
   * dos pinos), tal como o normalizador da API. As junções só fazem de ponte.
   */
  nets: string[][];
  netOfTerminal: Map<string, number>;
  netOfJunction: Map<string, number>;
  netOfWire: Map<string, number>;
}

/**
 * Agrupa terminais em redes: dois fios só ficam ligados se partilharem uma extremidade
 * (terminal ou junção); cruzamentos visuais não ligam. Extremidades inexistentes são ignoradas.
 */
export function deriveConnectivity(circuit: CircuitDocument): Connectivity {
  const parent = new Map<string, string>();
  const find = (node: string): string => {
    let root = node;
    while (parent.get(root) !== root) root = parent.get(root)!;
    for (let n = node; n !== root;) {
      const next = parent.get(n)!;
      parent.set(n, root);
      n = next;
    }
    return root;
  };

  const terminals = circuit.components.flatMap((c) => c.pins.map((p) => `${c.id}.${p}`));
  const junctionIds = (circuit.junctions ?? []).map((j) => j.id);
  const key = (endpoint: string) => (parseTerminal(endpoint) ? `t:${endpoint}` : `j:${endpoint}`);
  for (const node of [...terminals.map((t) => `t:${t}`), ...junctionIds.map((j) => `j:${j}`)]) {
    parent.set(node, node);
  }
  for (const wire of circuit.wires) {
    const [a, b] = [key(wire.from), key(wire.to)];
    if (parent.has(a) && parent.has(b)) parent.set(find(a), find(b));
  }

  const indexOfRoot = new Map<string, number>();
  const nets: string[][] = [];
  const netOfTerminal = new Map<string, number>();
  for (const terminal of terminals) {
    const root = find(`t:${terminal}`);
    let index = indexOfRoot.get(root);
    if (index === undefined) {
      index = nets.push([]) - 1;
      indexOfRoot.set(root, index);
    }
    nets[index].push(terminal);
    netOfTerminal.set(terminal, index);
  }

  const netOf = (node: string) => (parent.has(node) ? indexOfRoot.get(find(node)) : undefined);
  const netOfJunction = new Map<string, number>();
  for (const id of junctionIds) {
    const index = netOf(`j:${id}`);
    if (index !== undefined) netOfJunction.set(id, index);
  }
  const netOfWire = new Map<string, number>();
  for (const wire of circuit.wires) {
    const index = netOf(key(wire.from)) ?? netOf(key(wire.to));
    if (index !== undefined) netOfWire.set(wire.id, index);
  }
  return { nets, netOfTerminal, netOfJunction, netOfWire };
}

/**
 * IDs das redes (`N1`…), como os gera o normalizador da API quando o documento não traz `nets`:
 * sequenciais, saltando IDs já usados por componentes, junções ou fios.
 */
export function netIds(circuit: CircuitDocument, count: number): string[] {
  const taken = new Set([
    ...circuit.components.map((c) => c.id),
    ...(circuit.junctions ?? []).map((j) => j.id),
    ...circuit.wires.map((w) => w.id),
  ]);
  const ids: string[] = [];
  for (let n = 1; ids.length < count; n += 1) {
    if (!taken.has(`N${n}`)) ids.push(`N${n}`);
  }
  return ids;
}
