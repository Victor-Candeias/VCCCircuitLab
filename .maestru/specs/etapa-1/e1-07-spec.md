---
maestru: "0.4"
type: work-spec
id: e1-07-spec
title: "E1-07 — Plano de importação/exportação JSON"
template: implementation-plan-v1
work-item: etapa-1/E1-07
owner: developer
created: 2026-10-14
---

# E1-07 — Plano de importação/exportação JSON

## Overview

Guardar e abrir o projeto do editor (`apps/web`) como documento canónico JSON Schema 1.0 (§4), com validação na importação e round-trip sem perda de topologia (§12, teste 9). Tudo local no browser (sem backend). Sem alterações ao schema.

Decisões:

- **Exportação canónica** (`toCanonical`/`serializeCircuit`): chaves pela ordem do schema, indentação de 2 espaços e nova linha final, para ficheiros estáveis e legíveis em diffs. O `nets` é **omitido** (é derivado; o normalizador da API reconstrói-o de `wires` + `junctions`) e `junctions` vazio também. O estado de vista (seleção, fio em desenho) nunca entra no documento.
- **Validação na importação** (`parseCircuit`): `JSON.parse` → JSON Schema com Ajv 2020 (mesmas opções dos testes do pacote: `allErrors`, `strict`) → regras de integridade que o schema não exprime mas de que o editor depende: IDs únicos em todo o documento (componentes, junções, fios, redes), tipo no catálogo, pinos iguais aos do catálogo, extremidades de fios existentes (`<componente>.<pino>` ou junção) e `from ≠ to`. Mensagens em português com o caminho JSON; lista limitada a 20 erros.
- **`nets` importado é descartado** com aviso (nunca é fonte de verdade no editor, evita incoerências com os fios).
- **Ficheiros**: `<input type="file">` escondido + `File.text()` (limite de 5 MB); guardar com `Blob` + `URL.createObjectURL` + `<a download>`. O nome do ficheiro é o slug do nome do circuito (sem acentos), ou o `id`.
- **Erros não destroem trabalho**: um ficheiro inválido mostra os erros num `role="alert"` (fechável) e o circuito atual fica intacto.
- **Novo** circuito vazio (confirmação se o atual tiver conteúdo).
- **Enquadrar após abrir**: `loadId` no store (incrementado por `loadCircuit`); o `EditorFlow` chama `fitView({ padding: 0.2 })` quando muda.
- O Ajv aumenta o bundle (~560 kB, aviso do Vite acima de 500 kB); aceitável nesta fase, code-splitting fica para mais tarde.

## Implementation

1. `src/project/circuitJson.ts`: `toCanonical`, `serializeCircuit`, `emptyCircuit`, `circuitFileName`, `parseCircuit`, `readCircuitFile`, `MAX_IMPORT_BYTES`.
2. `src/project/ProjectMenu.tsx` + `project.css`: nome do circuito, botões Novo / Abrir… / Guardar JSON, mensagem de erros/avisos.
3. `src/App.tsx` e `src/index.css`: menu no cabeçalho.
4. `src/store/editorStore.ts`: `loadId`; `src/editor/EditorCanvas.tsx`: `fitView` após carregar.
5. Dependência `ajv` em `apps/web`.
6. Testes: `circuitJson.test.ts` (round-trip do circuito de demonstração e das duas fixtures válidas do pacote — documento igual e ficheiro idêntico ao reexportar; ordem das chaves; nets ignorado com aviso; JSON inválido; erros de schema; IDs duplicados; tipo/pinos fora do catálogo; extremidades inexistentes; fio a si próprio; limite de erros; limite de tamanho; nome do ficheiro) e `ProjectMenu.test.tsx` (download do JSON canónico, abrir válido, abrir inválido sem alterar o circuito, Novo com confirmação).
7. `apps/web/README.md`: estrutura e secção "Projeto (abrir e guardar JSON)".

Verificação: `pnpm --filter @vcccircuitlab/web test` (122 testes), `lint`, `build`, `pnpm format:check`; módulos servidos pelo `vite dev`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/project/circuitJson.ts` | create | Serialização canónica, validação e leitura de ficheiros |
| `apps/web/src/project/circuitJson.test.ts` | create | Round-trip e validação |
| `apps/web/src/project/ProjectMenu.tsx` | create | UI Novo / Abrir / Guardar |
| `apps/web/src/project/ProjectMenu.test.tsx` | create | Testes da UI |
| `apps/web/src/project/project.css` | create | Estilos do menu e das mensagens |
| `apps/web/src/App.tsx` | modify | Menu no cabeçalho |
| `apps/web/src/index.css` | modify | Alinhamento do cabeçalho |
| `apps/web/src/store/editorStore.ts` | modify | `loadId` |
| `apps/web/src/editor/EditorCanvas.tsx` | modify | `fitView` após carregar |
| `apps/web/package.json` | modify | Dependência `ajv` |
| `apps/web/README.md` | modify | Documentação |
