import type {
  CircuitDocument,
  Component,
  Junction,
  Point,
  Wire,
} from '@vcccircuitlab/circuit-schema';
import { getComponentDefinition } from './catalog';
import { nextElementId, parseTerminal } from './wiring';

/** Elementos copiados: componentes, junções e os fios com as duas extremidades entre eles. */
export interface CircuitFragment {
  components: Component[];
  junctions: Junction[];
  wires: Wire[];
}

/** ID do componente ou da junção de uma extremidade de fio (`R1.a` → `R1`, `J1` → `J1`). */
const endpointOwner = (endpoint: string) => parseTerminal(endpoint)?.componentId ?? endpoint;

/**
 * Apaga os componentes, junções e fios indicados. Os fios ligados a um componente ou junção
 * apagados também desaparecem (não ficam fios soltos), tal como as junções que ficam sem fios.
 * Devolve o mesmo documento se nada for apagado.
 */
export function deleteElements(circuit: CircuitDocument, ids: readonly string[]): CircuitDocument {
  const removed = new Set(ids);
  const junctions = circuit.junctions ?? [];
  const components = circuit.components.filter((c) => !removed.has(c.id));
  const keptJunctions = junctions.filter((j) => !removed.has(j.id));
  const gone = (endpoint: string) => removed.has(endpointOwner(endpoint));
  const wires = circuit.wires.filter((w) => !removed.has(w.id) && !gone(w.from) && !gone(w.to));
  if (
    components.length === circuit.components.length &&
    keptJunctions.length === junctions.length &&
    wires.length === circuit.wires.length
  ) {
    return circuit;
  }

  // Junções que só serviam os fios apagados ficariam como pontos soltos.
  const lostWires = circuit.wires.filter((w) => !wires.includes(w));
  const touchedByLost = new Set(lostWires.flatMap((w) => [w.from, w.to]));
  const stillUsed = new Set(wires.flatMap((w) => [w.from, w.to]));
  const finalJunctions = keptJunctions.filter(
    (j) => !touchedByLost.has(j.id) || stillUsed.has(j.id),
  );

  return circuit.junctions === undefined
    ? { ...circuit, components, wires }
    : { ...circuit, components, junctions: finalJunctions, wires };
}

/**
 * Fragmento a copiar: os componentes e junções indicados e os fios cujas duas extremidades
 * pertencem a eles. Devolve `undefined` se não houver componentes nem junções.
 */
export function copyFragment(
  circuit: CircuitDocument,
  ids: readonly string[],
): CircuitFragment | undefined {
  const selected = new Set(ids);
  const components = circuit.components.filter((c) => selected.has(c.id));
  const junctions = (circuit.junctions ?? []).filter((j) => selected.has(j.id));
  if (components.length === 0 && junctions.length === 0) return undefined;
  const owners = new Set([...components.map((c) => c.id), ...junctions.map((j) => j.id)]);
  const inside = (endpoint: string) => owners.has(endpointOwner(endpoint));
  const wires = circuit.wires.filter((w) => inside(w.from) && inside(w.to));
  return structuredClone({ components, junctions, wires });
}

const shift = (p: Point, offset: Point): Point => ({ x: p.x + offset.x, y: p.y + offset.y });

/** Prefixo de IDs para um componente colado (catálogo; senão, as letras do ID original). */
const idPrefixOf = (component: Component) =>
  getComponentDefinition(component.type)?.idPrefix ?? component.id.replace(/[\d_-]+$/, '');

/**
 * Cola um fragmento deslocado de `offset`, com novos IDs estáveis e únicos (`<prefixo><n>`
 * seguinte ao maior existente). Devolve o novo documento e os IDs dos componentes e junções
 * colados (a nova seleção).
 */
export function pasteFragment(
  circuit: CircuitDocument,
  fragment: CircuitFragment,
  offset: Point,
): { circuit: CircuitDocument; ids: string[] } {
  const components = [...circuit.components];
  const junctions = [...(circuit.junctions ?? [])];
  const wires = [...circuit.wires];
  const view = (): CircuitDocument => ({ ...circuit, components, junctions, wires });
  const idMap = new Map<string, string>();

  for (const component of fragment.components) {
    const id = nextElementId(view(), idPrefixOf(component));
    idMap.set(component.id, id);
    components.push({
      ...structuredClone(component),
      id,
      position: shift(component.position, offset),
    });
  }
  for (const junction of fragment.junctions) {
    const id = nextElementId(view(), 'J');
    idMap.set(junction.id, id);
    junctions.push({ id, position: shift(junction.position, offset) });
  }
  const remap = (endpoint: string) => {
    const terminal = parseTerminal(endpoint);
    return terminal ? `${idMap.get(terminal.componentId)}.${terminal.pinId}` : idMap.get(endpoint)!;
  };
  for (const wire of fragment.wires) {
    wires.push({
      id: nextElementId(view(), 'W'),
      from: remap(wire.from),
      to: remap(wire.to),
      waypoints: wire.waypoints.map((p) => shift(p, offset)),
    });
  }

  const next =
    circuit.junctions === undefined && junctions.length === 0
      ? { ...circuit, components, wires }
      : view();
  return { circuit: next, ids: [...idMap.values()] };
}
