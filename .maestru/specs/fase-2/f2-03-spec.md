---
maestru: "0.4"
type: work-spec
id: f2-03-spec
title: "F2-03 — Instrumentos virtuais"
template: implementation-plan-v1
work-item: fase-2/F2-03
owner: developer
created: 2026-10-20
---

# F2-03 — Instrumentos virtuais

## Overview

Três instrumentos virtuais **ideais** (categoria `instrument`), que leem os resultados da simulação sem a perturbar:

- **Voltímetro** (`voltmeter`, pinos `positive`/`negative`): impedância infinita. A leitura é o `voltageV` do componente, V(+) − V(−); a corrente é 0.
- **Amperímetro** (`ammeter`, pinos `positive`/`negative`): impedância nula, estampado como uma fonte de 0 V (como um interruptor fechado). A leitura é o `currentA`, que entra por `positive`. Em paralelo com uma fonte de tensão é um curto (`VOLTAGE_SOURCE_LOOP`).
- **Osciloscópio** (`oscilloscope`, pinos `ch1`/`ch2`): impedância infinita, sem ramo nem resultado próprio. Cada canal mede a tensão da sua rede em relação à terra (`nodeVoltagesV`). Na transitória, o gráfico desenha um traço por canal.

**Redes só com pontas** (todas as pontas são de voltímetros/osciloscópios, por exemplo uma ponta desligada):
- não são `FLOATING_NET` (fica só o aviso `UNCONNECTED_PIN`);
- ficam fora das incógnitas e de `nodeVoltagesV` (MNA, transitória e ngspice);
- um voltímetro com uma ponta numa delas não tem resultado.

**Frontend:**
- Símbolos (círculo com `V`/`A` e ecrã com onda), grupo «Instrumentos» na paleta.
- Leitura junto ao instrumento no canvas e tabela «Instrumentos» no painel (valores finais na transitória).
- Opção de gráfico «Osciloscópio …», escolhida por omissão quando o circuito tem um osciloscópio.
- Exemplo «medicoes-rc».

## Implementation

### Phase 1: Catálogo e validação

| Step | Action |
|------|--------|
| 1 | Categoria `instrument` e modelos `voltmeter`, `ammeter`, `oscilloscope` no schema, tipos TS, modelo Pydantic e catálogo seed. |
| 2 | `validate.py`: amperímetro como aresta de impedância nula; voltímetro/osciloscópio sem aresta; redes só com pontas excluídas de `FLOATING_NET`. |

### Phase 2: Solvers

| Step | Action |
|------|--------|
| 1 | `mna.py`: estampas (voltímetro → aberto, amperímetro → fonte de 0 V), osciloscópio sem ramo, `defined_nets()` exclui as redes só com pontas. |
| 2 | `component_results()`/`transient_result()` ignoram ramos abertos com redes sem potencial. |
| 3 | `transient.py` e netlist ngspice usam `defined_nets()`; ramos abertos sem elemento antes de procurar os nós. |

### Phase 3: Frontend

| Step | Action |
|------|--------|
| 1 | Símbolos `voltmeter_iec`, `ammeter_iec`, `oscilloscope_iec`; categoria na paleta. |
| 2 | `simulation/instruments.ts`: modelo, canais do osciloscópio (rede de cada pino) e leituras (DC ou último instante). |
| 3 | Leitura no canvas (`ComponentNodeView`), tabela no painel e quantidade `scope:<id>` no gráfico. |
| 4 | Exemplo `medicoes-rc` no pacote e no menu Projeto. |

### Verificação

- [x] Testes da API: validação (pontas desligadas, amperímetro em curto, voltímetro não fecha circuitos), leituras DC/transitória, `nodeVoltagesV` sem redes só com pontas, netlist.
- [x] Comparação com o ngspice real do exemplo `medicoes-rc` (CI; ignorada localmente).
- [x] Testes do frontend: leituras, canais, gráfico do osciloscópio, painel e leitura no canvas.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/schema/catalog.schema.json`, `src/catalog.ts` | Modify | Categoria `instrument` e modelos dos instrumentos. |
| `packages/circuit-schema/test/fixtures/catalog.json`, `test/catalog.test.mjs` | Modify | Instrumentos no catálogo (seed). |
| `packages/circuit-schema/test/fixtures/valid/medicoes-rc.json` | Create | Exemplo com os três instrumentos. |
| `apps/api/app/models/component.py` | Modify | Categoria e modelos no Pydantic. |
| `apps/api/app/circuit/validate.py` | Modify | Topologia dos instrumentos e redes só com pontas. |
| `apps/api/app/solver/mna.py`, `transient.py` | Modify | Estampas, `defined_nets()` e resultados. |
| `apps/api/app/spice/netlist.py` | Modify | Instrumentos na netlist. |
| `apps/api/tests/test_instruments.py` | Create | Testes dos instrumentos. |
| `apps/api/tests/conftest.py`, `factories.py`, `test_spice_ngspice.py` | Modify | Catálogo de teste e comparação ngspice. |
| `apps/web/src/components/symbols/symbolIds.ts`, `iecSymbols.tsx` | Modify | Símbolos dos instrumentos. |
| `apps/web/src/editor/palette.ts`, `ComponentNodeView.tsx`, `editor.css` | Modify | Grupo da paleta e leitura no canvas. |
| `apps/web/src/simulation/instruments.ts` | Create | Leituras e canais. |
| `apps/web/src/simulation/transient.ts`, `TransientChart.tsx`, `SimulationPanel.tsx` | Modify | Gráfico do osciloscópio e tabela de instrumentos. |
| `apps/web/src/project/examples.ts` | Modify | Exemplo no menu Projeto. |
| `apps/api/README.md`, `README.md` | Modify | Documentação. |
