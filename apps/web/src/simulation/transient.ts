import type { ComponentValues, TransientResult } from '../api/types';

/** Máximo de pontos desenhados por série; acima disto o gráfico é subamostrado. */
export const MAX_CHART_POINTS = 1000;

/** Grandeza desenhada: tensões de todas as redes, ou a tensão/corrente de um componente. */
export type Quantity = 'nets' | `voltage:${string}` | `current:${string}`;

export interface Plot {
  unit: 'V' | 'A';
  series: { key: string; label: string; values: number[] }[];
}

export function plotOf(result: TransientResult, quantity: Quantity): Plot {
  if (quantity === 'nets') {
    return {
      unit: 'V',
      series: Object.entries(result.nodeVoltagesV).map(([id, values]) => ({
        key: id,
        label: id,
        values,
      })),
    };
  }
  const separator = quantity.indexOf(':');
  const kind = quantity.slice(0, separator);
  const id = quantity.slice(separator + 1);
  const component = result.components[id];
  if (kind === 'current') {
    return {
      unit: 'A',
      series: [{ key: id, label: `I(${id})`, values: component?.currentA ?? [] }],
    };
  }
  return { unit: 'V', series: [{ key: id, label: `V(${id})`, values: component?.voltageV ?? [] }] };
}

/** Índices a desenhar: todos, ou no máximo `max` equidistantes (incluindo o primeiro e o último). */
export function sampleIndices(length: number, max = MAX_CHART_POINTS): number[] {
  if (length <= max) return Array.from({ length }, (_, i) => i);
  const stride = Math.ceil((length - 1) / (max - 1));
  const indices: number[] = [];
  for (let i = 0; i < length - 1; i += stride) indices.push(i);
  indices.push(length - 1);
  return indices;
}

/** Linhas para o Recharts: `{ t, [série]: valor }`. */
export function chartRows(timeS: readonly number[], plot: Plot): Record<string, number>[] {
  return sampleIndices(timeS.length).map((i) => {
    const row: Record<string, number> = { t: timeS[i] };
    for (const { key, values } of plot.series) row[key] = values[i];
    return row;
  });
}

/** Valores no último instante, no formato do resultado DC (para as tabelas). */
export function finalValues(result: TransientResult): {
  nodeVoltagesV: Record<string, number>;
  components: Record<string, ComponentValues>;
} {
  const last = <T>(values: readonly T[]) => values[values.length - 1];
  return {
    nodeVoltagesV: Object.fromEntries(
      Object.entries(result.nodeVoltagesV).map(([id, values]) => [id, last(values)]),
    ),
    components: Object.fromEntries(
      Object.entries(result.components).map(([id, s]) => [
        id,
        { voltageV: last(s.voltageV), currentA: last(s.currentA), powerW: last(s.powerW) },
      ]),
    ),
  };
}
