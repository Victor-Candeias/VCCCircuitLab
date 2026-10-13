import type {
  CircuitDocument,
  Component,
  Junction,
  Point,
  Rotation,
  Wire,
  WireEndpoint,
} from '@vcccircuitlab/circuit-schema';
import { getComponentDefinition } from './catalog';
import { snapToGrid } from './geometry';

/**
 * Extremidade de um fio a ser desenhado: um terminal, uma junção existente ou um ponto
 * sobre um fio existente (convertido numa junção explícita só quando o fio é confirmado).
 */
export type WireAnchor =
  | { kind: 'terminal'; ref: string }
  | { kind: 'junction'; id: string }
  | { kind: 'wire'; wireId: string; point: Point };

export interface WireDraft {
  start: WireAnchor;
  /** Pontos intermédios já fixados (ortogonais), excluindo as extremidades. */
  waypoints: Point[];
}

const samePoint = (a: Point, b: Point) => a.x === b.x && a.y === b.y;

/** Rotação horária (eixo y para baixo) de um vetor relativo à âncora. */
export function rotateOffset(offset: Point, rotation: Rotation): Point {
  switch (rotation) {
    case 90:
      return { x: -offset.y + 0, y: offset.x + 0 };
    case 180:
      return { x: -offset.x + 0, y: -offset.y + 0 };
    case 270:
      return { x: offset.y + 0, y: -offset.x + 0 };
    default:
      return offset;
  }
}

/** Posição de um pino relativa à âncora do componente, já com a rotação aplicada. */
export function pinOffset(component: Component, pinId: string): Point | undefined {
  const pin = getComponentDefinition(component.type)?.pins.find((p) => p.id === pinId);
  return pin ? rotateOffset(pin.position, component.rotation) : undefined;
}

export const parseTerminal = (ref: string): { componentId: string; pinId: string } | undefined => {
  const dot = ref.indexOf('.');
  return dot > 0 ? { componentId: ref.slice(0, dot), pinId: ref.slice(dot + 1) } : undefined;
};

export function terminalPosition(circuit: CircuitDocument, ref: string): Point | undefined {
  const terminal = parseTerminal(ref);
  if (!terminal) return undefined;
  const component = circuit.components.find((c) => c.id === terminal.componentId);
  if (!component?.pins.includes(terminal.pinId)) return undefined;
  const offset = pinOffset(component, terminal.pinId);
  return offset && { x: component.position.x + offset.x, y: component.position.y + offset.y };
}

const findJunction = (circuit: CircuitDocument, id: string): Junction | undefined =>
  circuit.junctions?.find((j) => j.id === id);

/** Posição absoluta de uma extremidade de fio (terminal `C.p` ou junção). */
export const endpointPosition = (
  circuit: CircuitDocument,
  endpoint: WireEndpoint,
): Point | undefined =>
  endpoint.includes('.')
    ? terminalPosition(circuit, endpoint)
    : findJunction(circuit, endpoint)?.position;

export function anchorPosition(circuit: CircuitDocument, anchor: WireAnchor): Point | undefined {
  switch (anchor.kind) {
    case 'terminal':
      return terminalPosition(circuit, anchor.ref);
    case 'junction':
      return findJunction(circuit, anchor.id)?.position;
    case 'wire':
      return anchor.point;
  }
}

/** Remove pontos repetidos e pontos intermédios colineares (mantém as extremidades). */
export function simplifyPath(points: readonly Point[]): Point[] {
  const deduped = points.filter((p, i) => i === 0 || !samePoint(p, points[i - 1]));
  return deduped.filter((p, i) => {
    if (i === 0 || i === deduped.length - 1) return true;
    const prev = deduped[i - 1];
    const next = deduped[i + 1];
    return !((prev.x === p.x && p.x === next.x) || (prev.y === p.y && p.y === next.y));
  });
}

/** Troço ortogonal de `from` até `to`: canto horizontal-primeiro quando não estão alinhados. */
export const routeTo = (from: Point, to: Point): Point[] =>
  from.x === to.x || from.y === to.y ? [to] : [{ x: to.x, y: from.y }, to];

/** Torna um traçado ortogonal, inserindo um canto em cada troço diagonal. */
export function orthogonalize(points: readonly Point[]): Point[] {
  if (points.length === 0) return [];
  const result = [points[0]];
  for (let i = 1; i < points.length; i++) {
    result.push(...routeTo(result[result.length - 1], points[i]));
  }
  return simplifyPath(result);
}

/**
 * Traçado completo de um fio (extremidades + waypoints), sempre ortogonal: se um componente
 * foi movido e um troço ficou diagonal, é desenhado com um canto (o documento não é alterado).
 */
export function wirePath(circuit: CircuitDocument, wire: Wire): Point[] | undefined {
  const from = endpointPosition(circuit, wire.from);
  const to = endpointPosition(circuit, wire.to);
  if (!from || !to) return undefined;
  return orthogonalize([from, ...wire.waypoints, to]);
}

export const pathToSvg = (points: readonly Point[]): string =>
  points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

const clamp = (value: number, a: number, b: number) =>
  Math.min(Math.max(value, Math.min(a, b)), Math.max(a, b));

/**
 * Ponto do traçado mais próximo de `target`, encaixado na grelha ao longo do troço.
 * Devolve o índice do troço (entre `points[segment]` e `points[segment + 1]`).
 */
