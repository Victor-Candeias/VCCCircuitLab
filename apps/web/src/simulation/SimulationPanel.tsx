import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import { lazy, Suspense, useState } from 'react';
import type { CircuitIssue, ComponentValues, TransientResult } from '../api/types';
import { getComponentDefinition } from '../editor/catalog';
import { parseTerminal } from '../editor/wiring';
import { useEditorStore } from '../store/editorStore';
import { formatQuantity } from './format';
import { circuitNets } from './nets';
import {
  isCurrent,
  isValidTransient,
  useSimulationStore,
  type AnalysisKind,
  type SimulationState,
} from './simulationStore';
import { finalValues, type Quantity } from './transient';
import './simulation.css';

// O Recharts só é descarregado quando há um resultado transitório para desenhar.
const TransientChart = lazy(() => import('./TransientChart'));

/** Seleciona no canvas os elementos citados num erro e destaca a primeira rede citada. */
function showRefs(circuit: CircuitDocument, refs: readonly string[]) {
  const netIds = new Set(circuitNets(circuit).map((n) => n.id));
  useEditorStore.getState().setSelection(refs.map((ref) => parseTerminal(ref)?.componentId ?? ref));
  useSimulationStore.getState().setHighlightedNet(refs.find((ref) => netIds.has(ref)) ?? null);
}

