import { useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import type { TransientResult } from '../api/types';
import { formatQuantity } from './format';
import { chartRows, plotOf, type Quantity } from './transient';

const COLORS = ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#db2777'];

/** Gráfico (Recharts) da grandeza escolhida ao longo do tempo. */
export default function TransientChart({
  result,
  quantity,
  circuit,
}: {
  result: TransientResult;
  quantity: Quantity;
  circuit: CircuitDocument;
}) {
  const plot = useMemo(() => plotOf(result, quantity, circuit), [result, quantity, circuit]);
  const rows = useMemo(() => chartRows(result.timeS, plot), [result.timeS, plot]);
  const format = (value: unknown) => formatQuantity(Number(value), plot.unit);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="t"
          type="number"
          domain={['dataMin', 'dataMax']}
          tickFormatter={(t: number) => formatQuantity(t, 's')}
          tick={{ fontSize: 10 }}
        />
        <YAxis tickFormatter={format} tick={{ fontSize: 10 }} width={56} />
        <Tooltip
          formatter={format}
          labelFormatter={(t) => `t = ${formatQuantity(Number(t), 's')}`}
        />
        {plot.series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {plot.series.map((series, index) => (
          <Line
            key={series.key}
            dataKey={series.key}
            name={series.label}
            stroke={COLORS[index % COLORS.length]}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
