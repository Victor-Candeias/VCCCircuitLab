---
maestru: "0.4"
type: work-spec
id: e1-04-spec
title: "E1-04 — Plano de ligações, fios ortogonais e junções"
template: implementation-plan-v1
work-item: etapa-1/E1-04
owner: developer
created: 2026-10-13
---

# E1-04 — Plano de ligações, fios ortogonais e junções

## Overview

Ferramenta de fio pino-a-pino no canvas (`apps/web/src/editor`), com waypoints ortogonais e junções explícitas, sobre o modelo `wires` + `junctions` do `CircuitDocument` (§3.1, §5.1, §5.2). Sem alterações ao schema.

Decisões:

- **Ferramenta por cliques, sem modo explícito**: clique num terminal, junção ou fio começa um fio; cliques no fundo fixam waypoints; clique noutro terminal, junção ou fio termina. `Esc`/botão direito no fundo cancela; `Backspace` remove o último waypoint. O rascunho (`wireDraft`) é estado de vista no store, nunca gravado no documento.
- **Ortogonalidade**: cada waypoint é encaixado na grelha e ligado ao anterior com um canto horizontal-primeiro (`routeTo`); pontos repetidos e colineares são removidos (`simplifyPath`). Ao desenhar, troços que fiquem diagonais (componente movido) recebem um canto (`orthogonalize`) sem alterar o documento.
- **Junções explícitas**: só se cria uma junção quando um fio começa ou termina _sobre_ outro fio (clique na aresta). O ponto é projetado no troço mais próximo e encaixado na grelha; o fio é dividido em dois (`W` original → `J`, novo `W` → extremidade original) e a junção `J<n>` é criada. Se o ponto coincidir com uma extremidade do fio, liga-se a essa extremidade sem nova junção. A divisão só acontece quando o fio é confirmado (cancelar não altera nada).
- **Cruzamentos não ligam**: cliques no fundo nunca criam ligações; a conectividade vem só das extremidades dos fios.
- **React Flow**: pinos são `Handle`s (um por pino, posicionados pela rotação do catálogo, `isConnectable=false`, `onClick` próprio); junções são nós `junction` (arrastáveis com snap); fios são arestas `wire` cujo traçado vem de `data.points` (calculado do documento), não das posições dos handles. `ConnectionMode.Loose` porque todos os handles são `source`. A ligação nativa do React Flow (arrastar/`connectOnClick`) fica desligada.
- **IDs**: `nextElementId` gera `W<n>`/`J<n>` únicos em todo o documento (componentes, junções, fios, redes).
- Ligações inválidas (extremidade a si própria, fio a si próprio, âncoras inexistentes) são ignoradas e o rascunho mantém-se. Apagar fios/junções fica para o E1-06.

## Implementation

1. `src/editor/wiring.ts` (lógica pura): `rotateOffset`, `pinOffset`, `terminalPosition`, `endpointPosition`, `anchorPosition`, `simplifyPath`, `routeTo`, `orthogonalize`, `wirePath`, `pathToSvg`, `nearestPointOnPath`, `nextElementId`, `draftWaypoints`, `commitWire` (divide fios e cria junções).
2. `src/store/editorStore.ts`: `wireDraft`, `startWire`, `addWireWaypoint`, `removeLastWireWaypoint`, `finishWire`, `cancelWire`, `clickWireAnchor`, `moveJunction`; `setSelection` aceita junções; `loadCircuit` cancela o rascunho.
3. `src/editor/flowNodes.ts`: pinos relativos ao nó (`data.pins`), `toJunctionNodes`, `toFlowEdges`.
4. `ComponentNodeView.tsx` (handles clicáveis), `JunctionNodeView.tsx`, `WireEdgeView.tsx`; `EditorCanvas.tsx` com `ReactFlowProvider`, `screenToFlowPosition`, cliques em nós/arestas/fundo, teclado e pré-visualização (`ViewportPortal`).
5. CSS: pinos, fios, junções, pré-visualização tracejada; variável `--wire` (tema claro/escuro).
6. Testes (Vitest): `wiring.test.ts` (rotação, traçado, projeção, IDs, divisão de fios, cruzamento sem junção, imutabilidade), store (ferramenta de fio, junções), `flowNodes` (pinos, junções, arestas) e `EditorCanvas` (fios desenhados, terminal → terminal, `Esc`, junção).

Verificação: `pnpm test` (53 testes web + 43 schema), `pnpm lint`, `pnpm build`, `pnpm format:check`, e verificação no browser (`vite preview` + Edge headless com `playwright-core`): fio terminal → fio cria J1 e divide W2; fio que cruza W2 e W3 não cria junção e não altera os fios existentes; `Esc` cancela; mover R1 mantém todos os troços ortogonais; sem erros na consola.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/editor/wiring.ts` | create | Geometria de pinos/fios, criação de fios e junções |
| `apps/web/src/editor/JunctionNodeView.tsx`, `WireEdgeView.tsx` | create | Nó de junção e aresta de fio |
| `apps/web/src/editor/flowNodes.ts` | modify | Pinos, nós de junção e arestas |
| `apps/web/src/editor/ComponentNodeView.tsx` | modify | Pinos clicáveis |
| `apps/web/src/editor/EditorCanvas.tsx` | modify | Ferramenta de fio e pré-visualização |
| `apps/web/src/store/editorStore.ts` | modify | Rascunho de fio, junções |
| `apps/web/src/editor/editor.css`, `apps/web/src/index.css` | modify | Estilos de pinos, fios e junções |
| `apps/web/src/**/*.test.ts(x)` | create/modify | Testes |
| `apps/web/README.md` | modify | Utilização da ferramenta de fio |
