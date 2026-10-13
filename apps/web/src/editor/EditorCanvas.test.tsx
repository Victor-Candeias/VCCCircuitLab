import { createEvent, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test } from 'vitest';
import { useEditorStore } from '../store/editorStore';
import { EditorCanvas } from './EditorCanvas';

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
