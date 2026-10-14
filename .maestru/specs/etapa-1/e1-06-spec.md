---
maestru: "0.4"
type: work-spec
id: e1-06-spec
title: "E1-06 — Plano de undo/redo, copiar/colar e apagar"
template: implementation-plan-v1
work-item: etapa-1/E1-06
owner: developer
created: 2026-10-14
---

# E1-06 — Plano de undo/redo, copiar/colar e apagar

## Overview

Histórico de ações no store Zustand, apagar componentes/junções/fios e copiar/cortar/colar com novos IDs estáveis (§5.1). Só frontend; sem alterações ao schema nem à API.

Decisões:

- **Histórico de snapshots** do documento canónico (imutável, partilha estrutural): `past`/`future` no store, limite de 100 passos (`HISTORY_LIMIT`). Mais simples e robusto do que comandos inversos; a memória é pequena porque só os objetos alterados são novos. Só o documento entra no histórico — seleção, fio em desenho e área de transferência não.
- **Uma função `record`** usada por todas as ações que alteram o documento (adicionar, mover, mover junção, rodar, terminar fio, apagar, colar); não regista quando o documento não muda e uma alteração nova limpa `future`.
- **Gestos agrupados**: `beginHistoryGroup`/`endHistoryGroup` ligados a `onNodeDragStart/Stop` e `onSelectionDragStart/Stop` do React Flow — um arrasto (com muitos `moveComponent`) é um só passo; um gesto sem alterações não regista nada. Undo/redo são ignorados durante o gesto.
- **Undo/redo mantêm só a seleção que ainda existe** e cancelam o fio em desenho; `loadCircuit` (abrir/novo/exemplo) limpa o histórico.
- **Apagar não deixa fios soltos**: os fios ligados a um componente ou junção apagados desaparecem, tal como as junções que deixam de ter fios por causa do apagamento (`deleteElements`, função pura em `editing.ts`).
- **Fios selecionáveis com Alt + clique** (o clique simples num fio continua a iniciar/terminar ligações, E1-04). A seleção de fios fica no store (`selectedIds` aceita `W<n>`); o fio selecionado é desenhado com a cor de destaque. Clique no fundo ou num nó (sem Ctrl) limpa os fios selecionados.
- **Copiar** guarda um fragmento (componentes e junções selecionados + fios com as duas extremidades no fragmento) numa área de transferência interna (não no clipboard do sistema). **Colar** gera IDs com `nextElementId` (prefixo do catálogo, `J`, `W`), religa as extremidades, desloca posições e pontos intermédios `n × 40 px` na diagonal e seleciona os elementos colados. **Cortar** = copiar + apagar, e a primeira colagem fica no mesmo sítio (os IDs livres podem ser reaproveitados).
- **Atalhos**: `Delete`/`Backspace` (Backspace não apaga durante o desenho de um fio — remove o último ponto), `Ctrl/⌘+Z`, `Ctrl/⌘+Y`, `Ctrl/⌘+Shift+Z`, `Ctrl/⌘+C/X/V`; ignorados em campos editáveis; Ctrl+C/X não interferem quando há texto selecionado na página. `deleteKeyCode={null}` no React Flow para o apagar passar pelo store.
- **Barra de edição** (`EditToolbar`): Desfazer, Refazer, Copiar, Colar, Apagar seleção e os botões de rotação existentes, ativos só quando a ação é possível; ícones em SVG (não dependem de fontes de emoji).

## Implementation

1. `src/editor/editing.ts`: `deleteElements`, `copyFragment`, `pasteFragment`, tipo `CircuitFragment`.
2. `src/store/editorStore.ts`: `past`, `future`, `historyGroup`, `clipboard`; `record`/`travel`; ações `undo`, `redo`, `beginHistoryGroup`, `endHistoryGroup`, `deleteSelection`, `copySelection`, `cutSelection`, `paste`; ações existentes passam por `record`; `setSelection` aceita fios.
3. `src/editor/flowNodes.ts`, `WireEdgeView.tsx`, `editor.css`: fio selecionado (`is-selected`) e separador da barra.
4. `src/editor/EditorCanvas.tsx`: `EditToolbar`, atalhos de teclado (`editShortcut`), Alt + clique em fios, agrupamento do arrasto.
5. Testes: `editing.test.ts` (apagar com fios/junções ligados, junções órfãs, nada a apagar; copiar só fios internos; colar com novos IDs, religação, deslocamento, cópias independentes), `editorStore.test.ts` (undo/redo de todas as ações, limite, `loadCircuit`, gestos, apagar fios, colar deslocado, cortar e colar no sítio) e `EditorCanvas.test.tsx` (atalhos, Backspace em campo/desenho, copiar/colar/cortar, Alt + clique em fio + Delete, botões da barra).
6. `apps/web/README.md`: secção "Editar (desfazer, copiar/colar, apagar)".

Verificação: `pnpm --filter @vcccircuitlab/web test` (163 testes), `lint`, `build`, `pnpm format:check`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/editor/editing.ts` | create | Apagar, copiar e colar (funções puras) |
| `apps/web/src/editor/editing.test.ts` | create | Testes das funções de edição |
| `apps/web/src/store/editorStore.ts` | modify | Histórico, área de transferência e novas ações |
| `apps/web/src/store/editorStore.test.ts` | modify | Testes do histórico e das ações |
| `apps/web/src/editor/EditorCanvas.tsx` | modify | Barra de edição, atalhos, seleção de fios, gestos |
| `apps/web/src/editor/EditorCanvas.test.tsx` | modify | Testes de integração |
| `apps/web/src/editor/flowNodes.ts` | modify | `selected` nas arestas |
| `apps/web/src/editor/WireEdgeView.tsx` | modify | Classe `is-selected` |
| `apps/web/src/editor/editor.css` | modify | Fio selecionado e separador da barra |
| `apps/web/README.md` | modify | Documentação |
