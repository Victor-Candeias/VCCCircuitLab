---
maestru: "0.4"
type: work-spec
id: e2-07-spec
title: "E2-07 — Plano do cliente API e resultados no editor"
template: implementation-plan-v1
work-item: etapa-2/E2-07
owner: developer
created: 2026-10-14
---

# E2-07 — Plano do cliente API e resultados no editor

## Overview

Ligar o editor (`apps/web`) à API de simulação (E2-05): cliente em `src/api` configurado por `VITE_API_BASE_URL`, botão **Simular**, resultados por componente (tensão, corrente, potência) e por rede, destaque de redes no canvas, avisos e erros (§5.1, §8). Sem alterações à API nem ao schema.

Decisões:

- **URL da API**: `VITE_API_BASE_URL` (sem `/` final; §13). Vazia por omissão → pedidos para a mesma origem (`/api/v1/...`), e o `vite dev`/`vite preview` encaminham `/api` para `API_PROXY_TARGET` (omissão `http://127.0.0.1:8000`). Assim o FE aberto noutra máquina da rede funciona sem expor o backend nem configurar CORS; o CORS restrito ao domínio do frontend fica para o E5-04 (produção com API noutra origem).
- **Cliente** (`client.ts`): `fetch` com `POST` do documento canónico (`toCanonical`, sem `nets`), `Accept: application/json, application/problem+json`, timeout de 15 s e cancelamento por `AbortSignal`. Todas as falhas viram `ApiError` com `kind` (`problem`, `http`, `network`, `timeout`, `aborted`, `invalid-response`) e, nos erros da API, o `Problem` (RFC 9457) com a lista `errors`. Verificação mínima da forma das respostas 200. `validateCircuit` também fica disponível (E1-05/E3 poderão usá-lo).
- **Estado** num store próprio (`simulationStore`), separado do editor: `idle | running | success | error`, sempre com a referência do documento simulado. Os resultados só se mostram se `simulation.circuit === circuit` (documentos imutáveis): qualquer alteração invalida-os e desfazer até ao mesmo documento volta a mostrá-los, sem lógica de invalidação explícita. Um novo pedido cancela o anterior e respostas atrasadas são ignoradas.
- **Redes com os IDs da API**: `deriveConnectivity` (E1-08) já dá as redes pela ordem do normalizador; `netIds` replica a geração `N1…` (saltando IDs usados no documento). Assim `nodeVoltagesV` e os `refs` dos erros (`N3`) mapeiam diretamente para fios, junções e terminais, sem pedir `/validate`.
- **Apresentação**: painel lateral direito com tabela por componente (a terra não tem resultado) e tabela de redes (tensão + terminais); prefixos SI com 3 algarismos significativos e vírgula decimal (`Intl.NumberFormat('pt-PT')`); nota sobre a convenção passiva. Clicar num componente seleciona-o; clicar numa rede destaca-a (cor própria `--net`, distinta da seleção) — fios, junções e pinos.
- **Erros e avisos**: avisos (`role=status`) acima dos resultados; erros (`role=alert`) com título do problema, mensagem e código de cada erro e botão **Mostrar**, que seleciona os elementos citados (terminais → componente) e destaca a primeira rede citada. Falhas de rede indicam a URL e sugerem verificar o servidor.

## Implementation

1. `src/api/types.ts` e `src/api/client.ts`: tipos do contrato, `ApiError`, `simulateCircuit`, `validateCircuit`, `normalizeBaseUrl`, `toApiError`.
2. `src/editor/connectivity.ts`: `netIds`. `src/simulation/nets.ts`: `circuitNets` (cache por documento) e `netHighlight`.
3. `src/simulation/simulationStore.ts`: `simulate`, `setHighlightedNet`, `reset`, `isCurrent`.
4. `src/simulation/format.ts`: `formatQuantity`.
5. `src/simulation/SimulationPanel.tsx` + `simulation.css`: painel; `src/editor/EditorCanvas.tsx` inclui o painel e passa o destaque a `toFlowNodes`/`toJunctionNodes`/`toFlowEdges` (`flowNodes.ts`, `ComponentNodeView.tsx`, `editor.css`); cores `--net`, `--net-bg`, `--warning` em `index.css`.
6. `vite.config.ts`: `server.proxy`/`preview.proxy` de `/api`; `apps/web/.env.example`.
7. Testes: `client.test.ts` (POST canónico sem `nets`, URL base, problem+json, HTTP, resposta inesperada, rede, timeout, cancelamento), `nets.test.ts`, `format.test.ts`, `simulationStore.test.ts` (estados, erro, cancelamento de pedido anterior, reset) e `SimulationPanel.test.tsx` (resultados reais da API para o exemplo paralelo, destaque de rede no canvas, seleção a partir da tabela, invalidação e undo, erros com Mostrar, falha de rede, circuito vazio).
8. `apps/web/README.md`: estrutura e secção "Simulação (API)".

Verificação: `pnpm --filter @vcccircuitlab/web test` (199 testes), `lint`, `build`, `pnpm format:check`; teste manual no browser com a API real através do proxy do `vite dev` (exemplo ramificado: 7 componentes, 4 redes, destaque de N2; circuito sem terra → erro `MISSING_GROUND`).

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/api/types.ts` | create | Tipos do contrato da API |
| `apps/web/src/api/client.ts` | create | Cliente HTTP, erros e timeout |
| `apps/web/src/api/client.test.ts` | create | Testes do cliente |
| `apps/web/src/simulation/simulationStore.ts` | create | Estado da simulação |
| `apps/web/src/simulation/simulationStore.test.ts` | create | Testes do estado |
| `apps/web/src/simulation/nets.ts` | create | Redes com IDs da API e destaque |
| `apps/web/src/simulation/nets.test.ts` | create | Testes das redes |
| `apps/web/src/simulation/format.ts` | create | Formatação SI |
| `apps/web/src/simulation/format.test.ts` | create | Testes da formatação |
| `apps/web/src/simulation/SimulationPanel.tsx` | create | Painel de resultados |
| `apps/web/src/simulation/SimulationPanel.test.tsx` | create | Testes de integração |
| `apps/web/src/simulation/simulation.css` | create | Estilos do painel |
| `apps/web/src/editor/connectivity.ts` | modify | `netIds` |
| `apps/web/src/editor/flowNodes.ts` | modify | Destaque de rede em nós e arestas |
| `apps/web/src/editor/ComponentNodeView.tsx` | modify | Pinos destacados |
| `apps/web/src/editor/EditorCanvas.tsx` | modify | Painel e destaque |
| `apps/web/src/editor/editor.css` | modify | Estilos do destaque |
| `apps/web/src/index.css` | modify | Cores `--net`, `--warning` |
| `apps/web/vite.config.ts` | modify | Proxy `/api` |
| `apps/web/.env.example` | create | `VITE_API_BASE_URL` |
| `apps/web/README.md` | modify | Documentação |
