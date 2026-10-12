---
maestru: "0.4"
type: work-spec
id: e0-03-spec
title: "E0-03 — Plano de implementação de apps/web"
template: implementation-plan-v1
work-item: etapa-0/E0-03
owner: developer
created: 2026-10-12
---

# E0-03 — Plano de implementação de apps/web

## Overview

Criar o frontend em `apps/web` (React + TypeScript + Vite) como pacote do workspace pnpm, com `base` do Vite configurado para GitHub Pages (`Docs/arquitetura_simulador_circuitos.md` §9, §13).

## Implementation

### Fase 1 — Scaffold

1. `corepack pnpm@10 create vite apps/web --template react-ts --eslint --no-immediate --no-interactive` (Vite 8, React 19, TypeScript 6, ESLint).
2. Renomear o pacote para `@vcccircuitlab/web`; `index.html` com `lang="pt-PT"` e título `VCCCircuitLab`.

### Fase 2 — GitHub Pages

1. `vite.config.ts`: `base: process.env.BASE_PATH ?? '/VCCCircuitLab/'` (usar `BASE_PATH=/` com domínio próprio).

### Fase 3 — Dependências e documentação

1. `pnpm install` na raiz (atualiza o único `pnpm-lock.yaml`).
2. `apps/web/README.md` com comandos e nota sobre `BASE_PATH`.

### Verificação

- `pnpm build` e `pnpm lint` na raiz passam; `dist/index.html` referencia `/VCCCircuitLab/assets/...`.
- `pnpm --filter @vcccircuitlab/web dev` serve `http://localhost:<porta>/VCCCircuitLab/`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/**` | create | Scaffold Vite React TS (src, public, tsconfig, eslint) |
| `apps/web/package.json` | create | Pacote `@vcccircuitlab/web` e scripts dev/build/lint/preview |
| `apps/web/vite.config.ts` | create | `base` para GitHub Pages |
| `apps/web/index.html` | create | Título e idioma |
| `apps/web/README.md` | create | Comandos do frontend |
| `pnpm-lock.yaml` | update | Dependências do frontend |
