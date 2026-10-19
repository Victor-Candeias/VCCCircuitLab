import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import paraleloJson from '@vcccircuitlab/circuit-schema/examples/paralelo-juncao.json';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { EditorCanvas } from '../editor/EditorCanvas';
import { useEditorStore } from '../store/editorStore';
import { useSimulationStore } from './simulationStore';

const paralelo = paraleloJson as unknown as CircuitDocument;
const initialEditor = useEditorStore.getState();
const initialSimulation = useSimulationStore.getState();
const fetchMock = vi.fn<typeof fetch>();

// Resposta real da API para o exemplo paralelo-juncao.
const paraleloResult = {
  analysis: 'dc_operating_point',
  status: 'success',
  nodeVoltagesV: { N1: 9.0, N2: 0.0, N3: 9.0 },
  components: {
    V1: { voltageV: 9.0, currentA: -0.06814055838261587, powerW: -0.6132650254435429 },
    S1: { voltageV: 0.0, currentA: 0.06814055838261587, powerW: 0.0 },
    R1: { voltageV: 9.0, currentA: 0.04090909090909091, powerW: 0.36818181818181817 },
    R2: { voltageV: 9.0, currentA: 0.027231467473524965, powerW: 0.24508320726172467 },
  },
  warnings: [{ code: 'NO_CURRENT', message: 'Aviso de teste em R2.', refs: ['R2'] }],
};

const json = (body: unknown, status = 200, type = 'application/json') =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': type } });

