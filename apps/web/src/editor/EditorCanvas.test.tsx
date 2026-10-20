import { createEvent, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { useEditorStore } from '../store/editorStore';
import { EditorCanvas } from './EditorCanvas';
import { PALETTE_DRAG_TYPE } from './palette';
import { CIRCUIT_EXAMPLES } from '../project/examples';

const initialState = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initialState, true);
});

const renderCanvas = () =>
  render(
    <div style={{ width: 800, height: 600 }}>
      <EditorCanvas />
    </div>,
  );

// O d3-drag (usado pelo React Flow) lê `event.view.document`; o user-event despacha eventos com `view: null`.
const click = (target: Element) => {
  for (const create of [createEvent.mouseDown, createEvent.mouseUp, createEvent.click]) {
    const event = create(target, { button: 0 });
    Object.defineProperty(event, 'view', { value: window });
    fireEvent(target, event);
  }
};

const clickNode = (id: string) => click(screen.getByText(id));

const pin = (ref: string) => screen.getByRole('button', { name: `Terminal ${ref}` });

describe('EditorCanvas', () => {
  test('desenha um nó por componente do circuito, com grelha e controlos de zoom', () => {
    const { container } = renderCanvas();
    for (const id of ['V1', 'R1', 'H1', 'GND1']) {
      expect(screen.getByText(id)).toBeInTheDocument();
    }
    expect(container.querySelector('.react-flow__background')).not.toBeNull();
    expect(screen.getByRole('button', { name: /zoom in/i })).toBeInTheDocument();
  });

  test('desenha o símbolo IEC de cada componente, com a rotação do documento', () => {
    renderCanvas();
    const symbolOf = (id: string) =>
      screen.getByText(id).closest('.component-node')?.querySelector('svg.component-symbol');

    expect(symbolOf('V1')).toHaveAttribute('data-symbol', 'dc_voltage_source_iec');
    expect(symbolOf('R1')).toHaveAttribute('data-symbol', 'resistor_iec');
    expect(symbolOf('GND1')).toHaveAttribute('data-symbol', 'ground_iec');

    const lamp = symbolOf('H1');
    expect(lamp).toHaveAttribute('data-symbol', 'lamp_iec');
    expect(lamp).toHaveAttribute('width', '40');
    expect(lamp).toHaveAttribute('height', '80');
    expect(lamp?.querySelector('g')).toHaveAttribute('transform', 'rotate(90)');
  });

  test('tipos fora do catálogo aparecem como marcador de erro, sem símbolo', () => {
    const [source] = initialState.circuit.components;
    useEditorStore.setState({
      circuit: {
        ...initialState.circuit,
        components: [{ ...source, id: 'X1', type: 'motor' }],
        wires: [],
      },
    });
    renderCanvas();
    const node = screen.getByText('X1').closest('.component-node');
    expect(node).toHaveClass('is-unknown');
    expect(node?.querySelector('svg.component-symbol')).toBeNull();
  });

  test('clique seleciona um componente; clique noutro substitui a seleção', () => {
    renderCanvas();

    clickNode('R1');
    expect(useEditorStore.getState().selectedIds).toEqual(['R1']);

    clickNode('V1');
    expect(useEditorStore.getState().selectedIds).toEqual(['V1']);
  });

  test('Ctrl + clique acrescenta à seleção (seleção múltipla)', () => {
    renderCanvas();

    clickNode('R1');
    fireEvent.keyDown(document, { key: 'Control', code: 'ControlLeft' });
    clickNode('V1');
    fireEvent.keyUp(document, { key: 'Control', code: 'ControlLeft' });

    expect([...useEditorStore.getState().selectedIds].sort()).toEqual(['R1', 'V1']);
  });

  test('reflete a seleção do store no nó', () => {
    useEditorStore.getState().setSelection(['H1']);
    renderCanvas();
    expect(screen.getByText('H1').closest('.component-node')).toHaveClass('is-selected');
    expect(screen.getByText('R1').closest('.component-node')).not.toHaveClass('is-selected');
  });
});

