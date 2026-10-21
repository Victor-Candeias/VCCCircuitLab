---
maestru: "0.4"
type: work-spec
id: f2-09-spec
title: "F2-09 — Contas, partilha e colaboração"
template: implementation-plan-v1
work-item: fase-2/F2-09
owner: developer
created: 2026-10-21
---

# F2-09 — Contas, partilha e colaboração

## Overview

As contas (E5-08), o login (E5-09) e os roles (E5-10) já existem; os circuitos só eram guardados
localmente (IndexedDB e ficheiros JSON). Este work-item acrescenta **projetos guardados na conta**
(coleção `projects` do MongoDB), **partilha por email** com permissões e **colaboração
assíncrona** com controlo de versões otimista.

Decisões:

- **Projeto = documento canónico do circuito** (`CircuitDocument`, validado pelo modelo
  Pydantic estrito) + dono + partilhas + `version`. O nome do projeto é o `name` do circuito.
- **Permissões:** `owner` (tudo), `editor` (ler e guardar), `viewer` (só ler). Só o dono apaga,
  partilha ou altera permissões; qualquer convidado pode sair da partilha.
- **Sem acesso = 404** (`project-not-found`): não se revela a existência de projetos alheios.
  Com acesso mas sem permissão (ex.: `viewer` a guardar) = 403 `forbidden`.
- **Colaboração:** cada gravação envia a `version` lida; se outra pessoa gravou entretanto, a API
  responde 409 `project-version-conflict` e nada é perdido no servidor. Edição simultânea em tempo
  real (websockets/CRDT) fica fora do âmbito.
- **Partilha por email:** o email é procurado pelo índice cego (`emailIndex`) dos utilizadores;
  email sem conta = 404 `share-user-not-found`; partilhar com o próprio dono = 422 `invalid-share`.
- Os dados pessoais (nome/email) continuam encriptados em `users`; as respostas desencriptam-nos
  para mostrar dono, convidados e autor da última alteração.

## Implementation

### Phase 1: Backend (`apps/api`)

| Action | File | Details |
|---|---|---|
| Create | `app/models/project.py` | `ProjectCreate`, `ProjectUpdate` (`circuit`, `version`), `ShareRequest` (`email`, `role`), `ProjectSummary`, `ProjectOut`, `ProjectUser`, `ProjectShare`. |
| Create | `app/projects/errors.py` | `ProjectNotFoundError`, `ProjectVersionConflictError`, `ShareUserNotFoundError`, `InvalidShareError`. |
| Create | `app/projects/service.py` | CRUD da coleção `projects`, controlo de acesso, versão otimista (`update_one` com filtro `version` + `$inc`), partilhas. |
| Create | `app/routes/projects.py` | `GET/POST /api/v1/projects`, `GET/PUT/DELETE /api/v1/projects/{id}`, `PUT /api/v1/projects/{id}/shares`, `DELETE /api/v1/projects/{id}/shares/{userId}`. |
| Modify | `app/main.py` | Registar o router protegido por `require_user`. |
| Modify | `app/problems.py` | Códigos `PROJECT_NOT_FOUND`, `PROJECT_VERSION_CONFLICT`, `SHARE_USER_NOT_FOUND`, `INVALID_SHARE` e handlers. |
| Create | `tests/test_api_projects.py` | CRUD, permissões, partilha e conflito de versões com `mongomock`. |

### Phase 2: Frontend (`apps/web`)

| Action | File | Details |
|---|---|---|
| Modify | `src/api/types.ts`, `src/api/client.ts` | Tipos dos projetos; `requestJson` aceita `PUT`/`DELETE`; funções `listProjects`, `getProject`, `createProject`, `saveProject`, `deleteProject`, `shareProject`, `removeShare`. |
| Create | `src/project/cloudProjectStore.ts` | Ligação entre o editor e o projeto da conta (`id`, `version`, `access`), guardada no `sessionStorage`; limpa ao terminar sessão. |
| Create | `src/project/ProjectsDialog.tsx` | Lista "Os meus projetos" e "Partilhados comigo": abrir, apagar (dono) e sair (convidado). |
| Create | `src/project/ShareDialog.tsx` | Convidados do projeto atual: adicionar por email, mudar permissão e remover. |
| Create | `src/project/Dialog.tsx` | Moldura de diálogo modal (foco inicial, Esc, foco preso). |
| Modify | `src/project/ProjectMenu.tsx` | Botões "Guardar na conta", "Projetos…" e "Partilhar…"; desligar o projeto ao abrir outro circuito; avisos de conflito/sem permissão. |
| Modify | `src/project/GenerateDialog.tsx`, `src/auth/authStore.ts` | Desligar o projeto ao gerar um circuito novo e ao terminar sessão. |
| Create/Modify | testes `*.test.ts(x)` | Cliente, store e diálogos. |

### Phase 3: Documentação

| Action | File | Details |
|---|---|---|
| Modify | `apps/api/README.md` | Secção "Projetos, partilha e colaboração (F2-09)". |
| Modify | `apps/web/README.md`, `Docs/guia-utilizacao.md` | Utilização dos projetos na conta e da partilha. |

Checklist:
- [x] `pytest` e `ruff` do backend passam
- [x] `vitest`, `tsc -b` e `eslint` do frontend passam
- [x] Documentação atualizada (a §8 da arquitetura é o contrato inicial do MVP e mantém-se; os
  endpoints ficam documentados em `apps/api/README.md`)

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/models/project.py` | Create | Modelos Pydantic dos projetos |
| `apps/api/app/projects/*` | Create | Serviço e erros dos projetos |
| `apps/api/app/routes/projects.py` | Create | Endpoints `/api/v1/projects` |
| `apps/api/app/main.py` | Modify | Registo do router |
| `apps/api/app/problems.py` | Modify | Erros problem+json |
| `apps/api/tests/test_api_projects.py` | Create | Testes da API |
| `apps/web/src/api/*` | Modify | Cliente e tipos |
| `apps/web/src/project/*` | Create/Modify | Store, diálogos e menu |
| `apps/web/src/auth/authStore.ts` | Modify | Limpar ligação ao terminar sessão |
| `apps/api/README.md`, `apps/web/README.md`, `Docs/*` | Modify | Documentação |
