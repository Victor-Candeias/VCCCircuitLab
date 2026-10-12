---
maestru: "0.4"
type: work-track
id: etapa-0
title: Etapa 0 — Preparação
created: 2026-10-12
description: "Monorepo pnpm, FastAPI, CI, JSON Schema 1.0 e catálogo inicial. Aceitação: frontend e API arrancam localmente; CI executa testes mínimos."
owner: developer
status: active
---

# etapa-0: Etapa 0 — Preparação

## Summary

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| E0-01 | Inicializar monorepo pnpm (package.json raiz, pnpm-workspace.yaml, Corepack) | done | 2026-10-12 | developer | high | 2026-10-12 |  |  | [E0-01](../specs/etapa-0/e0-01-spec.md) |
| E0-02 | README, licença open source e ADRs iniciais | backlog | 2026-10-12 | developer | medium |  |  |  |  |
| E0-03 | Criar apps/web com Vite + React + TypeScript | done | 2026-10-12 | developer | high | 2026-10-12 |  | E0-01 | [E0-03](../specs/etapa-0/e0-03-spec.md) |
| E0-04 | Criar apps/api com FastAPI e endpoint /health | done | 2026-10-12 | developer | high | 2026-10-12 |  |  | [E0-04](../specs/etapa-0/e0-04-spec.md) |
| E0-05 | Configurar lint, format e testes (frontend e backend) | backlog | 2026-10-12 | developer | medium |  |  | E0-03, E0-04 |  |
| E0-06 | Pipelines CI no GitHub Actions (frontend e backend separados) | backlog | 2026-10-12 | developer | medium |  |  | E0-05 |  |
| E0-07 | Definir JSON Schema 1.0 do circuito (packages/circuit-schema) | done | 2026-10-12 | developer | high | 2026-10-12 |  |  | [E0-07](../specs/etapa-0/e0-07-spec.md) |
| E0-08 | Catálogo inicial de componentes e convenções | backlog | 2026-10-12 | developer | high |  |  | E0-07 |  |
<!-- /maestru:work-items-list -->