describe('EditorCanvas — ligações', () => {
  test('desenha um fio por ligação do documento e um terminal clicável por pino', async () => {
    const { container } = renderCanvas();
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(4));
    expect(container.querySelector('path.wire-edge')).toHaveAttribute(
      'd',
      'M 100 160 L 100 120 L 200 120',
    );
    expect(pin('V1.positive')).toBeInTheDocument();
    expect(pin('GND1.gnd')).toBeInTheDocument();
  });

  test('clique num terminal e noutro cria um fio, sem alterar a seleção', async () => {
    const { container } = renderCanvas();

    click(pin('GND1.gnd'));
    expect(useEditorStore.getState().wireDraft?.start).toEqual({
      kind: 'terminal',
      ref: 'GND1.gnd',
    });
    expect(container.querySelector('.react-flow')).toHaveClass('is-wiring');

    click(pin('R1.b'));
    expect(useEditorStore.getState().wireDraft).toBeNull();
    expect(useEditorStore.getState().circuit.wires.at(-1)).toMatchObject({
      from: 'GND1.gnd',
      to: 'R1.b',
    });
    expect(useEditorStore.getState().selectedIds).toEqual([]);
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(5));
  });

  test('Enter num terminal (navegação por teclado) inicia e termina um fio', async () => {
    const { container } = renderCanvas();

    fireEvent.keyDown(pin('GND1.gnd'), { key: 'Enter' });
    expect(useEditorStore.getState().wireDraft?.start).toEqual({
      kind: 'terminal',
      ref: 'GND1.gnd',
    });

    fireEvent.keyDown(pin('R1.b'), { key: ' ' });
    expect(useEditorStore.getState().wireDraft).toBeNull();
    expect(useEditorStore.getState().circuit.wires.at(-1)).toMatchObject({
      from: 'GND1.gnd',
      to: 'R1.b',
    });
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(5));
  });

  test('Esc cancela o fio em desenho', () => {
    renderCanvas();
    click(pin('GND1.gnd'));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(useEditorStore.getState().wireDraft).toBeNull();
    expect(useEditorStore.getState().circuit.wires).toHaveLength(4);
  });

  test('junções são desenhadas e podem começar ou terminar um fio', async () => {
    useEditorStore.getState().startWire({ kind: 'terminal', ref: 'GND1.gnd' });
    useEditorStore.getState().finishWire({ kind: 'wire', wireId: 'W2', point: { x: 320, y: 120 } });
    const { container } = renderCanvas();

    const junction = screen.getByLabelText('Junção J1');
    expect(junction).toHaveClass('junction-node');
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(6));

    click(pin('R1.a'));
    click(junction);
    expect(useEditorStore.getState().circuit.wires.at(-1)).toMatchObject({
      from: 'R1.a',
      to: 'J1',
    });
  });
});

describe('EditorCanvas — circuito ramificado (§5.2)', () => {
  test('desenha todos os ramos, junções e fios e permite editá-los', async () => {
    useEditorStore
      .getState()
      .loadCircuit(CIRCUIT_EXAMPLES.find((e) => e.id === 'ramificado')!.circuit);
    const { container } = renderCanvas();

    for (const id of ['V1', 'S1', 'R1', 'R2', 'H1', 'R3', 'R4', 'GND1']) {
      expect(screen.getByText(id)).toBeInTheDocument();
    }
    expect(container.querySelectorAll('.junction-node')).toHaveLength(5);
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(16));

    // Ligar R4.b à junção J1 (fio novo num nó com quatro fios).
    click(pin('R4.b'));
    click(screen.getByLabelText('Junção J1'));
    expect(useEditorStore.getState().circuit.wires.at(-1)).toMatchObject({
      id: 'W17',
      from: 'R4.b',
      to: 'J1',
    });
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(17));
  });
});

