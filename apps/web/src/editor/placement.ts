import type {
  CircuitDocument,
  Component,
  ComponentDefinition,
  ComponentProperties,
  Point,
  Rotation,
} from '@vcccircuitlab/circuit-schema';
import { getComponentDefinition, GRID_SIZE } from './catalog';
import { snapPoint } from './geometry';
import { nextElementId } from './wiring';

/** Sentido de rotação: 90 = horário, -90 = anti-horário (eixo y para baixo). */
export type RotationStep = 90 | -90;

/** Rotação seguinte, normalizada para 0/90/180/270. */
export const rotateBy = (rotation: Rotation, step: RotationStep): Rotation =>
  ((((rotation + step) % 360) + 360) % 360) as Rotation;

/** Valores por omissão das propriedades do catálogo. */
export const defaultProperties = (definition: ComponentDefinition): ComponentProperties =>
  Object.fromEntries(
    Object.entries(definition.properties).map(([name, property]) => [name, property.default]),
  );

/**
 * Âncora livre mais próxima de `anchor` (encaixada na grelha): se já houver um componente
 * com a mesma âncora, desloca uma célula na diagonal até encontrar uma posição livre.
 */
export function freeAnchor(circuit: CircuitDocument, anchor: Point): Point {
  const taken = new Set(circuit.components.map((c) => `${c.position.x},${c.position.y}`));
  let point = snapPoint(anchor, GRID_SIZE);
  while (taken.has(`${point.x},${point.y}`)) {
    point = { x: point.x + GRID_SIZE, y: point.y + GRID_SIZE };
  }
  return point;
}

/**
 * Acrescenta uma nova instância de `type` (rotação 0, propriedades e pinos do catálogo) com a
 * âncora em `anchor` (com snap). Devolve `undefined` para tipos fora do catálogo ou
 * coordenadas não finitas.
 */
export function placeComponent(
  circuit: CircuitDocument,
  type: string,
  anchor: Point,
): { circuit: CircuitDocument; component: Component } | undefined {
  const definition = getComponentDefinition(type);
  if (!definition || !Number.isFinite(anchor.x) || !Number.isFinite(anchor.y)) return undefined;
  const [firstPin, ...otherPins] = definition.pins;
  const component: Component = {
    id: nextElementId(circuit, definition.idPrefix),
    type,
    position: freeAnchor(circuit, anchor),
    rotation: 0,
    properties: defaultProperties(definition),
    pins: [firstPin.id, ...otherPins.map((pin) => pin.id)],
  };
  return { circuit: { ...circuit, components: [...circuit.components, component] }, component };
}

/**
 * Roda os componentes indicados 90° em torno da própria âncora. Como as posições dos pinos
 * são múltiplos da grelha, continuam na grelha depois de rodar. Devolve o mesmo documento se
 * nenhum componente for afetado.
 */
export function rotateComponents(
  circuit: CircuitDocument,
  ids: Iterable<string>,
  step: RotationStep,
): CircuitDocument {
  const targets = new Set(ids);
  if (!circuit.components.some((c) => targets.has(c.id))) return circuit;
  return {
    ...circuit,
    components: circuit.components.map((c) =>
      targets.has(c.id) ? { ...c, rotation: rotateBy(c.rotation, step) } : c,
    ),
  };
}
