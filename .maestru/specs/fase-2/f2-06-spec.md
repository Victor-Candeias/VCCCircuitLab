---
maestru: "0.4"
type: work-spec
id: f2-06-spec
title: "F2-06 — Gerador de circuitos por linguagem natural"
template: implementation-plan-v1
work-item: fase-2/F2-06
owner: developer
created: 2026-10-20
---

# F2-06 — Gerador de circuitos por linguagem natural

## Overview

Geração de circuitos a partir de uma descrição em português (§6.1 da arquitetura), sem quebrar as garantias da geração por templates.

- **Parser de intenções determinístico** (`app/generation/natural.py`), sem LLM: um LLM externo enviaria o texto do utilizador a terceiros e exigiria credenciais; fica possível no futuro atrás da mesma validação.
- **Saída limitada aos templates existentes** (`series_dc`, `parallel_dc`, `voltage_divider`, `switch_circuit`): o texto só escolhe um template e os seus parâmetros; nunca é executado nem transformado em código.
- **Três barreiras:** schema (modelo Pydantic do template), regras elétricas (`validate`) e confirmação visual no editor (resumo, valores assumidos e pré-visualização SVG antes de «Abrir no editor»).
- **Erros:** 422 `uninterpretable-text` / `UNINTERPRETABLE_TEXT`, um item por motivo; valores fora dos limites dão `invalid-parameters`.
- **Fora do âmbito:** circuitos mistos série/paralelo, fontes AC, condensadores/indutores e componentes fora dos templates.

## Implementation

### Fase 1 — Parser (backend)

| Step | Action |
|------|--------|
| 1 | Normalizar o texto (NFC, Ω, vírgula decimal) e criar uma versão sem acentos e em minúsculas com as mesmas posições. |
| 2 | Extrair quantidades (número, prefixo SI, unidade). V → tensão, Ω ou prefixo → resistência; A/W/F/H/Hz → erro. |
| 3 | Separar contagens («três resistências») dos valores; classificar números sem unidade pelo contexto («fonte de», «resistência de») ou pela lista vizinha. |
| 4 | Escolher o template por palavras-chave (divisor > interruptor > paralelo/série); sem palavra-chave assume série. |
| 5 | Preencher o que falta com valores por omissão e registá-los em `assumptions`; validar pelo modelo do template. |

### Fase 2 — Endpoint

| Step | Action |
|------|--------|
| 1 | `UninterpretableTextError` em `app/generation/errors.py` e handler `uninterpretable-text` em `app/problems.py`. |
| 2 | `POST /api/v1/circuits/generate/text` (`{text}`, 1–1000 caracteres, sem campos extra): interpretar, gerar, `validate(...).raise_for_errors()`, devolver `{template, title, parameters, summary, assumptions, circuit, warnings}`. |

### Fase 3 — Editor

| Step | Action |
|------|--------|
| 1 | `generateFromText` em `api/client.ts` e tipo `GenerateTextResult`. |
| 2 | `CircuitPreview`: SVG estático com os símbolos do catálogo e os traçados dos fios do editor. |
| 3 | `GenerateDialog`: modo «Texto livre» com «Interpretar» → resumo, valores assumidos, pré-visualização → «Abrir no editor» (com a confirmação habitual). Alterar o texto descarta a interpretação. |

### Verificação

- `tests/test_generation_natural.py`: frases para cada template, unidades e prefixos, listas e contexto, contagens, valores assumidos, rejeições (texto vazio de sentido, série+paralelo, unidades não suportadas, contagens inconsistentes, código) e o endpoint (incluindo simulação do circuito gerado).
- `client.test.ts` e `GenerateDialog.test.tsx` (pré-visualização com um nó por componente e um traçado por fio; não abre sem confirmação).
- `pytest`, `ruff`, `tsc`, `eslint`, `prettier`, `vitest` e `vite build`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/generation/natural.py` | Criar | Parser de intenções |
| `apps/api/app/generation/errors.py` | Editar | `UninterpretableTextError` |
| `apps/api/app/problems.py` | Editar | Código e handler `uninterpretable-text` |
| `apps/api/app/routes/circuits.py` | Editar | `POST /generate/text` |
| `apps/api/tests/test_generation_natural.py` | Criar | Testes do parser e do endpoint |
| `apps/web/src/api/client.ts`, `types.ts` | Editar | `generateFromText`, `GenerateTextResult` |
| `apps/web/src/project/CircuitPreview.tsx` | Criar | Pré-visualização SVG |
| `apps/web/src/project/GenerateDialog.tsx`, `project.css` | Editar | Modo «Texto livre» |
| `apps/web/src/api/client.test.ts`, `project/GenerateDialog.test.tsx` | Editar | Testes |
| `apps/api/README.md`, `README.md` | Editar | Documentação |
