import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { toApiError } from '../api/client';
import { RegisterDialog } from './RegisterDialog';
import { useAuthStore } from './authStore';
import '../project/project.css';
import './auth.css';

/** Ecrã de login: sem sessão iniciada, a aplicação mostra apenas este ecrã. */
export function LoginScreen() {
  const titleId = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const login = useAuthStore((state) => state.login);
  const notice = useAuthStore((state) => state.notice);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRegister, setShowRegister] = useState(false);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (email.trim() === '' || password === '') {
      setError('Indique o email e a password.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (cause) {
      const apiError = toApiError(cause);
      setError(apiError.problem?.errors[0]?.message ?? apiError.message);
      setPassword('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login">
      <form
        className="login__card"
        aria-labelledby={titleId}
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        <h1 className="login__brand">VCCCircuitLab</h1>
        <h2 id={titleId}>Iniciar sessão</h2>

        {notice && !error && (
          <p className="login__notice" role="status">
            {notice}
          </p>
        )}

        <label className="generate-dialog__field">
          Email
          <input
            ref={emailRef}
            type="email"
            value={email}
            maxLength={254}
            autoComplete="username"
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label className="generate-dialog__field">
          Password
          <input
            type="password"
            value={password}
            maxLength={128}
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {error && (
          <div className="generate-dialog__error" role="alert">
            <strong>{error}</strong>
          </div>
        )}

        <button type="submit" className="login__submit" disabled={busy}>
          {busy ? 'A entrar…' : 'Entrar'}
        </button>

        <p className="login__register">
          Ainda não tem conta?{' '}
          <button type="button" className="login__link" onClick={() => setShowRegister(true)}>
            Criar conta
          </button>
        </p>
      </form>

      {showRegister && (
        <RegisterDialog
          onClose={() => setShowRegister(false)}
          onCreated={(createdEmail) => {
            setEmail(createdEmail);
            setPassword('');
            setError(null);
          }}
        />
      )}
    </main>
  );
}
