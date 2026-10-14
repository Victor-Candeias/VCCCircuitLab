import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import type { CircuitIssue } from '../api/types';
import { getComponentDefinition } from '../editor/catalog';
import { parseTerminal } from '../editor/wiring';
import { useEditorStore } from '../store/editorStore';
import { formatQuantity } from './format';
import { circuitNets } from './nets';
import { isCurrent, useSimulationStore, type SimulationState } from './simulationStore';
import './simulation.css';

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
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const highlightedNet = useSimulationStore((s) => s.highlightedNet);

  if (simulation.status === 'idle') {
    return (
      <p className="results__hint" role="status">
        Simule o circuito para ver a tensão, a corrente e a potência de cada componente e a tensão
        de cada rede.
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
  const nets = circuitNets(circuit);
  const rows = circuit.components.filter((c) => result.components[c.id]);
  const select = (id: string) => useEditorStore.getState().setSelection([id]);
  const toggleNet = (id: string) =>
    useSimulationStore.getState().setHighlightedNet(highlightedNet === id ? null : id);

  return (
    <>
      {result.warnings.length > 0 && (
        <div className="results__warning" role="status">
          <strong>Avisos</strong>
          <IssueList issues={result.warnings} circuit={circuit} className="results__issues" />
        </div>
      )}

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
            const values = result.components[component.id];
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
                <td>{formatQuantity(values.voltageV, 'V')}</td>
                <td>{formatQuantity(values.currentA, 'A')}</td>
                <td>{formatQuantity(values.powerW, 'W')}</td>
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
            const voltage = result.nodeVoltagesV[net.id];
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

/** Painel de simulação: botão Simular, resultados por componente e por rede, avisos e erros. */
export function SimulationPanel() {
  const circuit = useEditorStore((s) => s.circuit);
  const simulation = useSimulationStore((s) => s.simulation);
  const running = simulation.status === 'running';
  const empty = circuit.components.length === 0;

  return (
    <aside className="results" aria-label="Simulação">
      <div className="results__header">
        <h2>Simulação DC</h2>
        <button
          type="button"
          className="results__run"
          disabled={running || empty}
          onClick={() => void useSimulationStore.getState().simulate(circuit)}
        >
          {running ? 'A simular…' : 'Simular'}
        </button>
      </div>
      <SimulationBody simulation={simulation} circuit={circuit} />
    </aside>
  );
}
