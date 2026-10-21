import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from '../store/editorStore';
import { emptyCircuit, serializeCircuit } from './circuitJson';
import { clearAutosave, saveAutosave } from './persistence';
import { ProjectMenu } from './ProjectMenu';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    exportSpice: vi.fn(),
    importSpice: vi.fn(),
    createProject: vi.fn(),
    saveProject: vi.fn(),
    listProjects: vi.fn(),
    getProject: vi.fn(),
    deleteProject: vi.fn(),
    shareProject: vi.fn(),
    removeShare: vi.fn(),
  };
});

import {
  ApiError,
  createProject,
  deleteProject,
  exportSpice,
  getProject,
  importSpice,
  listProjects,
  removeShare,
  saveProject,
  shareProject,
} from '../api/client';
import type { ProjectAccess, ProjectDetail } from '../api/types';
import { CLOUD_PROJECT_STORAGE_KEY, useCloudProjectStore } from './cloudProjectStore';

const exportSpiceMock = vi.mocked(exportSpice);
const importSpiceMock = vi.mocked(importSpice);
const initialState = useEditorStore.getState();

beforeEach(async () => {
  useEditorStore.setState(initialState, true);
  useCloudProjectStore.getState().unlink();
  await clearAutosave();
});

afterEach(async () => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
  sessionStorage.clear();
  await clearAutosave();
});

const ana = { id: 'u-ana', name: 'Ana', email: 'ana@exemplo.pt' };
const rui = { id: 'u-rui', name: 'Rui', email: 'rui@exemplo.pt' };

