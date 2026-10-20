---
maestru: "0.4"
type: work-spec
id: f2-04-spec
title: "F2-04 — Díodos, LEDs e transístores"
template: implementation-plan-v1
work-item: fase-2/F2-04
owner: developer
created: 2026-10-20
---

# F2-04 — Díodos, LEDs e transístores

## Overview

Semicondutores com modelos SPICE (categoria `semiconductor`), resolvidos em DC e na transitória pelo método de Newton-Raphson e equivalentes aos modelos do ngspice:

- **Díodo** (`diode`) e **LED** (`led`), modelo `diode`, pinos `anode`/`cathode`. Têm as propriedades `forwardVoltageV` e `forwardCurrentA` (díodo: 0,7 V a 10 mA; LED: 2 V a 20 mA). Usam a equação de Shockley com N = 2 e IS escolhido para passar nesse ponto.
- **Transístores NPN/PNP** (`npn_transistor`/`pnp_transistor`), modelos `bjt_npn`/`bjt_pnp`, pinos `collector`/`base`/`emitter`. Usam Ebers–Moll de transporte com `currentGain` (BF), `saturationCurrentA` (IS) e BR = 1.
- **Resultados:**
  - díodo: V(ânodo) − V(cátodo) e corrente pelo ânodo;
  - transístor: `voltageV` = Vce, `currentA` = Ic e `powerW` = Vce·Ic + Vbe·Ib.
- **Newton:**
  - limitação `pnjlim` das junções e `GMIN` = 1e-12 S em paralelo com cada junção;
  - *source stepping* se não convergir a partir de x = 0;
  - erro `NO_CONVERGENCE` (`simulation-failed`) se mesmo assim falhar.
- **Validação:** as junções são arestas condutoras na topologia, pelo que um nó entre díodos em série não é `FLOATING_NET`.
- **ngspice:** elementos `D`/`Q` com `.model`. Fontes de 0 V em série medem a corrente do ânodo, do coletor e da base.
- **Frontend:** símbolos IEC, grupo «Semicondutores» na paleta e exemplo «Transístor NPN a comandar um LED».

## Implementation

### Phase 1: Catálogo e validação

| Step | Action |
|------|--------|
| 1 | Schema: categoria `semiconductor`, modelos `diode`/`bjt_npn`/`bjt_pnp`, `unit` opcional (grandezas sem dimensão). Tipos TS regenerados, modelo Pydantic e catálogo seed com os quatro componentes. |
| 2 | `validate.py`: modelos suportados e junções (`_JUNCTIONS`) como arestas resistivas na topologia. |

### Phase 2: Solvers

| Step | Action |
|------|--------|
| 1 | `app/solver/semiconductors.py`: modelos (correntes e Jacobiano), `pnjlim`, `NewtonSolver` com *source stepping* e `semiconductor_results`. |
| 2 | `mna.py`: semicondutores fora dos ramos lineares. `solve_dc` usa Newton quando há dispositivos; o passo linear verifica a singularidade com a matriz equilibrada. Resultados pela ordem do documento. |
| 3 | `transient.py`: integração BDF2 passo a passo com Newton (`_integrate_nonlinear`) e estado inicial pelo mesmo método. |
| 4 | Netlist ngspice (`D`/`Q`, `.model`, fontes de medida) e leitura das correntes no `engine.py`. |

### Phase 3: Frontend e exemplo

| Step | Action |
|------|--------|
| 1 | Símbolos `diode_iec`, `led_iec`, `npn_iec`, `pnp_iec`; categoria «Semicondutores» na paleta. |
| 2 | Fixture `transistor-led` no pacote e no menu Projeto. |

### Verificação

- `tests/test_semiconductors.py` cobre:
  - díodo e LED comparados com a solução escalar por bisseção;
  - inversa, *source stepping* e `NO_CONVERGENCE`;
  - NPN na região ativa (Ic = β·Ib, Vbe = Vt·ln(Ic/IS + 1)), saturação e PNP espelhado;
  - validação de nós só entre junções;
  - transitória (estado final igual ao DC e KCL);
  - netlist e o exemplo `transistor-led`.
- `tests/test_spice_ngspice.py` acrescenta as transitórias `rc-diodo` e `transistor-led`; o DC do exemplo entra pelas fixtures. Só corre na CI, com o ngspice instalado.
- Pacote `circuit-schema` (catálogo e fixtures), vitest (paleta) e `vite build`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/schema/catalog.schema.json` | modify | Categoria, modelos e `unit` opcional |
| `packages/circuit-schema/src/catalog.ts` | modify | Tipos regenerados |
| `packages/circuit-schema/test/fixtures/catalog.json` | modify | Díodo, LED, NPN e PNP |
| `packages/circuit-schema/test/fixtures/valid/transistor-led.json` | create | Exemplo |
| `apps/api/app/models/component.py` | modify | Categoria, modelos e `unit` opcional |
| `apps/api/app/circuit/validate.py` | modify | Modelos suportados e junções na topologia |
| `apps/api/app/circuit/errors.py`, `app/problems.py` | modify | `NO_CONVERGENCE` |
| `apps/api/app/solver/semiconductors.py` | create | Modelos e método de Newton |
| `apps/api/app/solver/mna.py`, `transient.py` | modify | DC e transitória não lineares |
| `apps/api/app/spice/netlist.py`, `engine.py` | modify | Elementos `D`/`Q` e correntes medidas |
| `apps/api/tests/test_semiconductors.py` | create | Testes |
| `apps/web/src/components/symbols/*`, `editor/palette.ts`, `project/examples.ts` | modify | Símbolos, paleta e exemplo |
| `README.md`, `apps/api/README.md` | modify | Documentação |
