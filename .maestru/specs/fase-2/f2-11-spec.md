---
maestru: "0.4"
type: work-spec
id: f2-11-spec
title: "Catálogo de componentes do frontend a partir da API"
template: implementation-plan-v1
work-item: fase-2/F2-11
owner: developer
created: 2026-10-15
---

# Catálogo de componentes do frontend a partir da API

## Overview

O backend (F2-10) já lê o catálogo de componentes do MongoDB (coleção `templates`, via
`GET /api/v1/components`) e `apps/api/app/circuit/data/components.json` foi removido. O
frontend (`apps/web`) ainda importa estaticamente, em build-time, o segundo ficheiro
(`packages/circuit-schema/catalog/components.json`) via
`apps/web/src/editor/catalog.ts: import catalogJson from '@vcccircuitlab/circuit-schema/catalog.json'`.
Este work-item fecha a lacuna: o frontend passa a carregar o catálogo de `GET /api/v1/components`
em tempo de execução, e o ficheiro estático do pacote `circuit-schema` é apagado.

## Validação feita (análise de impacto)

Investigação confirmada por `grep`/leitura direta dos ficheiros (não há suposições por validar):

- **Só 1 ficheiro lê o JSON diretamente:** `apps/web/src/editor/catalog.ts` (`catalogJson`,
  `export const catalog`, `GRID_SIZE`, `UNKNOWN_COMPONENT_SIZE`, `getComponentDefinition`).
- **13 ficheiros consomem o módulo `./catalog`** (import de `catalog`/`GRID_SIZE`/
  `getComponentDefinition`/`UNKNOWN_COMPONENT_SIZE`), todos de forma **síncrona**, embebida em
  funções puras ou em render de componentes — nenhum é `async`/usa `Suspense` atualmente:
  `editor/editing.ts`, `editor/EditorCanvas.tsx`, `editor/flowNodes.ts`, `editor/palette.ts`
  (+ `editor/palette.test.ts`), `editor/placement.ts` (+ `editor/placement.test.ts`),
  `editor/PropertiesPanel.tsx`, `editor/wiring.ts`, `project/circuitJson.ts`,
  `project/examples.test.ts`, `simulation/SimulationPanel.tsx`, `store/editorStore.ts`,
  `components/symbols/ComponentSymbol.test.tsx`.
- Muitos outros ficheiros que apareceram numa pesquisa inicial mais larga (`ComponentSymbol.tsx`,
  `iecSymbols.tsx`, `ComponentPalette.tsx`, `demoCircuit.ts`, etc.) **só importam tipos** do
  pacote `@vcccircuitlab/circuit-schema` (`ComponentDefinition`, `CircuitDocument`, …), não o
  `catalog.json` — não são afetados por apagar o ficheiro.
- **Abordagem escolhida (menor risco):** não reescrever os 13 consumidores para `async`.
  `editor/catalog.ts` passa a expor um *singleton populado em runtime*: a app faz
  `GET /api/v1/components` uma vez, no arranque (antes de montar `EditorCanvas`), e só depois
  disso é que `catalog`/`GRID_SIZE`/`getComponentDefinition` ficam disponíveis — exatamente como
  hoje, só que a origem dos dados deixa de ser um import estático. Os 13 ficheiros **não
  precisam de nenhuma alteração**.
- **Alternativa rejeitada:** tornar todos os consumidores `async`/com `Suspense` — maior
  diff, maior risco de regressão em lógica pura de geometria/wiring, sem benefício adicional
  (a app já tem de esperar pela sessão/autenticação antes de mostrar o editor, ver `App.tsx`).

## Implementation

### Phase 1: Catálogo carregado da API no arranque

#### Step 1.1: Expor o catálogo como singleton populável

| Action | File | Details |
|---|---|---|
| Modify | `apps/web/src/editor/catalog.ts` | Remover `import catalogJson from '@vcccircuitlab/circuit-schema/catalog.json'`. Adicionar `let state: ComponentCatalog \| null = null` e `export async function loadCatalog(): Promise<void>` que chama `GET /api/v1/components` (novo cliente em `api/client.ts`) e preenche `state`. `catalog`/`GRID_SIZE`/`UNKNOWN_COMPONENT_SIZE`/`getComponentDefinition` passam a ler de `state`, lançando um erro claro (`"Catálogo não carregado"`) se chamados antes de `loadCatalog()` resolver — garante falha rápida em vez de `undefined` silencioso. |
| Modify | `apps/web/src/api/client.ts` | Adicionar `getComponents(options?: RequestOptions): Promise<ComponentCatalogResponse>` (`GET /api/v1/components`), com o `isExpected` a validar o formato (`catalogVersion`, `gridSize`, `components[]`), seguindo o padrão de `simulateCircuit`/`validateCircuit`. |

