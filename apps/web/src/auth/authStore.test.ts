import { afterEach, describe, expect, test, vi } from 'vitest';
import { ApiError, getCurrentUser, login, logoutSession, setAuthToken } from '../api/client';
import type { UserAccount } from '../api/types';
import { SESSION_STORAGE_KEY, useAuthStore } from './authStore';

vi.mock('../api/client', async (importActual) => ({
  ...(await importActual<typeof import('../api/client')>()),
  login: vi.fn(),
  getCurrentUser: vi.fn(),
  logoutSession: vi.fn(),
  setAuthToken: vi.fn(),
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
  vi.clearAllMocks();
});

describe('authStore', () => {
  test('login guarda o token no sessionStorage e envia-o nos pedidos', async () => {
    vi.mocked(login).mockResolvedValue({
      accessToken: 'tok',
      tokenType: 'bearer',
      expiresAt: '2030-01-01T00:00:00Z',
      user,
    });

    await useAuthStore.getState().login('ana@exemplo.pt', 'Abcdefg1!');

    expect(useAuthStore.getState()).toMatchObject({ status: 'authenticated', user, token: 'tok' });
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe('tok');
    expect(setAuthToken).toHaveBeenLastCalledWith('tok');
  });

  test('login recusado não altera a sessão', async () => {
    vi.mocked(login).mockRejectedValue(new ApiError('problem', 'Login inválido', { status: 401 }));

    await expect(useAuthStore.getState().login('ana@exemplo.pt', 'x')).rejects.toThrow();
    expect(useAuthStore.getState().status).toBe('anonymous');
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  test('restore sem token passa a anónimo sem contactar a API', async () => {
    useAuthStore.setState({ status: 'checking' });
    await useAuthStore.getState().restore();
    expect(useAuthStore.getState().status).toBe('anonymous');
    expect(getCurrentUser).not.toHaveBeenCalled();
  });

  test('restore com token válido autentica o utilizador (um só pedido em simultâneo)', async () => {
    useAuthStore.setState({ status: 'checking', token: 'tok' });
    vi.mocked(getCurrentUser).mockResolvedValue(user);

    await Promise.all([useAuthStore.getState().restore(), useAuthStore.getState().restore()]);

    expect(useAuthStore.getState()).toMatchObject({ status: 'authenticated', user });
    expect(getCurrentUser).toHaveBeenCalledTimes(1);
  });

  test('restore com token expirado limpa a sessão e mostra o aviso', async () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, 'velho');
    useAuthStore.setState({ status: 'checking', token: 'velho' });
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiError('problem', 'Autenticação necessária', { status: 401 }),
    );

    await useAuthStore.getState().restore();

    expect(useAuthStore.getState()).toMatchObject({
      status: 'anonymous',
      token: null,
      notice: 'A sessão expirou. Inicie sessão novamente.',
    });
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  test('logout termina a sessão local mesmo que a API falhe', async () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, 'tok');
    useAuthStore.setState({ status: 'authenticated', user, token: 'tok' });
    vi.mocked(logoutSession).mockRejectedValue(new ApiError('network', 'sem rede'));

    await useAuthStore.getState().logout();

    expect(logoutSession).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState()).toMatchObject({ status: 'anonymous', user: null, token: null });
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(setAuthToken).toHaveBeenLastCalledWith(null);
  });

  test('expire volta ao login com aviso', () => {
    useAuthStore.setState({ status: 'authenticated', user, token: 'tok' });
    useAuthStore.getState().expire();
    expect(useAuthStore.getState()).toMatchObject({
      status: 'anonymous',
      notice: 'A sessão expirou. Inicie sessão novamente.',
    });
  });
});
