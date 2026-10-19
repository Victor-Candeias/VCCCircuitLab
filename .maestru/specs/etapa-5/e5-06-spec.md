---
maestru: "0.4"
type: work-spec
id: e5-06-spec
title: "E5-06 — Testes em desktop, tablet e browsers principais"
template: implementation-plan-v1
work-item: etapa-5/E5-06
owner: developer
created: 2026-10-19
---

# E5-06 — Testes em desktop, tablet e browsers principais

## Overview

Validar o site com os exemplos em desktop (Chromium, Firefox, WebKit/Safari) e tablet (iPad e
Android, com toque), de forma automática e repetível: projetos Playwright por browser/dispositivo,
um cenário que abre e simula cada exemplo, um workflow de CI que os corre contra a API real
(com MongoDB) e a possibilidade de correr o mesmo cenário contra o site publicado. A validação
em dispositivos físicos fica numa checklist manual (notas do work-item).

## Implementation

### Phase 1: Dados de teste da API

| Action | File | Details |
|---|---|---|
| Create | `apps/api/app/component_templates/seed.py` | `python -m app.component_templates.seed <catalog.json>`: insere na coleção `templates` os componentes de um catálogo (`{components: [...]}`) cujo `type` ainda não exista (idempotente, `createdBy: "seed"`). Resolve também a instalação nova sem templates. |
| Create | `apps/api/tests/test_component_templates_seed.py` | Inserção, idempotência e ficheiro inválido. |

### Phase 2: Matriz Playwright e cenário dos exemplos

| Action | File | Details |
|---|---|---|
| Modify | `apps/web/playwright.config.ts` | Projetos `chromium` (todos os testes), `firefox`, `webkit`, `tablet-ipad` (iPad gen 7 landscape, WebKit, toque) e `tablet-android` (Galaxy Tab S4, Chromium, toque); os novos só correm `examples.spec.ts`. `PLAYWRIGHT_BASE_URL` (site publicado) dispensa os `webServer`. |
| Modify | `apps/web/e2e/auth.ts` | `PLAYWRIGHT_API_URL` para a API noutra origem; `E2E_EMAIL`/`E2E_PASSWORD` para usar uma conta existente. |
| Create | `apps/web/e2e/examples.spec.ts` | Para cada exemplo: abrir, sem scroll horizontal, barra de ações visível, simular e ver resultados sem erros. Em dispositivos com toque, adicionar um componente com *tap* na paleta. |

### Phase 3: Layout e CI

| Action | File | Details |
|---|---|---|
| Modify | `apps/web/src/index.css`, `src/project/project.css`, `src/editor/editor.css`, `src/editor/properties.css` | Cabeçalho e menu do projeto com `flex-wrap`; painéis laterais mais estreitos abaixo de 1100 px (tablet). |
| Create | `.github/workflows/e2e.yml` | MongoDB como serviço, venv da API, seed dos templates, `playwright install --with-deps` e `pnpm --filter ./apps/web test:e2e` (todos os projetos); relatório em artefacto quando falha. |
| Modify | `apps/web/README.md` | Projetos, variáveis e como correr contra o site publicado. |

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/component_templates/seed.py` | Create | Seed idempotente dos templates |
| `apps/api/tests/test_component_templates_seed.py` | Create | Testes do seed |
| `apps/web/playwright.config.ts` | Modify | Matriz de browsers/dispositivos |
| `apps/web/e2e/auth.ts` | Modify | API/conta configuráveis |
| `apps/web/e2e/examples.spec.ts` | Create | Cenário dos exemplos |
| `apps/web/src/*.css` | Modify | Layout em tablet |
| `.github/workflows/e2e.yml` | Create | CI E2E |
| `apps/web/README.md`, `apps/api/README.md` | Modify | Documentação |