function IssueList({
  issues,
  circuit,
  className,
}: {
  issues: readonly CircuitIssue[];
  circuit: CircuitDocument;
  className: string;
}) {
  return (
    <ul className={className}>
      {issues.map((issue, index) => (
        <li key={`${issue.code}-${index}`}>
          <span>{issue.message}</span> <code className="results__code">{issue.code}</code>
          {issue.refs.length > 0 && (
            <button
              type="button"
              className="results__link"
              onClick={() => showRefs(circuit, issue.refs)}
            >
              Mostrar
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function SimulationBody({
  simulation,
  circuit,
}: {
  simulation: SimulationState;
  circuit: CircuitDocument;
}) {
  const analysis = useSimulationStore((s) => s.analysis);

  if (simulation.status === 'idle') {
    return (
      <p className="results__hint" role="status">
        {analysis === 'transient'
          ? 'Simule o circuito para ver a evolução no tempo das tensões e correntes: as fontes ' +
            'ligam-se em t = 0 e os condensadores e bobinas partem das condições iniciais.'
          : 'Simule o circuito para ver a tensão, a corrente e a potência de cada componente e a ' +
            'tensão de cada rede.'}
      </p>
    );
  }
  if (!isCurrent(simulation, circuit)) {
    return (
      <p className="results__hint" role="status">
        O circuito foi alterado depois da última simulação. Simule de novo para ver os resultados.
      </p>
    );
  }
  if (simulation.status === 'running') {
    return (
      <p className="results__hint" role="status">
        A simular…
      </p>
    );
  }
  if (simulation.status === 'error') {
    const { error } = simulation;
    const problem = error.problem;
    return (
      <div className="results__error" role="alert">
        <strong>{problem?.title ?? 'Não foi possível simular'}</strong>
        {problem && problem.errors.length > 0 ? (
          <IssueList issues={problem.errors} circuit={circuit} className="results__issues" />
        ) : (
          <p>{error.message}</p>
        )}
      </div>
    );
  }

  const { result } = simulation;
  return (
    <>
      {result.warnings.length > 0 && (
        <div className="results__warning" role="status">
          <strong>Avisos</strong>
          <IssueList issues={result.warnings} circuit={circuit} className="results__issues" />
        </div>
      )}
      {result.analysis === 'transient' ? (
        <TransientView result={result} circuit={circuit} />
      ) : (
        <ResultTables values={result} circuit={circuit} />
      )}
    </>
  );
}

function TransientView({ result, circuit }: { result: TransientResult; circuit: CircuitDocument }) {
  const [quantity, setQuantity] = useState<Quantity>('nets');
  const components = circuit.components.filter((c) => result.components[c.id]);
  const end = result.timeS[result.timeS.length - 1] ?? 0;

  return (
    <>
      <label className="results__field">
        Gráfico
        <select value={quantity} onChange={(event) => setQuantity(event.target.value as Quantity)}>
          <option value="nets">Tensões das redes</option>
          {components.map((c) => (
            <option key={`v-${c.id}`} value={`voltage:${c.id}`}>
              Tensão em {c.id}
            </option>
          ))}
          {components.map((c) => (
            <option key={`i-${c.id}`} value={`current:${c.id}`}>
              Corrente em {c.id}
            </option>
          ))}
        </select>
      </label>
      <figure className="results__chart" aria-label="Gráfico da análise transitória">
        <Suspense fallback={<p className="results__hint">A carregar o gráfico…</p>}>
          <TransientChart result={result} quantity={quantity} />
        </Suspense>
      </figure>
      <h3 className="results__subtitle">Valores finais (t = {formatQuantity(end, 's')})</h3>
      <ResultTables values={finalValues(result)} circuit={circuit} />
    </>
  );
}

/** Tabelas por componente e por rede (resultado DC ou valores finais da transitória). */
function ResultTables({
  values,
  circuit,
}: {
  values: { nodeVoltagesV: Record<string, number>; components: Record<string, ComponentValues> };
  circuit: CircuitDocument;
}) {
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const highlightedNet = useSimulationStore((s) => s.highlightedNet);
  const nets = circuitNets(circuit);
  const rows = circuit.components.filter((c) => values.components[c.id]);
  const select = (id: string) => useEditorStore.getState().setSelection([id]);
  const toggleNet = (id: string) =>
    useSimulationStore.getState().setHighlightedNet(highlightedNet === id ? null : id);

  return (
    <>
      <table className="results__table" aria-label="Resultados por componente">
        <thead>
          <tr>
            <th scope="col">Comp.</th>
            <th scope="col">Tensão</th>
            <th scope="col">Corrente</th>
            <th scope="col">Potência</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((component) => {
            const row = values.components[component.id];
            const label = getComponentDefinition(component.type)?.label ?? component.type;
            return (
              <tr
                key={component.id}
                className={selectedIds.includes(component.id) ? 'is-selected' : undefined}
              >
                <th scope="row">
                  <button
                    type="button"
                    className="results__ref"
                    title={`Selecionar ${component.id} (${label})`}
                    onClick={() => select(component.id)}
                  >
                    {component.id}
                  </button>
                </th>
                <td>{formatQuantity(row.voltageV, 'V')}</td>
                <td>{formatQuantity(row.currentA, 'A')}</td>
                <td>{formatQuantity(row.powerW, 'W')}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="results__note">
        Tensão e corrente do 1.º para o 2.º pino; potência negativa = o componente fornece energia.
      </p>

      <table className="results__table" aria-label="Tensão das redes">
        <thead>
          <tr>
            <th scope="col">Rede</th>
            <th scope="col">Tensão</th>
            <th scope="col" className="results__terminals">
              Terminais
            </th>
          </tr>
        </thead>
        <tbody>
          {nets.map((net) => {
            const voltage = values.nodeVoltagesV[net.id];
            const highlighted = highlightedNet === net.id;
            return (
              <tr key={net.id} className={highlighted ? 'is-highlighted' : undefined}>
                <th scope="row">
                  <button
                    type="button"
                    className="results__ref"
                    aria-pressed={highlighted}
                    title={`Destacar a rede ${net.id} no circuito`}
                    onClick={() => toggleNet(net.id)}
                  >
                    {net.id}
                  </button>
                </th>
                <td>{voltage === undefined ? '—' : formatQuantity(voltage, 'V')}</td>
                <td className="results__terminals">{net.terminals.join(', ')}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

/** Campo numérico em `unit` (ms, µs…) para um valor guardado em segundos (`NaN` se inválido). */
function SecondsField({
  label,
  unit,
  factor,
  value,
  onChange,
}: {
  label: string;
  unit: string;
  factor: number;
  value: number;
  onChange: (seconds: number) => void;
}) {
  const [text, setText] = useState(() => String(Number((value / factor).toPrecision(12))));
  const invalid = !(Number.isFinite(value) && value > 0);
  return (
    <label className="results__field">
      {label} ({unit})
      <input
        type="number"
        min={0}
        step="any"
        value={text}
        aria-invalid={invalid || undefined}
        onChange={(event) => {
          setText(event.target.value);
          const parsed = event.target.value.trim() === '' ? Number.NaN : Number(event.target.value);
          onChange(Number((parsed * factor).toPrecision(12)));
        }}
      />
    </label>
  );
}

function AnalysisControls() {
  const analysis = useSimulationStore((s) => s.analysis);
  const transient = useSimulationStore((s) => s.transient);
  const { setAnalysis, setTransient } = useSimulationStore.getState();

  return (
    <div className="results__analysis">
      <label className="results__field">
        Análise
        <select
          value={analysis}
          onChange={(event) => setAnalysis(event.target.value as AnalysisKind)}
        >
          <option value="dc">Ponto de funcionamento (DC)</option>
          <option value="transient">Transitória (no tempo)</option>
        </select>
      </label>
      {analysis === 'transient' && (
        <>
          <SecondsField
            label="Duração"
            unit="ms"
            factor={1e-3}
            value={transient.stopTimeS}
            onChange={(stopTimeS) => setTransient({ stopTimeS })}
          />
          <SecondsField
            label="Passo"
            unit="µs"
            factor={1e-6}
            value={transient.timeStepS}
            onChange={(timeStepS) => setTransient({ timeStepS })}
          />
        </>
      )}
    </div>
  );
}

/** Painel de simulação: análise (DC ou transitória), botão Simular, resultados, avisos e erros. */
export function SimulationPanel() {
  const circuit = useEditorStore((s) => s.circuit);
  const simulation = useSimulationStore((s) => s.simulation);
  const invalidParameters = useSimulationStore(
    (s) => s.analysis === 'transient' && !isValidTransient(s.transient),
  );
  const running = simulation.status === 'running';
  const empty = circuit.components.length === 0;

  return (
    <aside className="results" aria-label="Simulação">
      <div className="results__header">
        <h2>Simulação</h2>
        <button
          type="button"
          className="results__run"
          disabled={running || empty || invalidParameters}
          onClick={() => void useSimulationStore.getState().simulate(circuit)}
        >
          {running ? 'A simular…' : 'Simular'}
        </button>
      </div>
      <AnalysisControls />
      <SimulationBody simulation={simulation} circuit={circuit} />
    </aside>
  );
}
