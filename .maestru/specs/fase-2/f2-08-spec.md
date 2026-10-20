---
maestru: "0.4"
type: work-spec
id: f2-08-spec
title: "F2-08 — Template de geração iluminacao_escada (230 V)"
template: implementation-plan-v1
work-item: fase-2/F2-08
owner: developer
created: 2026-10-20
---

# F2-08 — Template de geração iluminacao_escada (230 V)

## Overview

Template de geração da iluminação de escada (§6.1 da arquitetura, `iluminacao_escada`), registado como `staircase_lighting` para seguir a convenção dos outros templates (`series_dc`, `switch_circuit`, …). Usa os componentes de rede da F2-07.

- **Circuito:** `AC1` (rede) → `QF1` (disjuntor) → `SC1` ⇄ `SC2` (comutadores ligados pelos dois retornos) → `HR1` (lâmpada de rede) → neutro, com o neutro à terra (`GND1`, necessária ao solver).
- **Parâmetros (todos opcionais):**

  | Parâmetro | Omissão | Limites |
  |---|---|---|
  | `voltageV` | 230 | ≤ 400 |
  | `frequencyHz` | 50 | 50–60 |
  | `lampPowerW` | 60 | ≤ 5000 |
  | `breakerRatedA` | 10 | ≤ 125 |
  | `switch1ToL2`, `switch2ToL2` | `false` | — |

  Os limites são os do catálogo.
- **Funcionamento:** a lâmpada acende com os comutadores em posições diferentes.
- **Layout:** `staircase_loop`, com o segundo comutador rodado 180°. Os retornos (`SC1.l1`–`SC2.l2`, `SC1.l2`–`SC2.l1`) ficam horizontais e paralelos.
- **Texto livre:** «escada»/«lustre» escolhem o template. Aceita V, Hz, W e A; «acesa» liga a lâmpada.

## Implementation

### Fase 1 — Backend

| Step | Action |
|------|--------|
| 1 | `StaircaseLightingParams` em `params.py` (limites do catálogo). |
| 2 | `staircase_loop` em `layout.py` e `build_staircase_lighting` em `templates.py`; registo em `registry.py`. |
| 3 | `natural.py`: ramo `_interpret_staircase` (unidades V/Hz/W/A, estado acesa/apagada, valores assumidos, resumo). |

### Fase 2 — Editor e docs

| Step | Action |
|------|--------|
| 1 | `generateTemplates.ts`: template «Iluminação de escada (rede 230 V)» com os seis campos. |
| 2 | READMEs (raiz e API) e nota na arquitetura (§6.1). |

### Verificação

- `test_generation_templates.py`:
  - documento válido, só com o aviso `MAINS_VOLTAGE`;
  - as quatro combinações dos comutadores;
  - os parâmetros chegam aos componentes;
  - os limites são respeitados.
- `test_generation_layout.py`: pinos na grelha, segmentos ortogonais e retornos paralelos.
- `test_generation_natural.py`: valores assumidos, leitura de W/A/estado, rejeição de Ω e limites. O endpoint gera um circuito simulável.
- `test_api_generate.py` e `generateTemplates.test.ts`.
- `pytest`, `ruff`, `tsc`, `eslint`, `vitest`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/generation/params.py`, `templates.py`, `registry.py`, `layout.py` | Modificar | Template `staircase_lighting` |
| `apps/api/app/generation/natural.py` | Modificar | Texto livre «escada» |
| `apps/api/tests/test_generation_*.py`, `test_api_generate.py` | Modificar | Testes |
| `apps/web/src/project/generateTemplates.ts` | Modificar | Formulário «Gerar…» |
| `README.md`, `apps/api/README.md`, `Docs/arquitetura_simulador_circuitos.md` | Modificar | Documentação |