export function nearestPointOnPath(
  points: readonly Point[],
  target: Point,
  grid: number,
): { point: Point; segment: number } | undefined {
  let best: { point: Point; segment: number; distance: number } | undefined;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    const point =
      a.y === b.y
        ? { x: clamp(snapToGrid(clamp(target.x, a.x, b.x), grid), a.x, b.x), y: a.y }
        : { x: a.x, y: clamp(snapToGrid(clamp(target.y, a.y, b.y), grid), a.y, b.y) };
    const distance = Math.hypot(point.x - target.x, point.y - target.y);
    if (!best || distance < best.distance) best = { point, segment: i, distance };
  }
  return best && { point: best.point, segment: best.segment };
}

/** Próximo ID livre `<prefix><n>` (os IDs são únicos em todo o documento). */
export function nextElementId(circuit: CircuitDocument, prefix: string): string {
  const used = new Set<string>([
    ...circuit.components.map((c) => c.id),
    ...(circuit.junctions ?? []).map((j) => j.id),
    ...circuit.wires.map((w) => w.id),
    ...(circuit.nets ?? []).map((n) => n.id),
  ]);
  const pattern = new RegExp(`^${prefix}(\\d+)$`);
  let n = 1;
  for (const id of used) {
    const match = pattern.exec(id);
    if (match) n = Math.max(n, Number(match[1]) + 1);
  }
  while (used.has(`${prefix}${n}`)) n++;
  return `${prefix}${n}`;
}

/**
 * Resolve uma âncora numa extremidade do documento. Um ponto sobre um fio divide-o em dois
 * e cria uma junção explícita nesse ponto (exceto se coincidir com uma extremidade do fio).
 */
function resolveAnchor(
  circuit: CircuitDocument,
  anchor: WireAnchor,
): { circuit: CircuitDocument; endpoint: WireEndpoint } | undefined {
  if (anchor.kind === 'terminal') {
    return terminalPosition(circuit, anchor.ref) ? { circuit, endpoint: anchor.ref } : undefined;
  }
  if (anchor.kind === 'junction') {
    return findJunction(circuit, anchor.id) ? { circuit, endpoint: anchor.id } : undefined;
  }

  const wire = circuit.wires.find((w) => w.id === anchor.wireId);
  const path = wire && wirePath(circuit, wire);
  if (!wire || !path) return undefined;
  if (samePoint(anchor.point, path[0])) return { circuit, endpoint: wire.from };
  if (samePoint(anchor.point, path[path.length - 1])) return { circuit, endpoint: wire.to };

  const segment = path.findIndex((a, i) => {
    const b = path[i + 1];
    if (!b) return false;
    const { x, y } = anchor.point;
    return a.y === b.y
      ? y === a.y && x === clamp(x, a.x, b.x)
      : x === a.x && y === clamp(y, a.y, b.y);
  });
  if (segment < 0) return undefined;

  const junction: Junction = { id: nextElementId(circuit, 'J'), position: anchor.point };
  const withJunction = { ...circuit, junctions: [...(circuit.junctions ?? []), junction] };
  const second: Wire = {
    id: nextElementId(withJunction, 'W'),
    from: junction.id,
    to: wire.to,
    waypoints: simplifyPath([anchor.point, ...path.slice(segment + 1)]).slice(1, -1),
  };
  const first: Wire = {
    ...wire,
    to: junction.id,
    waypoints: simplifyPath([...path.slice(0, segment + 1), anchor.point]).slice(1, -1),
  };
  const wires = circuit.wires.flatMap((w) => (w.id === wire.id ? [first, second] : [w]));
  return { circuit: { ...withJunction, wires }, endpoint: junction.id };
}

/** Pontos intermédios do rascunho até `end`, ortogonais e sem redundâncias. */
export function draftWaypoints(start: Point, waypoints: readonly Point[], end: Point): Point[] {
  return orthogonalize([start, ...waypoints, end]).slice(1, -1);
}

const sameAnchor = (a: WireAnchor, b: WireAnchor) =>
  (a.kind === 'terminal' && b.kind === 'terminal' && a.ref === b.ref) ||
  (a.kind === 'junction' && b.kind === 'junction' && a.id === b.id) ||
  (a.kind === 'wire' && b.kind === 'wire' && a.wireId === b.wireId);

/**
 * Cria o fio do rascunho até `end`. Devolve `undefined` se a ligação for inválida
 * (extremidades iguais, no mesmo fio ou inexistentes).
 */
export function commitWire(
  circuit: CircuitDocument,
  draft: WireDraft,
  end: WireAnchor,
): CircuitDocument | undefined {
  if (sameAnchor(draft.start, end)) return undefined;
  const startPoint = anchorPosition(circuit, draft.start);
  const endPoint = anchorPosition(circuit, end);
  if (!startPoint || !endPoint) return undefined;

  const from = resolveAnchor(circuit, draft.start);
  const to = from && resolveAnchor(from.circuit, end);
  if (!from || !to || from.endpoint === to.endpoint) return undefined;

  const wire: Wire = {
    id: nextElementId(to.circuit, 'W'),
    from: from.endpoint,
    to: to.endpoint,
    waypoints: draftWaypoints(startPoint, draft.waypoints, endPoint),
  };
  return { ...to.circuit, wires: [...to.circuit.wires, wire] };
}
