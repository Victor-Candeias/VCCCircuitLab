import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, createUser: vi.fn() };
});

import { ApiError, createUser } from '../api/client';
import { PasswordStrengthMeter, RegisterDialog } from './RegisterDialog';

const createUserMock = vi.mocked(createUser);

afterEach(() => {
  createUserMock.mockReset();
});

function fill(values: { name?: string; email?: string; password?: string; confirm?: string }) {
  const set = (label: string, value: string | undefined) => {
    if (value !== undefined) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  };
  set('Nome', values.name);
  set('Email', values.email);
  set('Password', values.password);
  set('Repetir password', values.confirm);
}

const VALID = {
  name: ' Ana Silva ',
  email: 'ana@exemplo.pt',
  password: 'Abcdefg1!',
  confirm: 'Abcdefg1!',
};

describe('PasswordStrengthMeter', () => {
  test('vai do vermelho ao verde e cresce com a qualidade', () => {
    const { rerender } = render(<PasswordStrengthMeter password="" />);
    const bar = screen.getByRole('progressbar', { name: 'Qualidade da password' });
    const fill = () => bar.firstElementChild as HTMLElement;
    expect(fill().style.width).toBe('0%');

    rerender(<PasswordStrengthMeter password="abc" />);
    expect(screen.getByText('Muito fraca')).toBeInTheDocument();
    expect(fill().style.width).toBe('20%');
    expect(fill().style.background).toBe('rgb(217, 45, 32)');

    rerender(<PasswordStrengthMeter password="Abcdefghijklmn1!" />);
    expect(screen.getByText('Muito forte')).toBeInTheDocument();
    expect(bar).toHaveAttribute('aria-valuenow', '4');
    expect(fill().style.width).toBe('100%');
    expect(fill().style.background).toBe('rgb(22, 163, 74)');
  });
});

describe('RegisterDialog', () => {
  test('pede nome, email, password e repetição, e mostra a qualidade ao escrever', () => {
    render(<RegisterDialog onClose={vi.fn()} />);
    expect(screen.getByLabelText('Nome')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText('Repetir password')).toHaveAttribute('type', 'password');

    fill({ password: 'abc' });
    expect(screen.getByText('Muito fraca')).toBeInTheDocument();
    fill({ password: 'Abcdefghij1k' });
    expect(screen.getByText('Forte')).toBeInTheDocument();
  });

  test('avisa quando a repetição da password não coincide', () => {
    render(<RegisterDialog onClose={vi.fn()} />);
    fill({ password: 'Abcdefg1!', confirm: 'Abcdefg1' });
    expect(screen.getByText('As passwords não coincidem.')).toBeInTheDocument();
    fill({ confirm: 'Abcdefg1!' });
    expect(screen.queryByText('As passwords não coincidem.')).not.toBeInTheDocument();
  });

  test.each([
    [{ ...VALID, name: '  ' }, 'Indique o nome.'],
    [{ ...VALID, email: 'sem-arroba' }, 'Indique um email válido.'],
    [{ ...VALID, password: 'abcdefgh', confirm: 'abcdefgh' }, /demasiado fraca/],
    [{ ...VALID, confirm: 'Abcdefg1?' }, /As passwords não coincidem\./],
  ])('não envia dados inválidos (%#)', (values, message) => {
    render(<RegisterDialog onClose={vi.fn()} />);
    fill(values);
    fireEvent.click(screen.getByRole('button', { name: 'Criar conta' }));

    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(createUserMock).not.toHaveBeenCalled();
  });

  test('cria a conta e mostra a confirmação', async () => {
    createUserMock.mockResolvedValue({
      id: '1',
      name: 'Ana Silva',
      email: 'ana@exemplo.pt',
      createdAt: '2026-10-14T21:00:00Z',
    });
    const onClose = vi.fn();
    render(<RegisterDialog onClose={onClose} />);
    fill(VALID);
    fireEvent.click(screen.getByRole('button', { name: 'Criar conta' }));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ana Silva'));
    expect(createUserMock).toHaveBeenCalledWith({
      name: 'Ana Silva',
      email: 'ana@exemplo.pt',
      password: 'Abcdefg1!',
      passwordConfirm: 'Abcdefg1!',
    });
    fireEvent.click(screen.getByRole('button', { name: 'Fechar' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  test('mostra os erros devolvidos pela API (email já registado)', async () => {
    createUserMock.mockRejectedValue(
      new ApiError('problem', 'Já existe uma conta com este email.', {
        status: 409,
        problem: {
          type: 'urn:vcccircuitlab:problem:email-already-registered',
          title: 'Email já registado',
          status: 409,
          code: 'EMAIL_ALREADY_REGISTERED',
          errors: [
            {
              code: 'EMAIL_ALREADY_REGISTERED',
              message: 'Já existe uma conta com este email.',
              refs: [],
            },
          ],
        },
      }),
    );
    render(<RegisterDialog onClose={vi.fn()} />);
    fill(VALID);
    fireEvent.click(screen.getByRole('button', { name: 'Criar conta' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Email já registado');
    expect(alert).toHaveTextContent('Já existe uma conta com este email.');
    expect(screen.getByRole('button', { name: 'Criar conta' })).toBeEnabled();
  });

  test('Esc fecha o diálogo', () => {
    const onClose = vi.fn();
    render(<RegisterDialog onClose={onClose} />);
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
