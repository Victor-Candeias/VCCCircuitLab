import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from '../store/editorStore';
import { emptyCircuit, serializeCircuit } from './circuitJson';
import { clearAutosave, saveAutosave } from './persistence';
import { ProjectMenu } from './ProjectMenu';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, exportSpice: vi.fn(), importSpice: vi.fn() };
});

import { ApiError, exportSpice, importSpice } from '../api/client';

const exportSpiceMock = vi.mocked(exportSpice);
const importSpiceMock = vi.mocked(importSpice);
const initialState = useEditorStore.getState();

beforeEach(async () => {
  useEditorStore.setState(initialState, true);
  await clearAutosave();
});

afterEach(async () => {
  vi.restoreAllMocks();
  exportSpiceMock.mockReset();
  importSpiceMock.mockReset();
  await clearAutosave();
});

const chooseFile = (content: string, name = 'circuito.json') => {
  const input = screen.getByLabelText('Ficheiro de circuito (JSON)');
  fireEvent.change(input, { target: { files: [new File([content], name)] } });
};

const chooseNetlist = (content: string, name = 'circuito.cir') => {
  const input = screen.getByLabelText('Netlist SPICE');
  fireEvent.change(input, { target: { files: [new File([content], name)] } });
};

describe('ProjectMenu', () => {
  test('Exportar SPICE descarrega a netlist da API como .cir', async () => {
    exportSpiceMock.mockResolvedValue('* Demo\nR1 n1 0 100.0\n.op\n.end\n');
    let saved: Blob | undefined;
    const createObjectURL = vi.fn((blob: Blob) => {
      saved = blob;
      return 'blob:netlist';
    });
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<ProjectMenu />);
    fireEvent.click(screen.getByRole('button', { name: 'Exportar SPICE' }));

    await waitFor(() => expect(clickSpy).toHaveBeenCalledOnce());
    expect(exportSpiceMock).toHaveBeenCalledWith(demoCircuit);
    const link = clickSpy.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toMatch(/\.cir$/);
    expect(saved?.type).toBe('text/plain');
    expect(await saved?.text()).toBe('* Demo\nR1 n1 0 100.0\n.op\n.end\n');
  });

  test('Exportar SPICE mostra os erros de um circuito inválido', async () => {
    const problem = {
      type: 'urn:vcccircuitlab:problem:invalid-circuit',
      title: 'Circuito inválido',
      status: 422,
      code: 'MISSING_GROUND',
      errors: [{ code: 'MISSING_GROUND', message: 'O circuito não tem terra.', refs: [] }],
    };
    exportSpiceMock.mockRejectedValue(new ApiError('problem', problem.title, { problem }));

    render(<ProjectMenu />);
    fireEvent.click(screen.getByRole('button', { name: 'Exportar SPICE' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível exportar a netlist SPICE');
    expect(alert).toHaveTextContent('O circuito não tem terra.');
  });

  test('Importar SPICE carrega o circuito traduzido e mostra os avisos', async () => {
    const imported = { ...demoCircuit, id: 'netlist-spice', name: 'Da netlist' };
    importSpiceMock.mockResolvedValue({
      circuit: imported,
      warnings: [
        { code: 'IGNORED_DIRECTIVE', message: 'Linha 5: a diretiva .tran foi ignorada.', refs: [] },
      ],
      issues: [],
    });

    render(<ProjectMenu />);
    chooseNetlist('Da netlist\nV1 a 0 9\n.tran 1u 1m\n');

    await waitFor(() => expect(useEditorStore.getState().circuit.id).toBe('netlist-spice'));
    expect(importSpiceMock).toHaveBeenCalledWith('Da netlist\nV1 a 0 9\n.tran 1u 1m\n');
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Importado "Da netlist" (SPICE).');
    expect(status).toHaveTextContent('Linha 5: a diretiva .tran foi ignorada.');
  });

  test('uma netlist inválida mostra os erros por linha e não altera o circuito', async () => {
    const problem = {
      type: 'urn:vcccircuitlab:problem:invalid-netlist',
      title: 'Netlist SPICE inválida',
      status: 422,
      code: 'INVALID_NETLIST',
      errors: [
        {
          code: 'UNSUPPORTED_ELEMENT',
          message: 'Linha 2: o elemento X1 não é suportado.',
          refs: [],
        },
      ],
    };
    importSpiceMock.mockRejectedValue(new ApiError('problem', problem.title, { problem }));

    render(<ProjectMenu />);
    chooseNetlist('T\nX1 a b sub\n', 'mau.cir');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível importar "mau.cir"');
    expect(alert).toHaveTextContent('Linha 2: o elemento X1 não é suportado.');
    expect(useEditorStore.getState().circuit).toBe(demoCircuit);
  });

  test('uma netlist demasiado grande é recusada sem chamar a API', async () => {
    render(<ProjectMenu />);
    chooseNetlist('*'.repeat(256 * 1024 + 1));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ficheiro demasiado grande');
    expect(importSpiceMock).not.toHaveBeenCalled();
  });

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

  test('ao arrancar, recupera automaticamente o último projeto gravado', async () => {
    const saved = { ...emptyCircuit(), name: 'Projeto recuperado' };
    await saveAutosave(saved);

    render(<ProjectMenu />);

    await waitFor(() => expect(useEditorStore.getState().circuit.name).toBe('Projeto recuperado'));
    expect(screen.getByText(/recuperado automaticamente/i)).toBeInTheDocument();
  });

  test('fechar o diálogo Gerar devolve o foco ao botão que o abriu', () => {
    render(<ProjectMenu />);
    const generateButton = screen.getByRole('button', { name: 'Gerar…' });
    fireEvent.click(generateButton);
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(generateButton).toHaveFocus();
  });
});
