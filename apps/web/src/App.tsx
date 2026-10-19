import { useEffect, useState } from 'react';
import { getComponents, toApiError } from './api/client';
import { LoginScreen } from './auth/LoginScreen';
import { useAuthStore } from './auth/authStore';
import { isCatalogLoaded, setCatalog } from './editor/catalog';
import { EditorCanvas } from './editor/EditorCanvas';
import { ProjectMenu } from './project/ProjectMenu';
import './auth/auth.css';

function App() {
  const status = useAuthStore((state) => state.status);
  const user = useAuthStore((state) => state.user);
  const restore = useAuthStore((state) => state.restore);
  const logout = useAuthStore((state) => state.logout);

  const authenticated = status === 'authenticated' && !!user;
  // O catálogo vem da API (F2-11), que exige sessão: só se carrega depois de autenticado e
  // antes de montar o editor (os consumidores de `editor/catalog` leem-no de forma síncrona).
  const [catalogReady, setCatalogReady] = useState(isCatalogLoaded);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogAttempt, setCatalogAttempt] = useState(0);

  useEffect(() => {
    void restore();
  }, [restore]);

  useEffect(() => {
    if (!authenticated || isCatalogLoaded()) return;
    const controller = new AbortController();
    getComponents({ signal: controller.signal }).then(
      (loaded) => {
        setCatalog(loaded);
        setCatalogReady(true);
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setCatalogError(toApiError(error).message);
      },
    );
    return () => controller.abort();
  }, [authenticated, catalogAttempt]);

  if (status === 'checking') {
    return (
      <main className="login">
        <p className="login__checking" role="status">
          A validar a sessão…
        </p>
      </main>
    );
  }

  if (status === 'anonymous' || !user) return <LoginScreen />;

  if (!catalogReady) {
    return (
      <main className="login">
        {catalogError ? (
          <div className="generate-dialog__error" role="alert">
            <p>Não foi possível carregar o catálogo de componentes. {catalogError}</p>
            <button
              type="button"
              onClick={() => {
                setCatalogError(null);
                setCatalogAttempt((attempt) => attempt + 1);
              }}
            >
              Tentar novamente
            </button>
          </div>
        ) : (
          <p className="login__checking" role="status">
            A carregar o catálogo de componentes…
          </p>
        )}
      </main>
    );
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>VCCCircuitLab</h1>
        <span className="app__subtitle">Editor de circuitos</span>
        <ProjectMenu />
        <span className="app__user" title={user.email}>
          {user.name}
        </span>
        <button type="button" className="app__account" onClick={() => void logout()}>
          Terminar sessão
        </button>
      </header>
      <main className="app__editor">
        <EditorCanvas />
      </main>
    </div>
  );
}

export default App;
