---
maestru: "0.4"
type: work-track
id: etapa-5
title: Etapa 5 — Publicação
created: 2026-10-12
description: "CI/CD, deploy do frontend no GitHub Pages e do backend em Debian com HTTPS. Aceitação: site público acessível, API segura, health check e exemplos funcionais."
owner: developer
status: active
---

# etapa-5: Etapa 5 — Publicação

## Summary

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| E5-01 | Deploy do frontend no GitHub Pages | done | 2026-10-12 | developer | high | 2026-10-14 |  | etapa-0/E0-06, etapa-4/E4-05 |  |
| E5-02 | Containerizar a API (Docker não privilegiado e docker-compose) | done | 2026-10-12 | developer | high | 2026-10-12 |  | etapa-0/E0-04 | [E5-02](../specs/etapa-5/e5-02-spec.md) |
| E5-03 | Deploy do backend em Debian com HTTPS | done | 2026-10-12 | developer | high | 2026-10-14 |  | E5-02 |  |
| E5-04 | Segurança operacional da API | done | 2026-10-12 | developer | high | 2026-10-19 |  | E5-03 | [E5-04](../specs/etapa-5/e5-04-spec.md) |
| E5-05 | Monitorização, logs e health check | done | 2026-10-12 | developer | medium | 2026-10-19 |  | E5-03 | [E5-05](../specs/etapa-5/e5-05-spec.md) |
| E5-06 | Testes em desktop, tablet e browsers principais | done | 2026-10-12 | developer | medium | 2026-10-19 |  | E5-01, E5-03 | [E5-06](../specs/etapa-5/e5-06-spec.md) |
| E5-07 | Ligação à BD MongoDB com CRUD genérico de collections | done | 2026-10-14 | developer | medium | 2026-10-14 |  |  |  |
| E5-08 | Criar utilizador (registo) com dados encriptados na BD e barra de qualidade da password | done | 2026-10-14 | developer | high | 2026-10-14 |  | E5-07 | [E5-08](../specs/etapa-5/e5-08-spec.md) |
| E5-09 | Janela de login | done | 2026-10-14 | developer | high | 2026-10-14 |  | E5-08 | [E5-09](../specs/etapa-5/e5-09-spec.md) |
| E5-10 | Role de utilizador (USER/ADMIN) e utilizador admin | done | 2026-10-14 | developer | high | 2026-10-14 |  |  |  |
<!-- /maestru:work-items-list -->
