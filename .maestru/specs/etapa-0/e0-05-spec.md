---
maestru: "0.4"
type: work-spec
id: e0-05-spec
title: "E0-05 — Plano de lint, format e testes"
template: implementation-plan-v1
work-item: etapa-0/E0-05
owner: developer
created: 2026-10-12
---

# E0-05 — Plano de lint, format e testes

## Overview

Ferramentas de qualidade para frontend e backend (§2, §10 Etapa 0): ESLint + Prettier + Vitest/Testing Library no frontend e ruff + pytest/httpx no backend, com um teste mínimo de cada lado.

Decisões:

- **Prettier na raiz** do workspace (um só estilo para `apps/web` e `packages/*`): `singleQuote`, `semi`, `trailingComma: all`, `printWidth: 100`, `endOfLine: auto` (o repositório tem ficheiros CRLF e LF e o `core.autocrlf` varia entre máquinas; evita normalizar o repositório inteiro).
- `.prettierignore` exclui Markdown (tabelas/prosa), `.maestru/`, `Docs/`, `apps/api/` (formatado pelo ruff), lockfile e tipos gerados por `json-schema-to-typescript` (o teste de sincronização compara-os com a saída do gerador).
- `eslint-config-prettier` no fim da configuração ESLint para desligar regras de estilo.
- **ruff** (lint + format) em vez de black/flake8/isort — uma só ferramenta, configurada em `pyproject.toml`.
- pytest + `httpx2` já existiam desde o E0-04 (`GET /health`).

## Implementation

1. Raiz: `prettier` (devDependency), `.prettierrc.json`, `.prettierignore`; scripts `format` (`prettier --write .`) e `format:check`.
2. `apps/web`: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `eslint-config-prettier`; bloco `test` no `vite.config.ts` (jsdom, `src/test/setup.ts`); scripts `test` (`vitest run`) e `test:watch`; teste mínimo `src/App.test.tsx`.
3. `apps/api`: `ruff==0.17.0` em `requirements-dev.txt`; `[tool.ruff]` (py312, 100 colunas, regras E/W/F/I/UP/B/SIM/N/PT).
4. Formatação inicial do código existente com Prettier.
5. READMEs (raiz, web, api) com os comandos.

Verificação: `pnpm format:check`, `pnpm lint`, `pnpm test` (43 + 2 testes), `pnpm build`, `ruff check apps/api`, `ruff format --check apps/api`, `pytest apps/api`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `.prettierrc.json`, `.prettierignore` | create | Configuração do Prettier |
| `package.json`, `pnpm-lock.yaml` | modify | Prettier e scripts `format`/`format:check` |
| `apps/web/package.json` | modify | Dependências e scripts de teste |
| `apps/web/vite.config.ts` | modify | Configuração do Vitest |
| `apps/web/eslint.config.js` | modify | `eslint-config-prettier` |
| `apps/web/src/test/setup.ts` | create | jest-dom + cleanup |
| `apps/web/src/App.test.tsx` | create | Teste mínimo do frontend |
| `apps/api/requirements-dev.txt`, `apps/api/pyproject.toml` | modify | ruff |
| `README.md`, `apps/web/README.md`, `apps/api/README.md` | modify | Comandos de lint/format/test |
| `apps/web/src/*`, `packages/circuit-schema/**` | modify | Formatação inicial com Prettier |
