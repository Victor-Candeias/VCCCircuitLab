import { useEffect, useState, type FormEvent } from 'react';
import { getProject, removeShare, shareProject, toApiError } from '../api/client';
import type { ProjectDetail, ShareRole } from '../api/types';
import { ACCESS_LABELS } from './cloudProjectStore';
import { DialogError, ModalDialog } from './Dialog';

const ROLES: ShareRole[] = ['viewer', 'editor'];

/**
 * "Partilhar": o dono do projeto (F2-09) convida outras contas pelo email, com permissão de
 * leitura (`viewer`) ou de edição (`editor`), muda a permissão de um convidado ou remove-o.
 */
export function ShareDialog({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<ShareRole>('viewer');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getProject(projectId, { signal: controller.signal }).then(setProject, (cause: unknown) => {
      if (!controller.signal.aborted) setError(toApiError(cause).message);
    });
    return () => controller.abort();
  }, [projectId]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(toApiError(cause).message);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const target = email.trim();
    if (!target) return;
    void run(async () => {
      setProject(await shareProject(projectId, target, role));
      setEmail('');
    });
  };

  const onRoleChange = (shareEmail: string, next: ShareRole) =>
    void run(async () => setProject(await shareProject(projectId, shareEmail, next)));

  const onRemove = (userId: string) =>
    void run(async () => {
      await removeShare(projectId, userId);
      setProject(
        (current) =>
          current && { ...current, shares: current.shares.filter((s) => s.user.id !== userId) },
      );
    });

  return (
    <ModalDialog
      title={project ? `Partilhar "${project.name}"` : 'Partilhar projeto'}
      onClose={onClose}
      className="projects-dialog"
    >
      <form className="share-dialog__form" onSubmit={onSubmit}>
        <label className="generate-dialog__field">
          Email da conta
          <input
            type="email"
            value={email}
            required
            maxLength={254}
            autoComplete="off"
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="generate-dialog__field">
          Permissão
          <select value={role} onChange={(event) => setRole(event.target.value as ShareRole)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ACCESS_LABELS[r]}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy || !project}>
          Partilhar
        </button>
      </form>

      <DialogError message={error} />

      <h3>Com acesso</h3>
      {project === null ? (
        !error && (
          <p role="status" className="projects-dialog__empty">
            A carregar…
          </p>
        )
      ) : project.shares.length === 0 ? (
        <p className="projects-dialog__empty">Ainda não partilhou este projeto.</p>
      ) : (
        <ul className="projects-dialog__list">
          {project.shares.map((share) => (
            <li key={share.user.id}>
              <div className="projects-dialog__info">
                <strong>{share.user.name}</strong>
                <span>{share.user.email}</span>
              </div>
              <select
                aria-label={`Permissão de ${share.user.name}`}
                value={share.role}
                disabled={busy}
                onChange={(event) =>
                  onRoleChange(share.user.email, event.target.value as ShareRole)
                }
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ACCESS_LABELS[r]}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={busy}
                aria-label={`Remover ${share.user.name}`}
                onClick={() => onRemove(share.user.id)}
              >
                Remover
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="generate-dialog__actions">
        <button type="button" onClick={onClose}>
          Fechar
        </button>
      </div>
    </ModalDialog>
  );
}
