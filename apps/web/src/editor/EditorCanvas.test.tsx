import { createEvent, fireEvent, render, screen } from '@testing-library/react';
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
const clickNode = (id: string) => {
  const target = screen.getByText(id);
  for (const create of [createEvent.mouseDown, createEvent.mouseUp, createEvent.click]) {
    const event = create(target, { button: 0 });
    Object.defineProperty(event, 'view', { value: window });
    fireEvent(target, event);
  }
};

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
