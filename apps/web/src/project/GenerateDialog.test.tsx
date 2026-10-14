import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from '../store/editorStore';
import { GenerateDialog } from './GenerateDialog';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, generateCircuit: vi.fn() };
});

import { ApiError, generateCircuit } from '../api/client';

const generateCircuitMock = vi.mocked(generateCircuit);
const initialState = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initialState, true);
});

afterEach(() => {
  vi.restoreAllMocks();
  generateCircuitMock.mockReset();
});

describe('GenerateDialog', () => {
  test('gera com os valores por omissão e substitui o circuito (com confirmação)', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const generated = { ...demoCircuit, id: 'gerado', name: 'Circuito gerado' };
    generateCircuitMock.mockResolvedValue(generated);
    const onClose = vi.fn();

    render(<GenerateDialog onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }));

    await waitFor(() => expect(useEditorStore.getState().circuit.id).toBe('gerado'));
    expect(confirm).toHaveBeenCalledOnce();
    expect(generateCircuitMock).toHaveBeenCalledWith('series_dc', {
      voltageV: 12,
      resistorsOhm: [100, 220],
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  test('não substitui o circuito se a confirmação for recusada', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    generateCircuitMock.mockResolvedValue({ ...demoCircuit, id: 'gerado' });
    const onClose = vi.fn();

    render(<GenerateDialog onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }));

    await waitFor(() => expect(generateCircuitMock).toHaveBeenCalledOnce());
    expect(confirm).toHaveBeenCalledOnce();
    expect(useEditorStore.getState().circuit).toBe(demoCircuit);
    expect(onClose).not.toHaveBeenCalled();
  });

  test('muda de template e envia os parâmetros do interruptor (incluindo o booleano)', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    generateCircuitMock.mockResolvedValue({ ...demoCircuit, id: 'gerado' });

    render(<GenerateDialog onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Template'), { target: { value: 'switch_circuit' } });
    fireEvent.click(screen.getByLabelText('Fechado'));
    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }));

    await waitFor(() =>
      expect(generateCircuitMock).toHaveBeenCalledWith('switch_circuit', {
        voltageV: 12,
        loadOhm: 100,
        closed: false,
      }),
    );
  });

  test('mostra o erro de parâmetros devolvido pela API sem alterar o circuito', async () => {
    const problem = {
      type: 'urn:vcccircuitlab:problem:invalid-parameters',
      title: 'Parâmetros inválidos',
      status: 422,
      code: 'INVALID_PARAMETERS',
      errors: [
        {
          code: 'OUT_OF_RANGE',
          message: 'Tensão fora do intervalo.',
          refs: [],
          pointer: '/parameters/voltageV',
        },
      ],
    };
    generateCircuitMock.mockRejectedValue(
      new ApiError('problem', problem.title, { status: 422, problem }),
    );

    render(<GenerateDialog onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Parâmetros inválidos');
    expect(alert).toHaveTextContent('/parameters/voltageV');
    expect(alert).toHaveTextContent('Tensão fora do intervalo.');
    expect(useEditorStore.getState().circuit).toBe(demoCircuit);
  });

  test('valida localmente uma lista de resistências vazia sem chamar a API', () => {
    render(<GenerateDialog onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Resistências (Ω, separadas por vírgula)'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }));

    expect(screen.getByRole('alert')).toHaveTextContent('indique um ou mais números válidos');
    expect(generateCircuitMock).not.toHaveBeenCalled();
  });

  test('Cancelar fecha o diálogo sem gerar', () => {
    const onClose = vi.fn();
    render(<GenerateDialog onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(generateCircuitMock).not.toHaveBeenCalled();
  });

  test('Esc fecha o diálogo (acessibilidade por teclado)', () => {
    const onClose = vi.fn();
    render(<GenerateDialog onClose={onClose} />);
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  test('foca o primeiro campo ao abrir', () => {
    render(<GenerateDialog onClose={vi.fn()} />);
    expect(screen.getByLabelText('Template')).toHaveFocus();
  });
});
