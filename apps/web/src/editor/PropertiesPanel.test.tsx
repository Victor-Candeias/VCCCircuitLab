import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { demoCircuit } from './demoCircuit';
import { PropertiesPanel } from './PropertiesPanel';
import { useEditorStore } from '../store/editorStore';

const initial = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initial, true);
  useEditorStore.getState().loadCircuit(demoCircuit);
});

afterEach(() => {
  useEditorStore.setState(initial, true);
});

describe('PropertiesPanel', () => {
  test('sem seleção, mostra uma sugestão', () => {
    render(<PropertiesPanel />);
    expect(screen.getByText(/selecione um componente/i)).toBeInTheDocument();
  });

  test('com seleção múltipla, pede para escolher um único componente', () => {
    useEditorStore.getState().setSelection(['R1', 'H1']);
    render(<PropertiesPanel />);
    expect(screen.getByText(/selecione um único componente/i)).toBeInTheDocument();
  });

  test('mostra os campos de propriedades do componente selecionado', () => {
    useEditorStore.getState().setSelection(['R1']);
    render(<PropertiesPanel />);
    expect(screen.getByLabelText(/Resistência/)).toHaveValue(100);
  });

  test('aplica uma alteração válida ao documento', async () => {
    useEditorStore.getState().setSelection(['R1']);
    render(<PropertiesPanel />);
    const input = screen.getByLabelText(/Resistência/);
    fireEvent.change(input, { target: { value: '220' } });
    await waitFor(() =>
      expect(
        useEditorStore.getState().circuit.components.find((c) => c.id === 'R1')?.properties,
      ).toEqual({ resistanceOhm: 220 }),
    );
  });

  test('assinala um valor fora dos limites e não altera o documento', async () => {
    useEditorStore.getState().setSelection(['R1']);
    render(<PropertiesPanel />);
    const input = screen.getByLabelText(/Resistência/);
    fireEvent.change(input, { target: { value: '-5' } });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/tem de ser/i));
    expect(useEditorStore.getState().circuit.components.find((c) => c.id === 'R1')?.properties).toEqual({
      resistanceOhm: 100,
    });
  });

  test('troca de seleção recomeça o formulário sem erros antigos', async () => {
    useEditorStore.getState().setSelection(['R1']);
    render(<PropertiesPanel />);
    const input = screen.getByLabelText(/Resistência/);
    fireEvent.change(input, { target: { value: '-5' } });
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());

    useEditorStore.getState().setSelection(['H1']);
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(screen.getByLabelText(/Tensão nominal/)).toHaveValue(12);
  });
});
