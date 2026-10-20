---
maestru: "0.4"
type: work-spec
id: f2-07-spec
title: "F2-07 — Componentes de rede 230/400 V e proteções"
template: implementation-plan-v1
work-item: fase-2/F2-07
owner: developer
created: 2026-10-20
---

# F2-07 — Componentes de rede 230/400 V e proteções

## Overview

Componentes de instalações domésticas 230/400 V com simbologia IEC 60617, modelos simples e avisos de segurança (§1.2, §7.3 da arquitetura).

- **Catálogo:**
  - `mains_source`: rede CA, RMS, 50–60 Hz.
  - `mains_lamp`.
  - `changeover_switch`: comutador de escada.
  - `circuit_breaker` e `rcd`: categoria nova `protection`.
  - `relay`: só símbolo, `simulationModel` null.
- **Análise:** a rede é simulada em regime RMS equivalente no solver DC (fonte de tensão de `voltageV`) e só com cargas resistivas. A análise transitória rejeita a rede com `UNSUPPORTED_ANALYSIS`, e a exportação SPICE gera `SIN(0 Vpico f)`.
- **Contactos múltiplos:**
  - O comutador é um contacto comum–ativo; o terminal inativo comporta-se como uma ponta de instrumento.
  - O diferencial tem um contacto por polo (`ID1:L`, `ID1:N`), com resultados juntos num só componente.
- **Avisos:**
  - `MAINS_VOLTAGE`: sempre.
  - `MISSING_PROTECTION`: sem disjuntor.
  - `OVERCURRENT`: corrente acima de `In`.
  - `RESIDUAL_CURRENT`: `|iL + iN|` acima de `IΔn`.
- **Fora do âmbito:**
  - Análise fasorial/AC com componentes reativos.
  - Disparo automático: o simulador avisa, mas não abre a proteção.
  - Simulação do relé.
  - Template `iluminacao_escada` (F2-08).

## Implementation

### Fase 1 — Catálogo e schema

| Step | Action |
|------|--------|
| 1 | `catalog.schema.json`: categoria `protection`; modelos `ac_voltage_source`, `changeover_switch`, `circuit_breaker`, `rcd`. Regenerar `src/catalog.ts`. |
| 2 | Seis entradas novas em `test/fixtures/catalog.json` (prefixos únicos `AC`, `SC`, `K`, `QF`, `ID`, `HR`). |

### Fase 2 — Validação e solver

| Step | Action |
|------|--------|
| 1 | `validate.py`: `contacts()`/`open_terminals()` para componentes com vários contactos; topologia com contactos fechados de impedância nula. |
| 2 | `_check_mains`: `UNSUPPORTED_ANALYSIS` (transitória ou DC com elementos não resistivos), `MAINS_VOLTAGE` e `MISSING_PROTECTION`. A análise `export` aceita a rede. |
| 3 | `mna.py`: um ramo por contacto e a fonte CA estampada como fonte de tensão; `finish_dc` junta os polos e acrescenta os avisos de disparo. |
| 4 | `protection.py`: `finish_components` para `OVERCURRENT` e `RESIDUAL_CURRENT`; `finish_transient` e o motor ngspice usam a mesma função. |
| 5 | `exchange.py`: exportação `SIN` e fontes de 0 V por contacto; a importação aceita primeiro o documento embutido não editado. |

### Fase 3 — Editor e docs

| Step | Action |
|------|--------|
| 1 | Símbolos `ac_voltage_source_iec`, `switch_spdt_iec`, `relay_iec`, `circuit_breaker_iec`, `rcd_iec` (estado desenhado: `toL2`, `closed`). |
| 2 | Grupo «Proteção» na paleta. |
| 3 | READMEs (raiz e API). |

### Verificação

- `tests/test_mains_protection.py`:
  - avisos e rejeições da validação, incluindo o relé não suportado;
  - lâmpada RMS e disjuntor aberto ou em sobrecorrente;
  - as quatro combinações do comutador de escada;
  - junção dos polos do diferencial, fuga à terra e sobrecorrente;
  - transitória com diferencial;
  - netlist ngspice, exportação SPICE e reimportação.
- `ComponentSymbol.test.tsx`: pinos nas extremidades dos condutores e estados desenhados.
- `palette.test.ts` e `EditorCanvas.test.tsx`: grupo «Proteção».
- `pytest`, `ruff`, `node --test`, `tsc`, `eslint`, `prettier`, `vitest`, `vite build`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/schema/catalog.schema.json`, `src/catalog.ts` | Modificar | Categoria e modelos novos |
| `packages/circuit-schema/test/fixtures/catalog.json` | Modificar | Seis componentes novos |
| `apps/api/app/circuit/validate.py`, `errors.py` | Modificar | Contactos, regras da rede, códigos novos |
| `apps/api/app/solver/mna.py`, `transient.py` | Modificar | Ramos por contacto, junção de polos |
| `apps/api/app/solver/protection.py` | Criar | Avisos de disparo |
| `apps/api/app/spice/engine.py`, `exchange.py` | Modificar | ngspice e SPICE |
| `apps/api/tests/test_mains_protection.py` | Criar | Testes F2-07 |
| `apps/web/src/components/symbols/*` | Modificar | Símbolos IEC novos |
| `apps/web/src/editor/palette.ts` | Modificar | Grupo «Proteção» |
| `README.md`, `apps/api/README.md` | Modificar | Documentação |
