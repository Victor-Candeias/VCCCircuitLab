---
maestru: "0.4"
type: work-track
id: etapa-1
title: Etapa 1 — Editor manual
created: 2026-10-12
description: "Canvas, símbolos SVG IEC, ligações, propriedades, undo/redo e JSON. Aceitação: criar e reabrir um circuito série e um paralelo sem perder ligações."
owner: developer
status: active
---

# etapa-1: Etapa 1 — Editor manual

## Summary

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| E1-01 | Canvas do editor com React Flow (grelha, pan, zoom, seleção) | done | 2026-10-12 | developer | high | 2026-10-12 |  | etapa-0/E0-03 | [E1-01](../specs/etapa-1/e1-01-spec.md) |
| E1-02 | Símbolos SVG IEC: fonte DC, resistência, interruptor, lâmpada e terra | backlog | 2026-10-12 | developer | high |  |  | etapa-0/E0-08 |  |
| E1-03 | Paleta de componentes com drag-and-drop, snap-to-grid e rotação | backlog | 2026-10-12 | developer | high |  |  | E1-02 |  |
| E1-04 | Ligações entre pinos, fios ortogonais e junções explícitas | done | 2026-10-12 | developer | critical | 2026-10-13 |  | E1-01 | [E1-04](../specs/etapa-1/e1-04-spec.md) |
| E1-05 | Painel de propriedades com validação imediata | backlog | 2026-10-12 | developer | medium |  |  | E1-02 |  |
| E1-06 | Undo/redo, copiar/colar e apagar | backlog | 2026-10-12 | developer | medium |  |  | E1-04 |  |
| E1-07 | Importar/exportar projeto em JSON canónico | backlog | 2026-10-12 | developer | high |  |  | etapa-0/E0-07, E1-04 |  |
| E1-08 | Prototipar circuitos ramificados para validar React Flow | backlog | 2026-10-12 | developer | high |  |  | E1-01 |  |
<!-- /maestru:work-items-list -->
