---
maestru: "0.4"
type: work-spec
id: e0-01-spec
title: "E0-01 — Plano de implementação do monorepo pnpm"
template: implementation-plan-v1
work-item: etapa-0/E0-01
owner: developer
created: 2026-10-12
---

# E0-01 — Plano de implementação do monorepo pnpm

## Overview

Inicializar o monorepo pnpm na raiz do repositório, conforme `Docs/arquitetura_simulador_circuitos.md` §2, §9 e §15 (decisão 7): pnpm com workspaces ativado via Corepack, versão fixada em `packageManager` e um único lockfile `pnpm-lock.yaml`. O backend Python (`apps/api`) fica fora do workspace pnpm.

## Implementation

### Fase 1 — Manifesto raiz

1. Criar `package.json` raiz privado com `packageManager: pnpm@10.34.6`, `engines` (Node ≥ 20, pnpm ≥ 10) e scripts raiz que delegam recursivamente nos pacotes (`dev`, `build`, `lint`, `format`, `test`) com `--if-present`.

### Fase 2 — Workspace

1. Criar `pnpm-workspace.yaml` com `apps/web` e `packages/*` (sem `apps/api`).
2. Criar `.npmrc` com `engine-strict=true` para impor as versões de Node/pnpm.

### Fase 3 — Lockfile e documentação

1. Executar `corepack pnpm@10 install` para gerar `pnpm-lock.yaml`.
2. Documentar pré-requisitos e comandos iniciais no `README.md`.

### Verificação

- `corepack pnpm install --frozen-lockfile` conclui sem erros.
- `corepack pnpm -r list` e scripts raiz executam sem falhar (sem pacotes ainda).

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `package.json` | create | Manifesto raiz, `packageManager`, `engines` e scripts do workspace |
| `pnpm-workspace.yaml` | create | Declarar pacotes `apps/web` e `packages/*` |
| `.npmrc` | create | `engine-strict=true` |
| `pnpm-lock.yaml` | create | Único lockfile gerado pelo pnpm |
| `README.md` | update | Pré-requisitos e comandos iniciais |
