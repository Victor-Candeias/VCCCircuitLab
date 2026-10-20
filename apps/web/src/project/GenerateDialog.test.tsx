import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { demoCircuit } from '../editor/demoCircuit';
import { useEditorStore } from '../store/editorStore';
import { GenerateDialog } from './GenerateDialog';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, generateCircuit: vi.fn(), generateFromText: vi.fn() };
});

import { ApiError, generateCircuit, generateFromText } from '../api/client';
import type { GenerateTextResult } from '../api/types';

const generateCircuitMock = vi.mocked(generateCircuit);
const generateFromTextMock = vi.mocked(generateFromText);
const initialState = useEditorStore.getState();

beforeEach(() => {
  useEditorStore.setState(initialState, true);
});

afterEach(() => {
  vi.restoreAllMocks();
  generateCircuitMock.mockReset();
  generateFromTextMock.mockReset();
});

const interpretation: GenerateTextResult = {
  template: 'series_dc',
  title: 'Circuito em série',
  parameters: { voltageV: 12, resistorsOhm: [100, 220] },
  summary: 'Circuito em série: fonte de 12 V e resistências de 100 Ω e 220 Ω.',
  assumptions: ['Topologia não indicada: assumido um circuito em série.'],
  circuit: { ...demoCircuit, id: 'interpretado' },
  warnings: [],
};

const switchToText = () => fireEvent.click(screen.getByLabelText('Texto livre'));
const typeDescription = (text: string) =>
  fireEvent.change(screen.getByLabelText('Descrição do circuito'), { target: { value: text } });

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
    expect(screen.getByLabelText('Por template')).toHaveFocus();
  });

  describe('texto livre', () => {
    test('interpreta, mostra resumo, valores assumidos e pré-visualização antes de abrir', async () => {
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
      generateFromTextMock.mockResolvedValue(interpretation);
      const onClose = vi.fn();

      render(<GenerateDialog onClose={onClose} />);
      switchToText();
      typeDescription('  12 V com 100 e 220 Ω  ');
      fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }));

      const section = await screen.findByRole('region', { name: 'Interpretação' });
      expect(generateFromTextMock).toHaveBeenCalledWith('12 V com 100 e 220 Ω');
      expect(section).toHaveTextContent(interpretation.summary);
      expect(section).toHaveTextContent('Topologia não indicada');
      const preview = screen.getByRole('img', {
        name: `Pré-visualização: ${interpretation.summary}`,
      });
      expect(preview.querySelectorAll('[data-component-id]')).toHaveLength(
        demoCircuit.components.length,
      );
      expect(preview.querySelectorAll('path.circuit-preview__wire')).toHaveLength(
        demoCircuit.wires.length,
      );
      expect(useEditorStore.getState().circuit).toBe(demoCircuit);

      fireEvent.click(screen.getByRole('button', { name: 'Abrir no editor' }));

      expect(confirm).toHaveBeenCalledOnce();
      expect(useEditorStore.getState().circuit.id).toBe('interpretado');
      expect(onClose).toHaveBeenCalledOnce();
    });

    test('alterar o texto descarta a interpretação anterior', async () => {
      generateFromTextMock.mockResolvedValue(interpretation);

      render(<GenerateDialog onClose={vi.fn()} />);
      switchToText();
      typeDescription('série 12 V 1k');
      fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }));
      await screen.findByRole('button', { name: 'Abrir no editor' });

      typeDescription('paralelo 12 V 1k');

      expect(screen.queryByRole('region', { name: 'Interpretação' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Interpretar' })).toBeInTheDocument();
    });

    test('mostra o problema da API quando o texto não é interpretável', async () => {
      const problem = {
        type: 'urn:vcccircuitlab:problem:uninterpretable-text',
        title: 'Não foi possível interpretar o pedido',
        status: 422,
        code: 'UNINTERPRETABLE_TEXT',
        errors: [{ code: 'UNINTERPRETABLE_TEXT', message: 'Descreva a topologia.', refs: [] }],
      };
      generateFromTextMock.mockRejectedValue(
        new ApiError('problem', problem.title, { status: 422, problem }),
      );

      render(<GenerateDialog onClose={vi.fn()} />);
      switchToText();
      typeDescription('uma torradeira');
      fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Não foi possível interpretar o pedido');
      expect(alert).toHaveTextContent('Descreva a topologia.');
      expect(useEditorStore.getState().circuit).toBe(demoCircuit);
    });

    test('não chama a API com a descrição vazia', () => {
      render(<GenerateDialog onClose={vi.fn()} />);
      switchToText();
      fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }));

      expect(screen.getByRole('alert')).toHaveTextContent('Descreva o circuito');
      expect(generateFromTextMock).not.toHaveBeenCalled();
    });
  });
});