#### Step 1.2: Esperar pelo catálogo antes de montar o editor

| Action | File | Details |
|---|---|---|
| Modify | `apps/web/src/App.tsx` | Depois de `restore()` da sessão (`status !== 'checking'`) e antes de montar `<EditorCanvas />`, chamar `loadCatalog()` uma vez (`useEffect` + estado `catalog-loading \| catalog-ready \| catalog-error`), mostrando um ecrã de carregamento/erro equivalente ao de `"A validar a sessão…"` já existente, para manter o mesmo padrão visual. |

#### Step 1.3: Testes

| Action | File | Details |
|---|---|---|
| Modify | `apps/web/src/editor/catalog.ts`-related tests (`palette.test.ts`, `placement.test.ts`, `examples.test.ts`, `ComponentSymbol.test.tsx`) | Adicionar um `beforeAll`/helper partilhado que popula o singleton com dados de teste fixos (mesmos 6 componentes), via `loadCatalog`'s ponto de injeção de teste ou um `setCatalogForTests()` exportado só em modo de teste — evita cada teste depender de `fetch`/MSW. |
| Create | `apps/web/src/editor/catalog.test.ts` (novo) | Testa `loadCatalog()` (sucesso/erro) e o comportamento de "não carregado" de `getComponentDefinition`/`GRID_SIZE`. |

Checklist da Fase 1:
- [ ] `pnpm --filter @vcccircuitlab/web test` passa
- [ ] `pnpm --filter @vcccircuitlab/web typecheck` passa
- [ ] Arranque manual (`./start.sh`) mostra o editor com o catálogo vindo da API (sem o ficheiro estático)

### Phase 2: Remover o ficheiro estático e limpar o pacote `circuit-schema`

#### Step 2.1: Apagar o ficheiro e atualizar o pacote

| Action | File | Details |
|---|---|---|
| Delete | `packages/circuit-schema/catalog/components.json` | Só depois da Fase 1 verificada — é o ficheiro cujo fim é o objetivo deste work-item. |
| Modify | `packages/circuit-schema/package.json` | Remover o export `"./catalog.json": "./catalog/components.json"`. |
| Modify | `packages/circuit-schema/test/catalog.test.mjs` | Este teste valida o JSON contra `catalog.schema.json` (schema Ajv) e as fixtures de circuito contra o catálogo — sem ficheiro, tem de deixar de ler `../catalog/components.json`. Duas opções: (a) remover o teste (o schema de catálogo deixa de ter uma instância de referência no repo) ou (b) substituir a leitura do ficheiro por um pedido à API local/fixture JSON de teste equivalente. Decidir ao implementar, documentando a escolha no commit. |
| Modify | `packages/circuit-schema/package.json` (scripts) | Confirmar que `"test": "node --test && tsc --noEmit"` continua válido depois da alteração ao `catalog.test.mjs`. |

Checklist da Fase 2:
- [ ] `pnpm --filter @vcccircuitlab/circuit-schema test` passa
- [ ] `git grep -n "catalog.json\|catalog/components.json"` não devolve mais nenhuma referência de produção (só, no máximo, este work-item/spec)
- [ ] `maestru check` sem erros

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/editor/catalog.ts` | Modify | Deixa de importar o JSON estático; expõe `loadCatalog()` e um singleton populado em runtime a partir da API |
| `apps/web/src/api/client.ts` | Modify | Novo `getComponents()` (`GET /api/v1/components`) |
| `apps/web/src/App.tsx` | Modify | Aguarda `loadCatalog()` antes de montar `EditorCanvas` |
| `apps/web/src/editor/catalog.test.ts` | Create | Testes do novo `loadCatalog()`/singleton |
| `apps/web/src/editor/palette.test.ts` | Modify | Popular o catálogo de teste antes dos testes |
| `apps/web/src/editor/placement.test.ts` | Modify | Popular o catálogo de teste antes dos testes |
| `apps/web/src/project/examples.test.ts` | Modify | Popular o catálogo de teste antes dos testes |
| `apps/web/src/components/symbols/ComponentSymbol.test.tsx` | Modify | Popular o catálogo de teste antes dos testes |
| `packages/circuit-schema/catalog/components.json` | Delete | Objetivo final deste work-item |
| `packages/circuit-schema/package.json` | Modify | Remover o export `./catalog.json` |
| `packages/circuit-schema/test/catalog.test.mjs` | Modify | Deixa de ler o ficheiro apagado (remover ou substituir por fixture de teste) |
