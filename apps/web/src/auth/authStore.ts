import { create } from 'zustand';
import {
  getCurrentUser,
  login as loginRequest,
  logoutSession,
  setAuthToken,
  setUnauthorizedHandler,
  toApiError,
} from '../api/client';
import type { UserAccount } from '../api/types';
import { unlinkCloudProject } from '../project/cloudProjectStore';

/** Chave do token de sessão no `sessionStorage` (dura enquanto o separador estiver aberto). */
export const SESSION_STORAGE_KEY = 'vcccircuitlab.session';

export type AuthStatus = 'checking' | 'anonymous' | 'authenticated';

export interface AuthState {
  status: AuthStatus;
  user: UserAccount | null;
  token: string | null;
  /** Aviso a mostrar no ecrã de login (ex.: sessão expirada). */
  notice: string | null;
  /** Valida o token guardado (`GET /auth/me`); sem token passa logo a `anonymous`. */
  restore: () => Promise<void>;
  /** Inicia sessão; lança `ApiError` se as credenciais forem recusadas. */
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Sessão recusada pela API (expirada ou terminada): volta ao ecrã de login. */
  expire: () => void;
}

function readToken(): string | null {
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(SESSION_STORAGE_KEY, token);
    else sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // sessionStorage indisponível (modo privado restrito): a sessão fica só em memória.
  }
  setAuthToken(token);
}

const initialToken = readToken();
setAuthToken(initialToken);

let restoring: Promise<void> | null = null;

export const useAuthStore = create<AuthState>()((set, get) => ({
  status: initialToken ? 'checking' : 'anonymous',
  user: null,
  token: initialToken,
  notice: null,

  restore: () => {
    if (restoring) return restoring;
    const { token } = get();
    if (!token) {
      set({ status: 'anonymous', user: null });
      return Promise.resolve();
    }
    restoring = (async () => {
      try {
        const user = await getCurrentUser();
        if (get().token === token) set({ status: 'authenticated', user });
      } catch (cause) {
        if (get().token !== token) return;
        const error = toApiError(cause);
        writeToken(null);
        set({
          status: 'anonymous',
          user: null,
          token: null,
          notice:
            error.status === 401
              ? 'A sessão expirou. Inicie sessão novamente.'
              : `Não foi possível validar a sessão: ${error.message}`,
        });
      } finally {
        restoring = null;
      }
    })();
    return restoring;
  },

  login: async (email, password) => {
    const result = await loginRequest({ email, password });
    writeToken(result.accessToken);
    set({ status: 'authenticated', user: result.user, token: result.accessToken, notice: null });
  },

  logout: async () => {
    const { token } = get();
    writeToken(null);
    unlinkCloudProject();
    set({ status: 'anonymous', user: null, token: null, notice: null });
    if (!token) return;
    try {
      setAuthToken(token);
      await logoutSession();
    } catch {
      // A sessão local já terminou; se a API falhar, o token expira sozinho.
    } finally {
      setAuthToken(get().token);
    }
  },

  expire: () => {
    if (get().status === 'anonymous') return;
    writeToken(null);
    unlinkCloudProject();
    set({
      status: 'anonymous',
      user: null,
      token: null,
      notice: 'A sessão expirou. Inicie sessão novamente.',
    });
  },
}));

setUnauthorizedHandler(() => useAuthStore.getState().expire());
