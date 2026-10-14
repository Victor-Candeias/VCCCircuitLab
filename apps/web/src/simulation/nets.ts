import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { deriveConnectivity, netIds, type Connectivity } from '../editor/connectivity';
import type { Highlight } from '../editor/flowNodes';

/** Rede elétrica com o ID que a API lhe dá (`N1`…) e os seus terminais. */
export interface CircuitNet {
  id: string;
  terminals: string[];
}

interface NetIndex {
  nets: CircuitNet[];
  connectivity: Connectivity;
}

const cache = new WeakMap<CircuitDocument, NetIndex>();

function netIndex(circuit: CircuitDocument): NetIndex {
  let index = cache.get(circuit);
  if (!index) {
    const connectivity = deriveConnectivity(circuit);
    const ids = netIds(circuit, connectivity.nets.length);
    index = {
      connectivity,
      nets: connectivity.nets.map((terminals, i) => ({ id: ids[i], terminals })),
    };
    cache.set(circuit, index);
  }
  return index;
}

/** Redes do circuito pela ordem e com os IDs da API (`nodeVoltagesV`, `refs` dos erros). */
export const circuitNets = (circuit: CircuitDocument): CircuitNet[] => netIndex(circuit).nets;

/** Fios, junções e terminais da rede `netId`, ou `null` se não existir. */
export function netHighlight(circuit: CircuitDocument, netId: string | null): Highlight | null {
  if (!netId) return null;
  const { nets, connectivity } = netIndex(circuit);
  const index = nets.findIndex((n) => n.id === netId);
  if (index === -1) return null;
  const members = (map: Map<string, number>) =>
    new Set([...map].filter(([, net]) => net === index).map(([id]) => id));
  return {
    wires: members(connectivity.netOfWire),
    junctions: members(connectivity.netOfJunction),
    terminals: new Set(nets[index].terminals),
  };
}
