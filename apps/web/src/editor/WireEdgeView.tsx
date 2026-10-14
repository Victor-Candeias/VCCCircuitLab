import { BaseEdge, type EdgeProps } from '@xyflow/react';
import type { WireEdge } from './flowNodes';
import { pathToSvg } from './wiring';

/** Fio ortogonal: o traçado vem do documento (extremidades + waypoints), não dos handles. */
export function WireEdgeView({ id, data, selected }: EdgeProps<WireEdge>) {
  if (!data) return null;
  return (
    <BaseEdge
      id={id}
      path={pathToSvg(data.points)}
      className={selected ? 'wire-edge is-selected' : 'wire-edge'}
      interactionWidth={12}
    />
  );
}
