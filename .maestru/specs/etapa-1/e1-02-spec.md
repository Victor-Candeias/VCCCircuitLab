---
maestru: "0.4"
type: work-spec
id: e1-02-spec
title: "E1-02 — Plano dos símbolos SVG IEC"
template: implementation-plan-v1
work-item: etapa-1/E1-02
owner: developer
created: 2026-10-14
---

# E1-02 — Plano dos símbolos SVG IEC

## Overview

Substituir o marcador provisório dos componentes no editor (`apps/web`) por símbolos SVG em simbologia IEC 60617 (§5.1, §15 decisão 2) para os seis tipos do catálogo: fonte de tensão DC, fonte de corrente DC, resistência, interruptor, lâmpada e terra. Sem alterações ao schema nem ao catálogo.

Decisões:

- **Localização**: `apps/web/src/components/symbols/` (§9: "UI e símbolos SVG"), reutilizável pela paleta (E1-03). Sem biblioteca externa nem base de dados: os símbolos são código React/SVG versionado; o catálogo guarda só o identificador (`ComponentDefinition.symbol`).
- **Coordenadas locais**: cada símbolo é desenhado com origem na âncora (`Component.position`), rotação 0 e as unidades do catálogo; os condutores (`symbol__lead`) terminam exatamente nas posições dos pinos do catálogo.
- **Rotação**: `ComponentSymbol` usa um `viewBox` centrado com o tamanho já rodado e `rotate(θ)` no SVG, que coincide com `rotateOffset` (rotação horária, eixo y para baixo); pinos e desenho rodam juntos. Os sinais de polaridade são contra-rodados para ficarem na vertical.
- **Símbolos**: fonte de tensão = círculo atravessado pelo condutor com `+`/`−`; fonte de corrente = círculo com traço perpendicular e seta para o terminal `positive` (sentido da corrente do catálogo); resistência = retângulo; interruptor = contacto de fecho, aberto/fechado conforme `properties.closed`, com contactos em círculo oco (não confundir com junções); lâmpada = círculo com cruz; terra = três traços decrescentes.
- **Registo estático**: `SYMBOL_IDS` + `switch` em `IecSymbol` (a regra `react-hooks/static-components` proíbe componentes resolvidos dinamicamente durante o render). IDs sem desenho mostram uma caixa tracejada vermelha; tipos fora do catálogo mantêm o marcador de erro.
- **Nó do editor**: o nó fica transparente (toda a caixa continua clicável); o ID aparece acima de símbolos horizontais e à direita dos verticais; a seleção pinta o símbolo com a cor de destaque e mostra um contorno tracejado. Os pinos passam a círculos ocos pequenos.

## Implementation

1. `src/components/symbols/symbolIds.ts`: `SYMBOL_IDS`, `SymbolId`, `isSymbolId`.
2. `src/components/symbols/iecSymbols.tsx`: desenho de cada símbolo e `IecSymbol` (switch por ID).
3. `src/components/symbols/ComponentSymbol.tsx` + `symbols.css`: caixa SVG rodada, cores por `currentColor` (`--wire`, tema claro/escuro), marcador de símbolo em falta.
4. `src/editor/ComponentNodeView.tsx` + `editor.css`: usa `ComponentSymbol`; rótulo, seleção, tipo desconhecido e pinos.
5. Testes (Vitest): `ComponentSymbol.test.tsx` (um símbolo por entrada do catálogo; cada pino é extremidade de um condutor; desenho dentro da caixa; viewBox e rotação; equivalência `rotate(θ)` ↔ `rotateOffset`; estado do interruptor; polaridade na vertical; símbolo em falta) e `EditorCanvas.test.tsx` (símbolo por nó com rotação; tipo desconhecido sem símbolo).
6. `apps/web/README.md`: estrutura e secção "Símbolos IEC".

Verificação: `pnpm --filter @vcccircuitlab/web test` (77 testes), `lint`, `build`, `pnpm format:check`; no browser (`vite preview` + Chromium headless com `playwright-core`): circuito de demonstração com os quatro símbolos, pinos nas extremidades dos condutores e fios ligados, seleção, temas claro/escuro, sem erros na consola; galeria dos seis símbolos nas quatro rotações e interruptor aberto/fechado.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/components/symbols/symbolIds.ts` | create | IDs de símbolos desenhados |
| `apps/web/src/components/symbols/iecSymbols.tsx` | create | Desenho SVG IEC de cada símbolo |
| `apps/web/src/components/symbols/ComponentSymbol.tsx` | create | Caixa SVG centrada e rodada |
| `apps/web/src/components/symbols/symbols.css` | create | Traço, preenchimento e marcadores |
| `apps/web/src/components/symbols/ComponentSymbol.test.tsx` | create | Testes dos símbolos |
| `apps/web/src/editor/ComponentNodeView.tsx` | modify | Nó com símbolo IEC |
| `apps/web/src/editor/editor.css` | modify | Rótulo, seleção, pinos |
| `apps/web/src/editor/EditorCanvas.test.tsx` | modify | Símbolos no canvas |
| `apps/web/README.md` | modify | Documentação dos símbolos |