describe('EditorCanvas — paleta e rotação', () => {
  const component = (id: string) =>
    useEditorStore.getState().circuit.components.find((c) => c.id === id);
  const paletteItem = (label: string) => screen.getByRole('button', { name: `Adicionar ${label}` });

  test('a paleta agrupa o catálogo por categoria, com o símbolo de cada componente', () => {
    renderCanvas();
    const palette = screen.getByRole('complementary', { name: 'Componentes' });
    const groups = [
      'Fontes',
      'Passivos',
      'Interruptores',
      'Proteção',
      'Cargas',
      'Instrumentos',
      'Semicondutores',
      'Referência',
    ];
    for (const group of groups) {
      expect(screen.getByRole('region', { name: group })).toBeInTheDocument();
    }
    expect(palette.querySelectorAll('.palette-item')).toHaveLength(21);
    expect(paletteItem('Resistência').querySelector('svg')).toHaveAttribute(
      'data-symbol',
      'resistor_iec',
    );
  });

  test('a pesquisa filtra a paleta', () => {
    renderCanvas();
    const search = screen.getByRole('searchbox', { name: 'Pesquisar componentes' });
    fireEvent.change(search, { target: { value: 'lampada' } });
    expect(paletteItem('Lâmpada')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Adicionar Resistência' })).toBeNull();
    fireEvent.change(search, { target: { value: 'xyz' } });
    expect(screen.getByText('Nenhum componente encontrado.')).toBeInTheDocument();
  });

  test('arrastar da paleta define o tipo no dataTransfer', () => {
    renderCanvas();
    const setData = vi.fn();
    fireEvent.dragStart(paletteItem('Interruptor'), {
      dataTransfer: { setData, effectAllowed: 'all' },
    });
    expect(setData).toHaveBeenCalledWith(PALETTE_DRAG_TYPE, 'switch');
  });

  test('largar no canvas cria o componente com snap à grelha e seleciona-o', async () => {
    const { container } = renderCanvas();
    const flow = container.querySelector('.react-flow')!;
    const dataTransfer = {
      types: [PALETTE_DRAG_TYPE],
      getData: (type: string) => (type === PALETTE_DRAG_TYPE ? 'lamp' : ''),
      dropEffect: 'none',
    };

    const dragOver = createEvent.dragOver(flow, { dataTransfer });
    fireEvent(flow, dragOver);
    expect(dragOver.defaultPrevented).toBe(true);

    // O jsdom não tem DragEvent: as coordenadas são definidas à mão.
    const drop = createEvent.drop(flow, { dataTransfer });
    Object.defineProperties(drop, { clientX: { value: 333 }, clientY: { value: 227 } });
    fireEvent(flow, drop);
    const lamp = component('H2');
    expect(lamp).toMatchObject({ type: 'lamp', rotation: 0 });
    expect(Math.abs(lamp!.position.x % 20)).toBe(0);
    expect(Math.abs(lamp!.position.y % 20)).toBe(0);
    expect(useEditorStore.getState().selectedIds).toEqual(['H2']);
    expect(await screen.findByText('H2')).toBeInTheDocument();
  });

  test('largar algo que não vem da paleta é ignorado', () => {
    const { container } = renderCanvas();
    const flow = container.querySelector('.react-flow')!;
    const dataTransfer = { types: ['text/plain'], getData: () => 'motor', dropEffect: 'none' };
    const dragOver = createEvent.dragOver(flow, { dataTransfer });
    fireEvent(flow, dragOver);
    expect(dragOver.defaultPrevented).toBe(false);
    fireEvent.drop(flow, { dataTransfer });
    expect(useEditorStore.getState().circuit).toBe(initialState.circuit);
  });

  test('clique ou Enter num item da paleta adiciona o componente', () => {
    renderCanvas();
    click(paletteItem('Resistência'));
    expect(component('R2')?.type).toBe('resistor');
    fireEvent.keyDown(paletteItem('Terra'), { key: 'Enter' });
    expect(component('GND2')?.type).toBe('ground');
    expect(useEditorStore.getState().selectedIds).toEqual(['GND2']);
  });

  test('R roda a seleção 90° (horário) e Shift+R no sentido anti-horário', () => {
    renderCanvas();
    clickNode('R1');
    fireEvent.keyDown(window, { key: 'r' });
    expect(component('R1')?.rotation).toBe(90);
    fireEvent.keyDown(window, { key: 'R', shiftKey: true });
    fireEvent.keyDown(window, { key: 'R', shiftKey: true });
    expect(component('R1')?.rotation).toBe(270);
    fireEvent.keyDown(window, { key: 'r', ctrlKey: true });
    expect(component('R1')?.rotation).toBe(270);
  });

  test('R ao escrever na pesquisa não roda a seleção', () => {
    renderCanvas();
    clickNode('R1');
    fireEvent.keyDown(screen.getByRole('searchbox', { name: 'Pesquisar componentes' }), {
      key: 'r',
    });
    expect(component('R1')?.rotation).toBe(0);
  });

  test('os botões de rotação só ficam ativos com componentes selecionados', () => {
    renderCanvas();
    const clockwise = screen.getByRole('button', { name: 'Rodar 90° no sentido horário' });
    const counter = screen.getByRole('button', { name: 'Rodar 90° no sentido anti-horário' });
    expect(clockwise).toBeDisabled();

    clickNode('H1');
    expect(clockwise).toBeEnabled();
    fireEvent.click(clockwise);
    expect(component('H1')?.rotation).toBe(180);
    fireEvent.click(counter);
    fireEvent.click(counter);
    expect(component('H1')?.rotation).toBe(0);
  });
});

describe('EditorCanvas — editar (desfazer, copiar/colar, apagar)', { timeout: 15_000 }, () => {
  const store = () => useEditorStore.getState();
  const has = (id: string) => store().circuit.components.some((c) => c.id === id);
  const button = (name: string) => screen.getByRole('button', { name });

  test('Delete apaga a seleção e os fios ligados; Ctrl+Z desfaz e Ctrl+Y refaz', () => {
    renderCanvas();
    clickNode('R1');
    fireEvent.keyDown(window, { key: 'Delete' });
    expect(has('R1')).toBe(false);
    expect(store().circuit.wires.map((w) => w.id)).toEqual(['W3', 'W4']);

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
    expect(has('R1')).toBe(true);
    fireEvent.keyDown(window, { key: 'y', ctrlKey: true });
    expect(has('R1')).toBe(false);
    fireEvent.keyDown(window, { key: 'Z', ctrlKey: true, shiftKey: true });
    expect(has('R1')).toBe(false);
    fireEvent.keyDown(window, { key: 'z', metaKey: true });
    expect(has('R1')).toBe(true);
  });

  test('Backspace durante o desenho de um fio ou a escrever não apaga', () => {
    renderCanvas();
    clickNode('R1');
    fireEvent.keyDown(screen.getByRole('searchbox', { name: 'Pesquisar componentes' }), {
      key: 'Backspace',
    });
    expect(has('R1')).toBe(true);
    click(pin('GND1.gnd'));
    fireEvent.keyDown(window, { key: 'Backspace' });
    expect(has('R1')).toBe(true);
  });

  test('Ctrl+C / Ctrl+V duplica a seleção com novos IDs e seleciona a cópia', async () => {
    renderCanvas();
    clickNode('R1');
    fireEvent.keyDown(window, { key: 'c', ctrlKey: true });
    fireEvent.keyDown(window, { key: 'v', ctrlKey: true });
    expect(store().selectedIds).toEqual(['R2']);
    expect(await screen.findByText('R2')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'x', ctrlKey: true });
    expect(has('R2')).toBe(false);
  });

  test('Alt + clique num fio seleciona-o e Delete apaga-o', async () => {
    const { container } = renderCanvas();
    await waitFor(() => expect(container.querySelectorAll('path.wire-edge')).toHaveLength(4));
    const wire = container.querySelectorAll('path.wire-edge')[1];
    fireEvent.click(wire, { altKey: true });
    expect(store().selectedIds).toEqual(['W2']);
    await waitFor(() =>
      expect(container.querySelectorAll('path.wire-edge')[1]).toHaveClass('is-selected'),
    );

    fireEvent.click(container.querySelector('.react-flow__pane')!);
    expect(store().selectedIds).toEqual([]);
    fireEvent.click(container.querySelectorAll('path.wire-edge')[1], { altKey: true });
    fireEvent.keyDown(window, { key: 'Delete' });
    expect(store().circuit.wires.map((w) => w.id)).toEqual(['W1', 'W3', 'W4']);
    expect(has('R1')).toBe(true);
  });

  test('os botões da barra refletem o que é possível fazer', () => {
    renderCanvas();
    for (const name of ['Desfazer', 'Refazer', 'Copiar', 'Colar', 'Apagar seleção']) {
      expect(button(name)).toBeDisabled();
    }
    clickNode('H1');
    expect(button('Copiar')).toBeEnabled();
    expect(button('Apagar seleção')).toBeEnabled();
    fireEvent.click(button('Copiar'));
    fireEvent.click(button('Colar'));
    expect(has('H2')).toBe(true);
    fireEvent.click(button('Desfazer'));
    expect(has('H2')).toBe(false);
    expect(button('Refazer')).toBeEnabled();
    fireEvent.click(button('Refazer'));
    expect(button('Apagar seleção')).toBeDisabled();
    clickNode('H2');
    fireEvent.click(button('Apagar seleção'));
    expect(has('H2')).toBe(false);
    expect(has('H1')).toBe(true);
  });
});
