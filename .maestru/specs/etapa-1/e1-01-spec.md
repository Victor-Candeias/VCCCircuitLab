---
maestru: "0.4"
type: work-spec
id: e1-01-spec
title: "E1-01 — Plano do canvas do editor"
template: implementation-plan-v1
work-item: etapa-1/E1-01
owner: developer
created: 2026-10-12
---

# E1-01 — Plano do canvas do editor

## Overview

Canvas do editor em `apps/web/src/editor` com `@xyflow/react` (React Flow 12): grelha, pan, zoom e seleção simples/múltipla. Estado em Zustand com o documento canónico (`CircuitDocument` de `@vcccircuitlab/circuit-schema`) separado do estado de vista (seleção) — §2, §5.1.

Decisões:

- **Nós derivados do documento**: o store guarda só o `CircuitDocument` e `selectedIds`; os nós do React Flow são calculados (`toFlowNodes`) e as `NodeChange` (posição, seleção) são traduzidas em ações do store. Não há uma segunda cópia do estado em formato React Flow.
- **Âncora = centro do símbolo**: `Component.position` é o centro; o React Flow posiciona pelo canto superior esquerdo, por isso há conversão em `geometry.ts`. O tamanho vem do catálogo (E0-08) e troca largura/altura a 90°/270°. Os nós têm `width`/`height` fixos (não dependem de medição DOM).
- **Snap no store** (não o `snapToGrid` do React Flow): o React Flow encaixaria o canto superior esquerdo, e a resistência (80×20) ficaria com os pinos fora da grelha. O snap é aplicado à âncora.
- Interação: pan ao arrastar o fundo, zoom 0,25–4, clique seleciona, Ctrl/⌘ + clique acrescenta, Shift + arrastar seleciona por caixa. Ligações e apagar ficam desativados (E1-04, E1-06).
- Nós provisórios (caixa com o ID); os símbolos IEC chegam no E1-02. Tipos fora do catálogo são desenhados com contorno tracejado de erro.
- Circuito de demonstração (V1, R1, H1, GND1) até existir importação (E1-07). Os fios ainda não são desenhados (E1-04).
- `colorMode="system"` e cores próprias da grelha para tema claro/escuro.

## Implementation

1. Dependências: `@xyflow/react`, `zustand`, `@vcccircuitlab/circuit-schema` (`workspace:*`); `resolveJsonModule` para importar o catálogo.
2. `src/editor/geometry.ts`, `catalog.ts`, `demoCircuit.ts`, `flowNodes.ts`, `ComponentNodeView.tsx`, `EditorCanvas.tsx`, `editor.css`.
3. `src/store/editorStore.ts`: `circuit`, `selectedIds`, `loadCircuit`, `moveComponent` (com snap), `setSelection`.
4. `App.tsx` passa a mostrar o editor; removidos os ficheiros do template Vite (`App.css`, `src/assets/*`, `public/icons.svg`); `index.css` reescrito.
5. Testes (Vitest): geometria, `toFlowNodes`, store e `EditorCanvas` (render, clique, Ctrl + clique, seleção refletida). Mocks de `ResizeObserver`/`DOMMatrixReadOnly`/dimensões para o React Flow em jsdom; os cliques usam `createEvent` com `view` definido porque o d3-drag lê `event.view.document`.

Verificação: `pnpm test` (19 testes web + 43 schema), `pnpm lint`, `pnpm build`, `pnpm format:check` e verificação visual com `vite preview` + Edge headless.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/package.json`, `pnpm-lock.yaml` | modify | Dependências do editor |
| `apps/web/tsconfig.app.json` | modify | `resolveJsonModule` |
| `apps/web/src/editor/*` | create | Canvas, geometria, catálogo, nós, demo |
| `apps/web/src/store/editorStore.ts` | create | Estado Zustand |
| `apps/web/src/App.tsx`, `apps/web/src/index.css` | modify | Layout com o editor |
| `apps/web/src/App.css`, `apps/web/src/assets/*`, `apps/web/public/icons.svg` | delete | Restos do template Vite |
| `apps/web/src/test/reactFlowMocks.ts`, `apps/web/src/test/setup.ts` | create/modify | Mocks do React Flow em jsdom |
| `apps/web/src/**/*.test.ts(x)` | create/modify | Testes |
| `apps/web/README.md` | modify | Estrutura e comportamento do editor |
