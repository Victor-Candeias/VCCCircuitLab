import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { ApiError, createUser, login } from '../api/client';
import type { UserAccount } from '../api/types';
import { LoginScreen } from './LoginScreen';
import { useAuthStore } from './authStore';

vi.mock('../api/client', async (importActual) => ({
  ...(await importActual<typeof import('../api/client')>()),
  login: vi.fn(),
  createUser: vi.fn(),
}));

const user: UserAccount = {
  id: 'u1',
  name: 'Ana',
  email: 'ana@exemplo.pt',
  role: 'USER',
  createdAt: '2025-01-01T00:00:00Z',
};

afterEach(() => {
  sessionStorage.clear();
  useAuthStore.setState({ status: 'anonymous', user: null, token: null, notice: null });
  vi.mocked(login).mockReset();
  vi.mocked(createUser).mockReset();
});

const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe('LoginScreen', () => {
  test('inicia sessão com email e password', async () => {
    vi.mocked(login).mockResolvedValue({
      accessToken: 'tok',
      tokenType: 'bearer',
      expiresAt: '2030-01-01T00:00:00Z',
      user,
    });
    render(<LoginScreen />);
    expect(screen.getByLabelText('Email')).toHaveFocus();

    fill('Email', '  ana@exemplo.pt ');
    fill('Password', 'Abcdefg1!');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'));
    expect(login).toHaveBeenCalledWith({ email: 'ana@exemplo.pt', password: 'Abcdefg1!' });
    expect(useAuthStore.getState().user).toEqual(user);
  });

  test('pede email e password antes de contactar a API', () => {
    render(<LoginScreen />);
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Indique o email e a password.');
    expect(login).not.toHaveBeenCalled();
  });

  test('mostra o erro da API e limpa a password', async () => {
    vi.mocked(login).mockRejectedValue(
      new ApiError('problem', 'Login inválido', {
        status: 401,
        problem: {
          type: 'urn:vcccircuitlab:problem:invalid-credentials',
          title: 'Login inválido',
          status: 401,
          code: 'INVALID_CREDENTIALS',
          errors: [{ code: 'INVALID_CREDENTIALS', message: 'Email ou password incorretos.' }],
        } as never,
      }),
    );
    render(<LoginScreen />);
    fill('Email', 'ana@exemplo.pt');
    fill('Password', 'errada');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email ou password incorretos.');
    expect(screen.getByLabelText('Password')).toHaveValue('');
    expect(useAuthStore.getState().status).toBe('anonymous');
  });

  test('mostra o aviso de sessão expirada', () => {
    useAuthStore.setState({ notice: 'A sessão expirou. Inicie sessão novamente.' });
    render(<LoginScreen />);
    expect(screen.getByRole('status')).toHaveTextContent('A sessão expirou');
  });

  test('"Criar conta" abre o registo e, criada a conta, pré-preenche o email', async () => {
    vi.mocked(createUser).mockResolvedValue(user);
    render(<LoginScreen />);
    fireEvent.click(screen.getByRole('button', { name: 'Criar conta' }));
    const dialog = screen.getByRole('dialog', { name: 'Criar conta' });

    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Ana' } });
    const emails = screen.getAllByLabelText('Email');
    fireEvent.change(emails[emails.length - 1], { target: { value: 'ana@exemplo.pt' } });
    const passwords = screen.getAllByLabelText('Password');
    fireEvent.change(passwords[passwords.length - 1], { target: { value: 'Abcdefg1!' } });
    fireEvent.change(screen.getByLabelText('Repetir password'), {
      target: { value: 'Abcdefg1!' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: 'Criar conta' }).at(-1)!);

    expect(await screen.findByText(/Conta criada com sucesso/)).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveValue('ana@exemplo.pt');
  });
});
