---
maestru: "0.4"
type: work-track
id: etapa-2
title: Etapa 2 — Validação e solver DC
created: 2026-10-12
description: "Normalizador de redes, validador topológico, solver MNA DC e API validate/simulate. Aceitação: 12 V + 100 Ω → 0,12 A e 1,44 W; circuito aberto e curto geram estados/avisos coerentes."
owner: developer
status: active
---

# etapa-2: Etapa 2 — Validação e solver DC

## Summary

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| E2-01 | Modelos Pydantic e normalizador de redes (union-find) | done | 2026-10-12 | developer | high | 2026-10-12 |  | etapa-0/E0-04, etapa-0/E0-07 | [E2-01](../specs/etapa-2/e2-01-spec.md) |
| E2-02 | Validador topológico e de valores | done | 2026-10-12 | developer | high | 2026-10-13 |  | E2-01 | [E2-02](../specs/etapa-2/e2-02-spec.md) |
| E2-03 | Solver MNA DC | done | 2026-10-12 | developer | critical | 2026-10-13 |  | E2-02 | [E2-03](../specs/etapa-2/e2-03-spec.md) |
| E2-04 | Testes do solver com resultados analíticos | backlog | 2026-10-12 | developer | high |  |  | E2-03 |  |
| E2-05 | Endpoints /validate e /simulate com erros problem+json | backlog | 2026-10-12 | developer | high |  |  | E2-03 |  |
| E2-06 | Endpoint GET /components (catálogo) | backlog | 2026-10-12 | developer | medium |  |  | etapa-0/E0-08 |  |
| E2-07 | Cliente API e apresentação de resultados no editor | backlog | 2026-10-12 | developer | high |  |  | E2-05, etapa-1/E1-07 |  |
<!-- /maestru:work-items-list -->