beforeEach(() => {
  useEditorStore.setState(initialEditor, true);
  useSimulationStore.setState(initialSimulation, true);
  useEditorStore.getState().loadCircuit(paralelo);
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

const renderEditor = () =>
  render(
    <div style={{ width: 1200, height: 600 }}>
      <EditorCanvas />
    </div>,
  );

const simulate = () => fireEvent.click(screen.getByRole('button', { name: 'Simular' }));

// O primeiro teste carrega o React Flow inteiro; em máquinas carregadas passa dos 5 s.
describe('SimulationPanel', { timeout: 15_000 }, () => {
  test('Simular mostra tensão, corrente e potência por componente e a tensão das redes', async () => {
    fetchMock.mockResolvedValue(json(paraleloResult));
    renderEditor();
    expect(screen.getByText(/Simule o circuito/)).toBeInTheDocument();

    simulate();
    expect(screen.getByRole('button', { name: 'A simular…' })).toBeDisabled();
    const table = await screen.findByRole('table', { name: 'Resultados por componente' });
    const row = (id: string) =>
      within(table)
        .getByRole('button', { name: id })
        .closest('tr')!
        .textContent?.replace(/\s+/g, ' ');
    expect(row('R1')).toBe('R19 V40,9 mA368 mW');
    expect(row('V1')).toBe('V19 V-68,1 mA-613 mW');
    expect(row('S1')).toBe('S10 V68,1 mA0 W');
    expect(within(table).queryByRole('button', { name: 'GND1' })).toBeNull();

    const nets = screen.getByRole('table', { name: 'Tensão das redes' });
    expect(within(nets).getAllByRole('row')).toHaveLength(4);
    expect(within(nets).getByRole('button', { name: 'N3' }).closest('tr')).toHaveTextContent(
      'N39 VS1.b, R1.a, R2.a',
    );
    expect(screen.getByRole('status')).toHaveTextContent('Aviso de teste em R2.');

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.id).toBe('paralelo-juncao');
  });

  test('clicar numa rede destaca os seus fios, junções e terminais no canvas', async () => {
    fetchMock.mockResolvedValue(json(paraleloResult));
    const { container } = renderEditor();
    simulate();
    const nets = await screen.findByRole('table', { name: 'Tensão das redes' });
    const n3 = within(nets).getByRole('button', { name: 'N3' });

    fireEvent.click(n3);
    expect(n3).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() =>
      expect(
        [...container.querySelectorAll('.react-flow__edge.is-net-highlighted')].map((e) =>
          e.getAttribute('data-id'),
        ),
      ).toEqual(['W2', 'W3', 'W4']),
    );
    expect(container.querySelector('.react-flow__node[data-id="J1"]')).toHaveClass(
      'is-net-highlighted',
    );
    expect(screen.getByRole('button', { name: 'Terminal R1.a' })).toHaveClass('is-net-highlighted');
    expect(screen.getByRole('button', { name: 'Terminal R1.b' })).not.toHaveClass(
      'is-net-highlighted',
    );

    fireEvent.click(n3);
    expect(n3).toHaveAttribute('aria-pressed', 'false');
    await waitFor(() =>
      expect(container.querySelector('.react-flow__edge.is-net-highlighted')).toBeNull(),
    );
  });

  test('clicar num componente da tabela seleciona-o no canvas', async () => {
    fetchMock.mockResolvedValue(json(paraleloResult));
    renderEditor();
    simulate();
    const table = await screen.findByRole('table', { name: 'Resultados por componente' });
    fireEvent.click(within(table).getByRole('button', { name: 'R2' }));
    expect(useEditorStore.getState().selectedIds).toEqual(['R2']);
    expect(within(table).getByRole('button', { name: 'R2' }).closest('tr')).toHaveClass(
      'is-selected',
    );
  });

  test('alterar o circuito invalida os resultados; desfazer volta a mostrá-los', async () => {
    fetchMock.mockResolvedValue(json(paraleloResult));
    const { container } = renderEditor();
    simulate();
    const nets = await screen.findByRole('table', { name: 'Tensão das redes' });
    fireEvent.click(within(nets).getByRole('button', { name: 'N3' }));

    useEditorStore.getState().moveComponent('R2', { x: 500, y: 200 });
    expect(await screen.findByText(/O circuito foi alterado/)).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
    await waitFor(() =>
      expect(container.querySelector('.react-flow__edge.is-net-highlighted')).toBeNull(),
    );

    useEditorStore.getState().undo();
    expect(await screen.findByRole('table', { name: 'Tensão das redes' })).toBeInTheDocument();
  });

  test('erros problem+json aparecem com a lista de erros e Mostrar seleciona os elementos', async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          type: 'urn:vcccircuitlab:problem:invalid-circuit',
          title: 'Circuito inválido',
          status: 422,
          detail: 'A propriedade resistanceOhm de R1 (0 Ω) tem de ser > 0 Ω.',
          code: 'INVALID_VALUE',
          errors: [
            {
              code: 'INVALID_VALUE',
              message: 'A propriedade resistanceOhm de R1 (0 Ω) tem de ser > 0 Ω.',
              refs: ['R1'],
            },
            {
              code: 'FLOATING_NET',
              message: 'Sem caminho condutor até à terra.',
              refs: ['N3', 'S1.b', 'R2.a'],
            },
          ],
        },
        422,
        'application/problem+json',
      ),
    );
    renderEditor();
    simulate();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Circuito inválido');
    expect(alert).toHaveTextContent('tem de ser > 0 Ω. INVALID_VALUE');
    expect(alert).toHaveTextContent('Sem caminho condutor até à terra. FLOATING_NET');

    fireEvent.click(within(alert).getAllByRole('button', { name: 'Mostrar' })[1]);
    expect(useEditorStore.getState().selectedIds).toEqual(['S1', 'R2']);
    expect(useSimulationStore.getState().highlightedNet).toBe('N3');
  });

  test('falha de rede mostra a mensagem do cliente', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    renderEditor();
    simulate();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível simular');
    expect(alert).toHaveTextContent('Não foi possível contactar a API');
  });

  test('análise transitória: envia duração e passo, mostra o gráfico e os valores finais', async () => {
    fetchMock.mockResolvedValue(
      json({
        analysis: 'transient',
        status: 'success',
        timeS: [0, 0.001, 0.002],
        nodeVoltagesV: { N1: [9, 9, 9], N2: [0, 0, 0], N3: [9, 9, 9] },
        components: Object.fromEntries(
          Object.entries(paraleloResult.components).map(([id, v]) => [
            id,
            {
              voltageV: [0, v.voltageV, v.voltageV],
              currentA: [0, 0, v.currentA],
              powerW: [0, 0, v.powerW],
            },
          ]),
        ),
        warnings: [],
      }),
    );
    renderEditor();
    fireEvent.change(screen.getByLabelText('Análise'), { target: { value: 'transient' } });
    expect(screen.getByText(/evolução no tempo/)).toBeInTheDocument();
    const duration = screen.getByLabelText('Duração (ms)');
    expect(duration).toHaveValue(10);
    expect(screen.getByLabelText('Passo (µs)')).toHaveValue(10);

    fireEvent.change(duration, { target: { value: '' } });
    expect(duration).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('button', { name: 'Simular' })).toBeDisabled();
    fireEvent.change(duration, { target: { value: '2' } });
    simulate();

    expect(await screen.findByText('Valores finais (t = 2 ms)')).toBeInTheDocument();
    expect(screen.getByRole('figure', { name: 'Gráfico da análise transitória' })).toBeVisible();
    const table = screen.getByRole('table', { name: 'Resultados por componente' });
    expect(within(table).getByRole('button', { name: 'R1' }).closest('tr')).toHaveTextContent(
      'R19 V40,9 mA368 mW',
    );
    const chart = screen.getByLabelText('Gráfico');
    expect(within(chart).getByRole('option', { name: 'Corrente em R2' })).toBeInTheDocument();
    fireEvent.change(chart, { target: { value: 'current:R2' } });
    expect(chart).toHaveValue('current:R2');

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/simulate\/transient$/);
    expect(JSON.parse(String(init?.body))).toMatchObject({ stopTimeS: 0.002, timeStepS: 1e-5 });
  });

  test('Simular fica desativado com o circuito vazio', () => {
    useEditorStore
      .getState()
      .loadCircuit({ ...paralelo, components: [], junctions: [], wires: [] });
    renderEditor();
    expect(screen.getByRole('button', { name: 'Simular' })).toBeDisabled();
  });
});
