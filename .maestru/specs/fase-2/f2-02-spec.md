---
maestru: "0.4"
type: work-spec
id: f2-02-spec
title: "F2-02 — Condensadores, bobinas e análise transitória"
template: implementation-plan-v1
work-item: fase-2/F2-02
owner: developer
created: 2026-10-19
---

# F2-02 — Condensadores, bobinas e análise transitória

## Overview

Novos componentes `capacitor` (capacidade `capacitanceF`, tensão inicial `initialVoltageV`) e `inductor` (indutância `inductanceH`, corrente inicial `initialCurrentA`), e uma análise transitória com gráficos (Recharts).

- **Análise DC:** o condensador é um circuito aberto e a bobina um curto-circuito (fonte de 0 V, para dar a corrente). O MNA e o ngspice mantêm o formato atual.
- **Análise transitória:** `POST /api/v1/circuits/simulate/transient` com `{circuit, stopTimeS, timeStepS}`.
  - As fontes (DC) ligam-se em t = 0 e os condensadores e bobinas partem das condições iniciais (0 por omissão). É a resposta ao degrau de circuitos RC, RL e RLC.
  - A resposta tem `timeS`, `nodeVoltagesV` (série por rede) e `components` (séries de `voltageV`, `currentA` e `powerW`), com a mesma convenção passiva da DC.
- **Motores** (`SIMULATION_ENGINE`):
  - `mna`: integração própria por BDF2 (Gear de 2.ª ordem, L-estável, sem oscilações numéricas) com modelos companheiros e passo fixo. O primeiro passo é de Euler implícito, e há subpassos internos para ter pelo menos 2000 passos.
  - `ngspice`: `.tran` com `uic` e `IC=`, depois `linearize` para obter pontos equidistantes.
- **Validação dependente da análise:**
  - Em DC, o condensador não conduz (como um interruptor aberto) e a bobina tem impedância nula (como um interruptor fechado: uma fonte de tensão em paralelo com uma bobina é um curto).
  - Na transitória, ambos são condutores para a deteção de redes flutuantes. Malhas fonte de tensão–condensador e cortes fonte de corrente–bobina são permitidos: o salto de estado em t = 0 é resolvido pelo primeiro passo.
- **Limites:** `stopTimeS` ∈ ]0, 1000] s, `timeStepS` > 0, no máximo 10 000 pontos de saída (422 `INVALID_PARAMETERS`); o timeout é o mesmo da DC.
- **Frontend:**
  - Símbolos IEC do condensador e da bobina; escolha da análise (DC/transitória) com a duração e o passo.
  - Gráfico (Recharts) das tensões das redes, ou da tensão/corrente dos componentes, mais uma tabela com os valores finais.
  - Novo exemplo «Carga de um condensador (RC)».

## Implementation

### Phase 1: Modelos e validação

| Action | File | Details |
|---|---|---|
| Modify | `packages/circuit-schema/schema/catalog.schema.json`, `src/catalog.ts`, `test/fixtures/catalog.json` | Modelos `capacitor`/`inductor`; componentes no catálogo (seed). |
| Modify | `apps/api/app/models/component.py` | `SimulationModel` com `capacitor`/`inductor`. |
| Modify | `apps/api/app/circuit/validate.py` | `validate(..., analysis="dc"|"transient")`: classificação das arestas por análise. |

### Phase 2: Solvers

| Action | File | Details |
|---|---|---|
| Modify | `apps/api/app/solver/mna.py` | `BranchKind.CAPACITOR/INDUCTOR` (com `initial`); `dc_branches()` converte-os nos equivalentes DC. |
| Create | `apps/api/app/solver/transient.py` | `TransientResult`, `simulate_transient()` (BDF2 com companheiros, t = 0 consistente ou, se singular, 0⁺). |
| Modify | `apps/api/app/spice/netlist.py`, `rawfile.py`, `engine.py` | Netlist `.tran … uic` + `linearize`; rawfile com vários pontos e `@c1[i]`. |
| Modify | `apps/api/app/solver/engine.py`, `routes/circuits.py` | `simulate_transient()` por motor; endpoint `/simulate/transient`. |

### Phase 3: Frontend

| Action | File | Details |
|---|---|---|
| Modify | `apps/web/src/components/symbols/*` | Símbolos `capacitor_iec`/`inductor_iec`. |
| Modify | `apps/web/src/api/*`, `simulation/*` | Cliente, store e painel com a análise transitória e o gráfico (Recharts). |
| Modify | `apps/web/src/project/examples.ts` | Exemplo RC. |

### Verificação

- [x] Testes analíticos: carga RC, RL, RLC subamortecido e condições iniciais (erro relativo < 1e-3).
- [x] Comparação com o ngspice real (CI; ignorada localmente sem ngspice).
- [x] Testes do endpoint (limites, erros) e do frontend (painel, store, cliente).

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/schema/catalog.schema.json`, `src/catalog.ts` | Modify | Modelos `capacitor`/`inductor`. |
| `packages/circuit-schema/test/fixtures/catalog.json`, `test/catalog.test.mjs` | Modify | Componentes condensador e bobina no catálogo (seed). |
| `packages/circuit-schema/test/fixtures/valid/carga-condensador.json` | Create | Exemplo RC. |
| `apps/api/app/models/component.py` | Modify | `SimulationModel` com os novos modelos. |
| `apps/api/app/circuit/validate.py` | Modify | Topologia dependente da análise. |
| `apps/api/app/solver/mna.py` | Modify | Ramos reativos e equivalentes DC. |
| `apps/api/app/solver/transient.py` | Create | Solver BDF2 e `TransientResult`. |
| `apps/api/app/solver/engine.py` | Modify | `simulate_transient()` por motor. |
| `apps/api/app/spice/netlist.py`, `rawfile.py`, `engine.py` | Modify | Transitória no ngspice. |
| `apps/api/app/routes/circuits.py`, `app/problems.py` | Modify | Endpoint `/simulate/transient` e erros de parâmetros. |
| `apps/api/tests/test_solver_transient.py` | Create | Testes analíticos da transitória. |
| `apps/api/tests/test_api_circuits.py`, `test_spice.py`, `test_spice_ngspice.py`, `test_circuit_validate.py`, `conftest.py`, `factories.py` | Modify | Endpoint, netlist/rawfile, comparação ngspice e catálogo de teste. |
| `apps/web/src/components/symbols/symbolIds.ts`, `iecSymbols.tsx` | Modify | Símbolos IEC do condensador e da bobina. |
| `apps/web/src/api/types.ts`, `client.ts` | Modify | `TransientResult` e `simulateTransient()`. |
| `apps/web/src/simulation/simulationStore.ts`, `SimulationPanel.tsx`, `simulation.css` | Modify | Escolha da análise, duração/passo, vista transitória. |
| `apps/web/src/simulation/transient.ts`, `TransientChart.tsx` | Create | Séries, subamostragem, valores finais e gráfico (Recharts, carregado a pedido). |
| `apps/web/src/project/examples.ts` | Modify | Exemplo «Carga de um condensador (RC)». |
| `apps/web/package.json`, `pnpm-lock.yaml` | Modify | Dependência `recharts`. |
| `apps/api/README.md`, `README.md` | Modify | Documentação da análise transitória. |
