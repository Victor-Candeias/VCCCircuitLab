---
maestru: "0.4"
type: work-track
id: fase-2
title: Fase 2 — Evolução pós-MVP
created: 2026-10-12
description: "Funcionalidades fora do MVP (secção 11): ngspice, transitórios, instrumentos virtuais, semicondutores, 230/400 V e iluminação de escada."
owner: developer
status: draft
---

# fase-2: Fase 2 — Evolução pós-MVP

## Summary

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| F2-01 | Integração ngspice (tradutor JSON → netlist SPICE) | done | 2026-10-12 | developer | high | 2026-10-19 |  |  | [F2-01](../specs/fase-2/f2-01-spec.md) |
| F2-02 | Condensadores, bobinas e análise transitória | done | 2026-10-12 | developer | high | 2026-10-19 |  | F2-01 | [F2-02](../specs/fase-2/f2-02-spec.md) |
| F2-03 | Instrumentos virtuais: voltímetro, amperímetro e osciloscópio | done | 2026-10-12 | developer | high | 2026-10-20 |  | F2-02 | [F2-03](../specs/fase-2/f2-03-spec.md) |
| F2-04 | Díodos, LEDs e transístores | done | 2026-10-12 | developer | medium | 2026-10-20 |  | F2-01 | [F2-04](../specs/fase-2/f2-04-spec.md) |
| F2-05 | Importação/exportação SPICE | backlog | 2026-10-12 | developer | medium |  |  | F2-01 |  |
| F2-06 | Gerador de circuitos por linguagem natural | backlog | 2026-10-12 | developer | medium |  |  |  |  |
| F2-07 | Catálogo IEC e modelos para instalações 230/400 V | backlog | 2026-10-12 | developer | medium |  |  |  |  |
| F2-08 | Template de geração iluminacao_escada (230 V) | backlog | 2026-10-12 | developer | medium |  |  | F2-07 |  |
| F2-09 | Contas, partilha e colaboração | backlog | 2026-10-12 | developer | low |  |  |  |  |
| F2-10 | Coleção de templates de componentes com acesso restrito a admin | done | 2026-10-14 | developer | medium | 2026-10-14 |  |  |  |
| F2-11 | Catálogo de componentes do frontend a partir da API (remover ficheiro estático) | done | 2026-10-15 | developer | medium | 2026-10-19 |  |  | [F2-11](../specs/fase-2/f2-11-spec.md) |
<!-- /maestru:work-items-list -->
