import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import App from './App';
import { ApiError, getComponents, getCurrentUser, logoutSession } from './api/client';
import type { UserAccount } from './api/types';
import { SESSION_STORAGE_KEY, useAuthStore } from './auth/authStore';
import { catalog, isCatalogLoaded } from './editor/catalog';

vi.mock('./api/client', async (importActual) => ({
  ...(await importActual<typeof import('./api/client')>()),
  getCurrentUser: vi.fn(),
  getComponents: vi.fn(),
  logoutSession: vi.fn(),
}));

vi.mock('./editor/catalog', async (importActual) => {
  const actual = await importActual<typeof import('./editor/catalog')>();
  return { ...actual, isCatalogLoaded: vi.fn(actual.isCatalogLoaded) };
});

const user: UserAccount = {
  id: 'u1',
  name: 'Ana Silva',
  email: 'ana@exemplo.pt',
  role: 'USER',
  createdAt: '2025-01-01T00:00:00Z',
};

beforeEach(() => {
  vi.mocked(logoutSession).mockResolvedValue();
});

afterEach(() => {
  sessionStorage.clear();
  useAuthStore.setState({ status: 'anonymous', user: null, token: null, notice: null });
  vi.mocked(getCurrentUser).mockReset();
  vi.mocked(getComponents).mockReset();
  vi.mocked(isCatalogLoaded).mockRestore();
});

describe('App', () => {
  test('sem sessão mostra apenas o ecrã de login', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Iniciar sessão' })).toBeInTheDocument();
    expect(screen.queryByText('R1')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Projeto|Abrir|Guardar/ })).not.toBeInTheDocument();
  });

  test('com sessão iniciada mostra o editor, o utilizador e "Terminar sessão"', async () => {
    useAuthStore.setState({ status: 'authenticated', user, token: 't' });
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'VCCCircuitLab' })).toBeInTheDocument();
    expect(screen.getByText('R1')).toBeInTheDocument();
    expect(screen.getByText('Ana Silva')).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Terminar sessão' }));
    });
    expect(screen.getByRole('heading', { name: 'Iniciar sessão' })).toBeInTheDocument();
    expect(logoutSession).toHaveBeenCalledTimes(1);
  });

  test('com token guardado valida a sessão antes de mostrar o editor', async () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, 'guardado');
    useAuthStore.setState({ status: 'checking', token: 'guardado' });
    vi.mocked(getCurrentUser).mockResolvedValue(user);

    render(<App />);
    expect(screen.getByRole('status')).toHaveTextContent('A validar a sessão');
    await waitFor(() => expect(screen.getByText('R1')).toBeInTheDocument());
  });

  test('sem catálogo carrega-o da API antes de mostrar o editor', async () => {
    vi.mocked(isCatalogLoaded).mockReturnValue(false);
    vi.mocked(getCurrentUser).mockResolvedValue(user);
    vi.mocked(getComponents).mockResolvedValue(catalog);
    useAuthStore.setState({ status: 'authenticated', user, token: 't' });

    render(<App />);
    expect(screen.getByRole('status')).toHaveTextContent('A carregar o catálogo');
    await waitFor(() => expect(screen.getByText('R1')).toBeInTheDocument());
    expect(getComponents).toHaveBeenCalledTimes(1);
  });

  test('falha ao carregar o catálogo mostra o erro e permite tentar novamente', async () => {
    vi.mocked(isCatalogLoaded).mockReturnValue(false);
    vi.mocked(getCurrentUser).mockResolvedValue(user);
    vi.mocked(getComponents)
      .mockRejectedValueOnce(new ApiError('network', 'Sem ligação à API.'))
      .mockResolvedValueOnce(catalog);
    useAuthStore.setState({ status: 'authenticated', user, token: 't' });

    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Sem ligação à API.');
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    await waitFor(() => expect(screen.getByText('R1')).toBeInTheDocument());
    expect(getComponents).toHaveBeenCalledTimes(2);
  });
});
