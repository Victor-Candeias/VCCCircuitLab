import { create } from 'zustand';
import type { ProjectAccess, ProjectSummary } from '../api/types';

/** Chave do projeto ligado no `sessionStorage` (acompanha o autosave depois de um refresh). */
export const CLOUD_PROJECT_STORAGE_KEY = 'vcccircuitlab.cloudProject';

export const ACCESS_LABELS: Record<ProjectAccess, string> = {
  owner: 'Dono',
  editor: 'Edição',
  viewer: 'Só leitura',
};

/** Projeto da conta aberto no editor (F2-09): onde "Guardar na conta" grava. */
export interface CloudProjectLink {
  id: string;
  /** Versão aberta/gravada; enviada ao gravar para detetar alterações de outras pessoas. */
  version: number;
  access: ProjectAccess;
  ownerName: string;
}

interface CloudProjectState {
  link: CloudProjectLink | null;
  /** Liga o editor ao projeto (depois de abrir, criar ou gravar). */
  linkProject: (project: ProjectSummary) => void;
  /** O editor passou a mostrar outro circuito (novo, ficheiro, exemplo…) ou a sessão terminou. */
  unlink: () => void;
}

const isAccess = (value: unknown): value is ProjectAccess =>
  value === 'owner' || value === 'editor' || value === 'viewer';

function readLink(): CloudProjectLink | null {
  try {
    const raw = sessionStorage.getItem(CLOUD_PROJECT_STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<CloudProjectLink>;
    if (
      typeof value.id === 'string' &&
      typeof value.version === 'number' &&
      isAccess(value.access) &&
      typeof value.ownerName === 'string'
    ) {
      return value as CloudProjectLink;
    }
  } catch {
    // sessionStorage indisponível ou conteúdo inválido: começa sem projeto ligado.
  }
  return null;
}

function writeLink(link: CloudProjectLink | null): void {
  try {
    if (link) sessionStorage.setItem(CLOUD_PROJECT_STORAGE_KEY, JSON.stringify(link));
    else sessionStorage.removeItem(CLOUD_PROJECT_STORAGE_KEY);
  } catch {
    // Sem sessionStorage a ligação fica só em memória.
  }
}

export const useCloudProjectStore = create<CloudProjectState>()((set) => ({
  link: readLink(),
  linkProject: (project) => {
    const link: CloudProjectLink = {
      id: project.id,
      version: project.version,
      access: project.access,
      ownerName: project.owner.name,
    };
    writeLink(link);
    set({ link });
  },
  unlink: () => {
    writeLink(null);
    set({ link: null });
  },
}));

/** Atalho para quem substitui o circuito do editor fora de um componente React. */
export const unlinkCloudProject = () => useCloudProjectStore.getState().unlink();
