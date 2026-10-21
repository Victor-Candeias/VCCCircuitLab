import { useCallback, useEffect, useState } from 'react';
import { deleteProject, getProject, listProjects, removeShare, toApiError } from '../api/client';
import type { ProjectDetail, ProjectSummary } from '../api/types';
import { useAuthStore } from '../auth/authStore';
import { ACCESS_LABELS, useCloudProjectStore } from './cloudProjectStore';
import { DialogError, ModalDialog } from './Dialog';

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString('pt-PT', { dateStyle: 'short', timeStyle: 'short' });

/**
 * "Projetos": lista os projetos guardados na conta e os partilhados com ela (F2-09). Abrir
 * entrega o projeto completo a `onOpen`, que devolve `true` se o carregou no editor (o
 * utilizador pode recusar descartar o circuito atual). O dono pode apagar; um convidado pode
 * sair da partilha.
 */
export function ProjectsDialog({
  onOpen,
  onClose,
}: {
  onOpen: (project: ProjectDetail) => boolean;
  onClose: () => void;
}) {
  const userId = useAuthStore((s) => s.user?.id);
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    listProjects({ signal: controller.signal }).then(setProjects, (cause: unknown) => {
      if (!controller.signal.aborted) {
        setError(`Não foi possível listar os projetos. ${toApiError(cause).message}`);
      }
    });
    return () => controller.abort();
  }, [reloadKey]);

  const run = async (id: string, action: () => Promise<void>) => {
    setBusyId(id);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(toApiError(cause).message);
    } finally {
      setBusyId(null);
    }
  };

  const onOpenClick = (project: ProjectSummary) =>
    run(project.id, async () => {
      const detail = await getProject(project.id);
      if (onOpen(detail)) onClose();
    });

  /** Apagar (dono) ou sair da partilha (convidado); o projeto deixa de estar ligado ao editor. */
  const onRemoveClick = (project: ProjectSummary) => {
    const owner = project.access === 'owner';
    const question = owner
      ? `Apagar o projeto "${project.name}" da conta? Os convidados perdem o acesso.`
      : `Deixar de ter acesso ao projeto "${project.name}"?`;
    if (!window.confirm(question)) return;
    void run(project.id, async () => {
      if (owner) await deleteProject(project.id);
      else if (userId) await removeShare(project.id, userId);
      const { link, unlink } = useCloudProjectStore.getState();
      if (link?.id === project.id) unlink();
      reload();
    });
  };

  const own = projects?.filter((p) => p.access === 'owner') ?? [];
  const shared = projects?.filter((p) => p.access !== 'owner') ?? [];

  const renderList = (items: ProjectSummary[], empty: string) =>
    items.length === 0 ? (
      <p className="projects-dialog__empty">{empty}</p>
    ) : (
      <ul className="projects-dialog__list">
        {items.map((project) => (
          <li key={project.id}>
            <div className="projects-dialog__info">
              <strong>{project.name}</strong>
              <span>
                {project.access !== 'owner' &&
                  `De ${project.owner.name} · ${ACCESS_LABELS[project.access]} · `}
                Alterado {formatDate(project.updatedAt)} por {project.updatedBy.name}
              </span>
            </div>
            <button
              type="button"
              disabled={busyId !== null}
              aria-label={`Abrir ${project.name}`}
              onClick={() => void onOpenClick(project)}
            >
              Abrir
            </button>
            <button
              type="button"
              disabled={busyId !== null}
              aria-label={`${project.access === 'owner' ? 'Apagar' : 'Sair de'} ${project.name}`}
              onClick={() => onRemoveClick(project)}
            >
              {project.access === 'owner' ? 'Apagar' : 'Sair'}
            </button>
          </li>
        ))}
      </ul>
    );

  return (
    <ModalDialog title="Projetos na conta" onClose={onClose} className="projects-dialog">
      <DialogError message={error} />
      {projects === null && !error && (
        <p role="status" className="projects-dialog__empty">
          A carregar os projetos…
        </p>
      )}
      {projects !== null && (
        <>
          <h3>Os meus projetos</h3>
          {renderList(own, 'Ainda não guardou nenhum projeto na conta.')}
          <h3>Partilhados comigo</h3>
          {renderList(shared, 'Nenhum projeto partilhado consigo.')}
        </>
      )}
      <div className="generate-dialog__actions">
        <button type="button" onClick={onClose}>
          Fechar
        </button>
      </div>
    </ModalDialog>
  );
}
