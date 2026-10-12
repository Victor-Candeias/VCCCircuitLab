---
maestru: "0.4"
type: work-spec
id: e0-02-spec
title: "E0-02 — Plano de README, licença e ADRs"
template: implementation-plan-v1
work-item: etapa-0/E0-02
owner: developer
created: 2026-10-12
---

# E0-02 — Plano de README, licença e ADRs

## Overview

Atualizar o README raiz com instalação e desenvolvimento, escolher a licença open source e registar como ADRs as decisões da `Docs/arquitetura_simulador_circuitos.md` §15.

## Implementation

### Fase 1 — Licença

1. Licença **MIT** (`LICENSE`), verificada a compatibilidade das dependências (`pnpm licenses list -r`: MIT, ISC, BSD, Apache-2.0, MPL-2.0 em tooling; backend MIT/BSD-3-Clause).

### Fase 2 — ADRs

1. `Docs/adr/README.md` com índice e modelo de ADR.
2. ADRs 0001–0007, um por decisão da §15: âmbito DC baixa tensão, simbologia IEC, editor simples, backend Python obrigatório, open source + MIT, nome/estrutura monorepo, pnpm via Corepack.
3. Referência aos ADRs no fim da §15 do documento de arquitetura.

### Fase 3 — README

1. README raiz com descrição, aviso de segurança, estrutura, pré-requisitos, instalação (frontend e backend), comandos de desenvolvimento, ligações para READMEs dos pacotes, documentação e licença.

### Verificação

- Todas as ligações do README e do índice de ADRs apontam para ficheiros existentes.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `LICENSE` | create | Licença MIT |
| `README.md` | update | Instalação e desenvolvimento |
| `Docs/adr/README.md` | create | Índice e modelo de ADR |
| `Docs/adr/0001…0007-*.md` | create | ADRs das decisões da §15 |
| `Docs/arquitetura_simulador_circuitos.md` | update | Referência aos ADRs |
