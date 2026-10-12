import { beforeEach, describe, expect, test } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from './editorStore';

const initialState = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initialState, true);
});

const componentPosition = (id: string) =>
  useEditorStore.getState().circuit.components.find((c) => c.id === id)?.position;

describe('editorStore', () => {
  test('começa com o circuito de demonstração e sem seleção', () => {
    const { circuit, selectedIds } = useEditorStore.getState();
    expect(circuit).toBe(demoCircuit);
    expect(selectedIds).toEqual([]);
  });

  test('moveComponent aplica snap à grelha na âncora', () => {
    useEditorStore.getState().moveComponent('R1', { x: 251, y: 129 });
    expect(componentPosition('R1')).toEqual({ x: 260, y: 120 });
  });

  test('moveComponent não altera o documento quando a posição encaixada é a mesma', () => {
    const before = useEditorStore.getState().circuit;
    useEditorStore.getState().moveComponent('R1', { x: 245, y: 115 });
    expect(useEditorStore.getState().circuit).toBe(before);
  });

  test('moveComponent é imutável e ignora IDs desconhecidos', () => {
    useEditorStore.getState().moveComponent('R1', { x: 300, y: 300 });
    expect(demoCircuit.components.find((c) => c.id === 'R1')?.position).toEqual({
      x: 240,
      y: 120,
    });
    const before = useEditorStore.getState().circuit;
    useEditorStore.getState().moveComponent('X9', { x: 0, y: 0 });
    expect(useEditorStore.getState().circuit).toBe(before);
  });

  test('seleção é estado de vista: não altera o circuito', () => {
    const before = useEditorStore.getState().circuit;
    useEditorStore.getState().setSelection(['R1', 'V1', 'R1', 'desconhecido']);
    expect(useEditorStore.getState().selectedIds).toEqual(['R1', 'V1']);
    expect(useEditorStore.getState().circuit).toBe(before);
  });

  test('mover não altera a seleção', () => {
    useEditorStore.getState().setSelection(['R1']);
    useEditorStore.getState().moveComponent('R1', { x: 400, y: 400 });
    expect(useEditorStore.getState().selectedIds).toEqual(['R1']);
  });

  test('loadCircuit substitui o documento e limpa a seleção', () => {
    useEditorStore.getState().setSelection(['R1']);
    const other = { ...demoCircuit, id: 'outro', components: [], wires: [] };
    useEditorStore.getState().loadCircuit(other);
    expect(useEditorStore.getState().circuit).toBe(other);
    expect(useEditorStore.getState().selectedIds).toEqual([]);
  });
});
