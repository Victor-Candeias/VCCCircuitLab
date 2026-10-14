import { useEffect } from 'react';
import { LoginScreen } from './auth/LoginScreen';
import { useAuthStore } from './auth/authStore';
import { EditorCanvas } from './editor/EditorCanvas';
import { ProjectMenu } from './project/ProjectMenu';
import './auth/auth.css';

function App() {
  const status = useAuthStore((state) => state.status);
  const user = useAuthStore((state) => state.user);
  const restore = useAuthStore((state) => state.restore);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    void restore();
  }, [restore]);

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
