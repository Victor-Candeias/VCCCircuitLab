import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from '../store/editorStore';
import { serializeCircuit } from './circuitJson';
import { ProjectMenu } from './ProjectMenu';

const initialState = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initialState, true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

const chooseFile = (content: string, name = 'circuito.json') => {
  const input = screen.getByLabelText('Ficheiro de circuito (JSON)');
  fireEvent.change(input, { target: { files: [new File([content], name)] } });
};

describe('ProjectMenu', () => {
  test('Guardar JSON descarrega o documento canónico com o nome do circuito', async () => {
    let saved: Blob | undefined;
    const createObjectURL = vi.fn((blob: Blob) => {
      saved = blob;
      return 'blob:circuito';
    });
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<ProjectMenu />);
    fireEvent.click(screen.getByRole('button', { name: 'Guardar JSON' }));

    expect(clickSpy).toHaveBeenCalledOnce();
    const link = clickSpy.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toMatch(/\.json$/);
    expect(await saved?.text()).toBe(serializeCircuit(demoCircuit));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:circuito');
  });

  test('Abrir carrega um ficheiro válido e mostra o nome do circuito', async () => {
    render(<ProjectMenu />);
    const other = { ...demoCircuit, id: 'outro', name: 'Outro circuito' };
    chooseFile(serializeCircuit(other));

    await waitFor(() => expect(useEditorStore.getState().circuit.id).toBe('outro'));
    expect(screen.getByText('Outro circuito')).toBeInTheDocument();
    expect(useEditorStore.getState().loadId).toBe(1);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  test('um ficheiro inválido mostra os erros e não altera o circuito atual', async () => {
    render(<ProjectMenu />);
    chooseFile('{"schemaVersion": "1.0"}', 'mau.json');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível abrir "mau.json"');
    expect(alert).toHaveTextContent('falta a propriedade obrigatória "components"');
    expect(useEditorStore.getState().circuit).toBe(demoCircuit);

    fireEvent.click(screen.getByRole('button', { name: 'Fechar mensagem' }));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  test('Exemplos abre um circuito de exemplo (com confirmação) e repõe o seletor', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ProjectMenu />);
    const select = screen.getByRole('combobox', { name: 'Abrir exemplo' });

    fireEvent.change(select, { target: { value: 'ramificado' } });

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Ramificado'));
    expect(useEditorStore.getState().circuit.id).toBe('ramificado');
    expect(useEditorStore.getState().circuit.junctions).toHaveLength(5);
    expect(select).toHaveValue('');
  });

  test('Novo pede confirmação e começa um circuito vazio', () => {
    const confirm = vi
      .spyOn(window, 'confirm')
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    render(<ProjectMenu />);

    fireEvent.click(screen.getByRole('button', { name: 'Novo' }));
    expect(useEditorStore.getState().circuit).toBe(demoCircuit);

    fireEvent.click(screen.getByRole('button', { name: 'Novo' }));
    expect(confirm).toHaveBeenCalledTimes(2);
    const { circuit } = useEditorStore.getState();
    expect(circuit.components).toEqual([]);
    expect(circuit.wires).toEqual([]);
    expect(screen.getByText('Novo circuito')).toBeInTheDocument();
  });
});