const cloudProject = (overrides: Partial<ProjectDetail> = {}): ProjectDetail => ({
  id: 'p1',
  name: demoCircuit.name,
  owner: ana,
  access: 'owner' as ProjectAccess,
  version: 1,
  createdAt: '2026-01-01T10:00:00Z',
  updatedAt: '2026-01-01T10:00:00Z',
  updatedBy: ana,
  circuit: demoCircuit,
  shares: [],
  ...overrides,
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

describe('ProjectMenu — projetos na conta (F2-09)', () => {
  test('Guardar na conta cria o projeto e liga-o ao editor; depois grava com a versão', async () => {
    vi.mocked(createProject).mockResolvedValue(cloudProject());
    vi.mocked(saveProject).mockResolvedValue(cloudProject({ version: 2 }));
    render(<ProjectMenu />);
    const share = screen.getByRole('button', { name: 'Partilhar…' });
    expect(share).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Guardar na conta' }));

    expect(await screen.findByText(/novo projeto/)).toBeInTheDocument();
    expect(createProject).toHaveBeenCalledWith(demoCircuit);
    expect(screen.getByText('Na conta')).toBeInTheDocument();
    expect(share).toBeEnabled();
    expect(JSON.parse(sessionStorage.getItem(CLOUD_PROJECT_STORAGE_KEY) ?? '')).toMatchObject({
      id: 'p1',
      version: 1,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Guardar na conta' }));

    expect(await screen.findByText(/versão 2/)).toBeInTheDocument();
    expect(saveProject).toHaveBeenCalledWith('p1', demoCircuit, 1);
    expect(useCloudProjectStore.getState().link?.version).toBe(2);
  });

  test('um conflito de versão mostra o erro e mantém a versão ligada', async () => {
    useCloudProjectStore.getState().linkProject(cloudProject({ version: 3 }));
    const problem = {
      type: 'urn:vcccircuitlab:problem:project-version-conflict',
      title: 'Conflito de versões',
      status: 409,
      detail: 'O projeto foi alterado por outra pessoa (versão atual: 4).',
      code: 'PROJECT_VERSION_CONFLICT',
      errors: [
        {
          code: 'PROJECT_VERSION_CONFLICT',
          message: 'O projeto foi alterado por outra pessoa (versão atual: 4).',
          refs: [],
        },
      ],
    };
    vi.mocked(saveProject).mockRejectedValue(
      new ApiError('problem', problem.detail, { status: 409, problem }),
    );
    render(<ProjectMenu />);

    fireEvent.click(screen.getByRole('button', { name: 'Guardar na conta' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível guardar na conta');
    expect(alert).toHaveTextContent('versão atual: 4');
    expect(useCloudProjectStore.getState().link?.version).toBe(3);
  });

  test('com permissão de leitura, Guardar na conta cria uma cópia (com confirmação)', async () => {
    useCloudProjectStore
      .getState()
      .linkProject(cloudProject({ owner: rui, access: 'viewer', updatedBy: rui }));
    vi.mocked(createProject).mockResolvedValue(cloudProject({ id: 'p2' }));
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ProjectMenu />);
    expect(screen.getByText('De Rui · Só leitura')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Guardar na conta' }));

    await waitFor(() => expect(useCloudProjectStore.getState().link?.id).toBe('p2'));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('permissão de leitura'));
    expect(saveProject).not.toHaveBeenCalled();
  });

  test('abrir um ficheiro desliga o projeto da conta', async () => {
    useCloudProjectStore.getState().linkProject(cloudProject());
    render(<ProjectMenu />);
    chooseFile(serializeCircuit({ ...demoCircuit, id: 'outro', name: 'Outro' }));

    await waitFor(() => expect(useEditorStore.getState().circuit.id).toBe('outro'));
    expect(useCloudProjectStore.getState().link).toBeNull();
    expect(sessionStorage.getItem(CLOUD_PROJECT_STORAGE_KEY)).toBeNull();
  });

  test('Projetos… lista os projetos e abre um partilhado no editor', async () => {
    const other = { ...demoCircuit, id: 'partilhado', name: 'Do Rui' };
    const shared = cloudProject({
      id: 'p2',
      name: 'Do Rui',
      owner: rui,
      access: 'editor',
      version: 5,
      updatedBy: rui,
      circuit: other,
    });
    vi.mocked(listProjects).mockResolvedValue([cloudProject({ name: 'Meu' }), shared]);
    vi.mocked(getProject).mockResolvedValue(shared);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ProjectMenu />);

    fireEvent.click(screen.getByRole('button', { name: 'Projetos…' }));

    const dialog = await screen.findByRole('dialog', { name: 'Projetos na conta' });
    expect(await screen.findByRole('button', { name: 'Apagar Meu' })).toBeInTheDocument();
    expect(dialog).toHaveTextContent('De Rui · Edição');
    fireEvent.click(screen.getByRole('button', { name: 'Abrir Do Rui' }));

    await waitFor(() => expect(useEditorStore.getState().circuit.id).toBe('partilhado'));
    expect(getProject).toHaveBeenCalledWith('p2');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(useCloudProjectStore.getState().link).toMatchObject({
      id: 'p2',
      version: 5,
      access: 'editor',
    });
    expect(screen.getByText('De Rui · Edição')).toBeInTheDocument();
  });

  test('Projetos… apaga um projeto próprio e desliga-o se estiver aberto', async () => {
    useCloudProjectStore.getState().linkProject(cloudProject());
    vi.mocked(listProjects)
      .mockResolvedValueOnce([cloudProject({ name: 'Meu' })])
      .mockResolvedValueOnce([]);
    vi.mocked(deleteProject).mockResolvedValue();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ProjectMenu />);

    fireEvent.click(screen.getByRole('button', { name: 'Projetos…' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Apagar Meu' }));

    expect(await screen.findByText(/Ainda não guardou nenhum projeto/)).toBeInTheDocument();
    expect(deleteProject).toHaveBeenCalledWith('p1');
    expect(useCloudProjectStore.getState().link).toBeNull();
  });

  test('Partilhar… convida por email, muda a permissão e remove o convidado', async () => {
    useCloudProjectStore.getState().linkProject(cloudProject());
    const withRui = cloudProject({ shares: [{ user: rui, role: 'viewer' }] });
    vi.mocked(getProject).mockResolvedValue(cloudProject());
    vi.mocked(shareProject)
      .mockResolvedValueOnce(withRui)
      .mockResolvedValueOnce(cloudProject({ shares: [{ user: rui, role: 'editor' }] }));
    vi.mocked(removeShare).mockResolvedValue();
    render(<ProjectMenu />);

    fireEvent.click(screen.getByRole('button', { name: 'Partilhar…' }));
    expect(await screen.findByText('Ainda não partilhou este projeto.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Email da conta'), {
      target: { value: ' rui@exemplo.pt ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Partilhar' }));

    const role = await screen.findByRole('combobox', { name: 'Permissão de Rui' });
    expect(shareProject).toHaveBeenCalledWith('p1', 'rui@exemplo.pt', 'viewer');
    expect(screen.getByLabelText('Email da conta')).toHaveValue('');

    fireEvent.change(role, { target: { value: 'editor' } });
    await waitFor(() => expect(role).toHaveValue('editor'));
    expect(shareProject).toHaveBeenLastCalledWith('p1', 'rui@exemplo.pt', 'editor');

    fireEvent.click(screen.getByRole('button', { name: 'Remover Rui' }));
    expect(await screen.findByText('Ainda não partilhou este projeto.')).toBeInTheDocument();
    expect(removeShare).toHaveBeenCalledWith('p1', 'u-rui');
  });

  test('Partilhar… mostra o erro de um email sem conta', async () => {
    useCloudProjectStore.getState().linkProject(cloudProject());
    vi.mocked(getProject).mockResolvedValue(cloudProject());
    vi.mocked(shareProject).mockRejectedValue(
      new ApiError('problem', 'Não existe nenhuma conta com esse email.', { status: 404 }),
    );
    render(<ProjectMenu />);

    fireEvent.click(screen.getByRole('button', { name: 'Partilhar…' }));
    await screen.findByText('Ainda não partilhou este projeto.');
    fireEvent.change(screen.getByLabelText('Email da conta'), {
      target: { value: 'x@exemplo.pt' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Partilhar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Não existe nenhuma conta');
  });
});
