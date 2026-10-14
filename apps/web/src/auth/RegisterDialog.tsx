import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { createUser, toApiError } from '../api/client';
import type { CircuitIssue } from '../api/types';
import {
  MIN_PASSWORD_LEVEL,
  PASSWORD_LEVEL_COLORS,
  PASSWORD_LEVEL_LABELS,
  passwordLevel,
} from './passwordStrength';
import '../project/project.css';
import './auth.css';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const EMAIL_PATTERN = /^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/;

interface FormError {
  title: string;
  issues: readonly CircuitIssue[];
}

/** Barra de qualidade da password: cresce e passa de vermelho a verde com o nível. */
export function PasswordStrengthMeter({ password }: { password: string }) {
  const level = passwordLevel(password);
  const empty = password.length === 0;
  return (
    <div className="strength">
      <div
        className="strength__bar"
        role="progressbar"
        aria-label="Qualidade da password"
        aria-valuemin={0}
        aria-valuemax={4}
        aria-valuenow={empty ? 0 : level}
        aria-valuetext={empty ? 'Sem password' : PASSWORD_LEVEL_LABELS[level]}
      >
        <div
          className="strength__fill"
          style={{
            width: empty ? '0%' : `${(level + 1) * 20}%`,
            background: PASSWORD_LEVEL_COLORS[level],
          }}
        />
      </div>
      <span className="strength__label" aria-live="polite">
        {empty ? 'Qualidade da password' : PASSWORD_LEVEL_LABELS[level]}
      </span>
    </div>
  );
}

/**
 * Diálogo "Criar conta": nome, email, password e repetição da password, com a qualidade da
 * password numa barra do vermelho ao verde. Os dados são validados aqui e de novo pela API
 * (`POST /api/v1/users`), que os guarda encriptados na base de dados.
 */
export function RegisterDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  /** Chamado com o email da conta criada (o ecrã de login pré-preenche-o). */
  onCreated?: (email: string) => void;
}) {
  const titleId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  const [createdName, setCreatedName] = useState<string | null>(null);

  useEffect(() => {
    formRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)?.focus();
  }, []);

  // Esc fecha o diálogo; Tab/Shift+Tab ficam contidos nos seus campos (foco preso).
  const onKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(
      formRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const mismatch = confirm.length > 0 && confirm !== password;

  const validate = (): string | null => {
    if (name.trim() === '') return 'Indique o nome.';
    if (!EMAIL_PATTERN.test(email.trim())) return 'Indique um email válido.';
    if (passwordLevel(password) < MIN_PASSWORD_LEVEL) {
      return 'A password é demasiado fraca: use pelo menos 8 caracteres com letras, números e símbolos, ou 12 caracteres.';
    }
    if (password !== confirm) return 'As passwords não coincidem.';
    return null;
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const problem = validate();
    if (problem) {
      setError({ title: problem, issues: [] });
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const account = await createUser({
        name: name.trim(),
        email: email.trim(),
        password,
        passwordConfirm: confirm,
      });
      setPassword('');
      setConfirm('');
      setCreatedName(account.name);
      onCreated?.(account.email);
    } catch (cause) {
      const apiError = toApiError(cause);
      setError({
        title: apiError.problem?.title ?? apiError.message,
        issues: apiError.problem?.errors ?? [],
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="generate-dialog__overlay" onClick={onClose}>
      <form
        ref={formRef}
        className="generate-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => void onSubmit(event)}
        onKeyDown={onKeyDown}
        noValidate
      >
        <h2 id={titleId}>Criar conta</h2>

        {createdName !== null ? (
          <>
            <p role="status" className="register__success">
              Conta criada com sucesso. Bem-vindo(a), {createdName}! Já pode iniciar sessão.
            </p>
            <div className="generate-dialog__actions">
              <button type="button" onClick={onClose}>
                Fechar
              </button>
            </div>
          </>
        ) : (
          <>
            <label className="generate-dialog__field">
              Nome
              <input
                value={name}
                maxLength={100}
                autoComplete="name"
                onChange={(event) => setName(event.target.value)}
              />
            </label>

            <label className="generate-dialog__field">
              Email
              <input
                type="email"
                value={email}
                maxLength={254}
                autoComplete="email"
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label className="generate-dialog__field">
              Password
              <input
                type="password"
                value={password}
                maxLength={128}
                autoComplete="new-password"
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <PasswordStrengthMeter password={password} />

            <label className="generate-dialog__field">
              Repetir password
              <input
                type="password"
                value={confirm}
                maxLength={128}
                autoComplete="new-password"
                aria-invalid={mismatch}
                onChange={(event) => setConfirm(event.target.value)}
              />
            </label>
            <span className="register__mismatch" aria-live="polite">
              {mismatch ? 'As passwords não coincidem.' : ''}
            </span>

            {error && (
              <div className="generate-dialog__error" role="alert">
                <strong>{error.title}</strong>
                {error.issues.length > 0 && (
                  <ul>
                    {error.issues.map((issue, index) => (
                      <li key={index}>{issue.message}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div className="generate-dialog__actions">
              <button type="button" onClick={onClose}>
                Cancelar
              </button>
              <button type="submit" disabled={busy}>
                {busy ? 'A criar…' : 'Criar conta'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}
