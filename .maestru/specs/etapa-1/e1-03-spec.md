---
maestru: "0.4"
type: work-spec
id: e1-03-spec
title: "E1-03 — Plano da paleta de componentes"
template: implementation-plan-v1
work-item: etapa-1/E1-03
owner: developer
created: 2026-10-14
---

# E1-03 — Plano da paleta de componentes

## Overview

Paleta de componentes do editor (`apps/web`, §5.1): pesquisável, agrupada por categorias do catálogo, com arrastar para o canvas, snap-to-grid na colocação e rotação de componentes. Mover já existia (E1-01, com snap na âncora). Sem alterações ao schema nem ao catálogo.

Decisões:

- **Paleta** (`ComponentPalette`, à esquerda do canvas, dentro do `ReactFlowProvider`): grupos pela ordem de `ComponentCategory` (Fontes, Passivos, Interruptores, Cargas, Referência), cada item com o símbolo IEC (`ComponentSymbol`, E1-02) e o nome. Pesquisa sem maiúsculas nem acentos; todas as palavras têm de ocorrer em nome, tipo, `idPrefix`, descrição ou categoria; grupos vazios omitidos.
- **Arrastar** com HTML5 drag-and-drop (MIME `application/x-vcccircuitlab-component`); o `dragover` só aceita esse tipo. Os itens são `div role="button"` (o Firefox não arrasta `<button>`). Alternativa acessível: clique/Enter adiciona no centro da vista.
- **Colocação** (`placement.ts`): nova instância com rotação 0, propriedades por omissão e pinos do catálogo, ID `<idPrefix><n>` único no documento (`nextElementId`). A âncora é encaixada na grelha; se já houver um componente com a mesma âncora, desloca-se uma célula na diagonal (evita sobreposição total ao clicar várias vezes). Coordenadas não finitas são recusadas. O novo componente fica selecionado.
- **Rotação**: `R` = 90° horário, `Shift+R` = anti-horário, e botões ⟲/⟳ num `Panel` (ativos só com componentes selecionados). Cada componente selecionado roda em torno da própria âncora; como os pinos do catálogo são múltiplos da grelha, continuam na grelha. Os fios são redesenhados pelo traçado ortogonal existente. Atalhos ignorados com Ctrl/⌘/Alt, repetição ou foco em campos de texto.

## Implementation

1. `src/editor/placement.ts`: `rotateBy`, `defaultProperties`, `freeAnchor`, `placeComponent`, `rotateComponents`.
2. `src/editor/palette.ts`: `PALETTE_DRAG_TYPE`, `CATEGORY_LABELS`, `paletteGroups(query)`.
3. `src/store/editorStore.ts`: `addComponent(type, anchor)` e `rotateSelection(step)`.
4. `src/editor/ComponentPalette.tsx`: pesquisa, grupos, itens arrastáveis, clique/Enter no centro da vista.
5. `src/editor/EditorCanvas.tsx`: layout paleta + canvas, `onDragOver`/`onDrop`, atalhos `R`/`Shift+R`, `RotateToolbar`.
6. `src/editor/editor.css`: layout, paleta e barra de rotação (temas claro/escuro).
7. Testes (Vitest): `placement.test.ts`, `palette.test.ts`, `editorStore.test.ts` (paleta e rotação) e `EditorCanvas.test.tsx` (grupos, pesquisa, dragstart, drop com snap e seleção, drop externo ignorado, clique/Enter, `R`/`Shift+R`, `R` na pesquisa, botões).
8. `apps/web/README.md`: estrutura e secção "Paleta e rotação".

Verificação: `pnpm --filter @vcccircuitlab/web test` (103 testes), `lint`, `build`, `pnpm format:check`; no browser (`vite preview` + Chromium headless com `playwright-core`): arrastar resistência e interruptor para o canvas (âncoras na grelha), `R`/`Shift+R`, fio entre componentes novos, dois cliques em "Terra" (GND2/GND3 deslocados), pesquisa, temas claro/escuro, sem erros na consola.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/editor/placement.ts` | create | Colocação e rotação de componentes |
| `apps/web/src/editor/placement.test.ts` | create | Testes da colocação e rotação |
| `apps/web/src/editor/palette.ts` | create | Agrupamento e pesquisa do catálogo |
| `apps/web/src/editor/palette.test.ts` | create | Testes da paleta |
| `apps/web/src/editor/ComponentPalette.tsx` | create | UI da paleta |
| `apps/web/src/editor/EditorCanvas.tsx` | modify | Drop, atalhos de rotação, barra, layout |
| `apps/web/src/editor/EditorCanvas.test.tsx` | modify | Testes de paleta, drop e rotação |
| `apps/web/src/editor/editor.css` | modify | Estilos da paleta e da barra |
| `apps/web/src/store/editorStore.ts` | modify | `addComponent`, `rotateSelection` |
| `apps/web/src/store/editorStore.test.ts` | modify | Testes das novas ações |
| `apps/web/README.md` | modify | Documentação da paleta e rotação |
