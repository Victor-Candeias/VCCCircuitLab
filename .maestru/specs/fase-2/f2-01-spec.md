---
maestru: "0.4"
type: work-spec
id: f2-01-spec
title: "F2-01 — Integração ngspice"
template: implementation-plan-v1
work-item: fase-2/F2-01
owner: developer
created: 2026-10-19
---

# F2-01 — Integração ngspice (tradutor JSON → netlist SPICE)

## Overview

Segundo motor de simulação DC, opcional: o circuito validado é traduzido para uma netlist SPICE
e resolvido pelo `ngspice` (binário, modo batch) num processo isolado, com timeout e limites de
CPU, memória e ficheiros. A integração é direta (sem PySpice). O resultado tem exatamente o
formato da simulação MNA (`DcResult`), pelo que o frontend não muda. O motor escolhe-se com
`SIMULATION_ENGINE=mna|ngspice` (por omissão `mna`).

## Implementation

### Phase 1: Tradutor e leitura de resultados

| Action | File | Details |
|---|---|---|
| Modify | `apps/api/app/solver/mna.py` | Expor `dc_branches()` (ramos de dois terminais) e `component_results()` (tensão/corrente/potência com a convenção passiva), partilhados pelos dois motores. |
| Create | `apps/api/app/spice/netlist.py` | `build_netlist()`: redes com terra → nó `0`, restantes → `n1…`; elementos com nomes gerados (`R1`, `V2`, …), nunca ids do utilizador. Resistência/lâmpada → `R`; fonte de tensão e interruptor fechado → `V … DC` (corrente de ramo); interruptor aberto → sem elemento; fonte de corrente → `I neg pos DC` (sai por `positive`). Bloco `.control`: `op` e `write` de um rawfile ASCII. |
| Create | `apps/api/app/spice/rawfile.py` | Parser do rawfile ASCII (`Variables:`/`Values:`), aceitando `v(n1)`/`n1` e `i(v1)`/`v1#branch`. |

### Phase 2: Execução isolada

| Action | File | Details |
|---|---|---|
| Create | `apps/api/app/spice/sandbox.py` | Lançador (`python -I app/spice/sandbox.py`, só biblioteca padrão) que aplica `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE` e `RLIMIT_CORE` a si próprio e faz `exec` do ngspice (evita `preexec_fn` com threads). |
| Create | `apps/api/app/spice/runner.py` | `run_ngspice()`: diretório temporário, ambiente mínimo, nova sessão, `timeout` (mata o grupo de processos). Erros: binário em falta/falha → `SimulationEngineError` (503 `SIMULATION_ENGINE_ERROR`); timeout → `SimulationTimeoutError`; matriz singular → `SINGULAR_MATRIX`. Configuração: `NGSPICE_PATH`, `NGSPICE_MAX_MEMORY_MB`. |
| Create | `apps/api/app/spice/engine.py` | `simulate_dc_ngspice()`: valida, gera a netlist, corre o ngspice e converte com `component_results()` → `DcResult`. |
| Create | `apps/api/app/solver/engine.py` | `simulate()`: escolhe o motor por `SIMULATION_ENGINE` (cada motor valida o documento). |
| Create | `apps/api/app/spice/errors.py` | `SimulationEngineError` e `singular_matrix_error()` (mesmo erro 422 do MNA). |
| Modify | `apps/api/app/routes/circuits.py`, `app/problems.py` | Usar `simulate()`; handler 503 do erro de motor. |

### Phase 3: Testes, CI e deploy

| Action | File | Details |
|---|---|---|
| Create | `apps/api/tests/test_spice.py` | Netlist (nós, orientação das fontes, interruptores, sem ids do utilizador), rawfile, runner com um ngspice falso (sucesso, timeout, falha, singular, limites aplicados) e API com `SIMULATION_ENGINE=ngspice`. |
| Create | `apps/api/tests/test_spice_ngspice.py` | Integração (só com `ngspice` instalado): todos os exemplos válidos dão o mesmo resultado que o MNA. |
| Modify | `.github/workflows/backend.yml` | Instalar `ngspice` para correr a integração. |
| Modify | `apps/api/Dockerfile`, `docker-compose.yml`, `.env.example`, `apps/api/README.md` | `ARG WITH_NGSPICE` na imagem; variáveis e documentação. |

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/solver/mna.py` | Modify | Expor `dc_branches()`, `Branch`, `BranchKind` e `component_results()` |
| `apps/api/app/spice/netlist.py` | Create | Circuito → netlist SPICE |
| `apps/api/app/spice/rawfile.py` | Create | Leitura do rawfile ASCII |
| `apps/api/app/spice/sandbox.py` | Create | Limites de recursos e `exec` do ngspice |
| `apps/api/app/spice/runner.py` | Create | Execução isolada com timeout |
| `apps/api/app/spice/errors.py` | Create | `SimulationEngineError`, erro de matriz singular |
| `apps/api/app/spice/engine.py` | Create | `simulate_dc_ngspice()` |
| `apps/api/app/solver/engine.py` | Create | Escolha do motor (`SIMULATION_ENGINE`) |
| `apps/api/app/problems.py` | Modify | 503 `SIMULATION_ENGINE_ERROR` |
| `apps/api/app/routes/circuits.py` | Modify | Usar `simulate()` |
| `apps/api/tests/test_spice.py` | Create | Testes com ngspice falso |
| `apps/api/tests/test_spice_ngspice.py` | Create | ngspice real vs. MNA |
| `apps/api/tests/test_api_circuits.py` | Modify | Mocks apontam para `simulate` |
| `.github/workflows/backend.yml` | Modify | Instalar ngspice na CI |
| `apps/api/Dockerfile` | Modify | `ARG WITH_NGSPICE` |
| `docker-compose.yml` | Modify | `WITH_NGSPICE`, `SIMULATION_ENGINE`, `NGSPICE_MAX_MEMORY_MB` |
| `.env.example` | Modify | Variáveis do motor |
| `apps/api/README.md` | Modify | Secção Motor ngspice |
| `README.md` | Modify | Nota sobre o motor |
