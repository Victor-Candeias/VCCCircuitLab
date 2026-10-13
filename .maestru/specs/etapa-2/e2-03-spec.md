---
maestru: "0.4"
type: work-spec
id: e2-03-spec
title: "E2-03 — Plano do solver MNA DC"
template: implementation-plan-v1
work-item: etapa-2/E2-03
owner: developer
created: 2026-10-13
---

# E2-03 — Plano do solver MNA DC

## Overview

Solver DC por análise nodal modificada (MNA), que calcula o ponto de funcionamento em corrente contínua. Recebe o documento canónico, valida-o com `validate()` (E2-02) e devolve tensões por rede e tensão, corrente e potência por componente. Referência: arquitetura §7.1, §7.3 e §8.

Decisões:
- `simulate_dc(doc, catalog=None) -> DcResult` corre primeiro o validador. Se houver erros (terra ausente, sub-circuitos sem terra, fontes em conflito, etc.), lança `CircuitValidationError`; os avisos passam para o resultado. `solve_dc(normalized, catalog)` resolve um circuito já validado.
- Usa só NumPy (`numpy.linalg`), porque o SciPy não é necessário para matrizes densas pequenas (MVP ≤ ~100 componentes).
- Incógnitas: tensões das redes sem terra e correntes de ramo das fontes de tensão e dos interruptores fechados. Todas as redes com terra ficam a 0 V e são eliminadas.
- Estampas:
  - resistência e lâmpada (R = `ratedVoltageV`² / `ratedPowerW`) → condutância;
  - fonte de tensão → linha extra com `V(positive) − V(negative) = voltageV`;
  - interruptor fechado → fonte de 0 V (corrente definida, sem R = 0);
  - interruptor aberto → sem estampa (corrente 0, sem R = ∞);
  - fonte de corrente → injeta `currentA` na rede de `positive` e retira-a de `negative`.
- Convenção de sinais (passiva, igual para todos os componentes de dois terminais, pinos pela ordem do catálogo):
  - `voltageV = V(pino1) − V(pino2)`;
  - `currentA` = corrente que entra pelo pino 1 e atravessa o componente até ao pino 2;
  - `powerW = voltageV × currentA` = potência absorvida (negativa quando o componente fornece energia).

  Assim, na fonte de 12 V + 100 Ω, R1 tem 0,12 A e 1,44 W, e V1 tem −0,12 A e −1,44 W. A soma das potências é 0 (Tellegen).
- A terra não aparece em `components`: com várias terras na mesma rede, a repartição da corrente fica indefinida.
- Deteção numérica: um `LinAlgError` ou um resultado não finito dá `SINGULAR_MATRIX`; `cond(A) > 1e12` dá `ILL_CONDITIONED_MATRIX`. Ambos são erros, para nunca se devolverem resultados falsos (§7.1). Com o validador, estes casos só ocorrem com valores extremos.
- `DcResult.to_json_dict()` segue o formato da §8: `analysis`, `status`, `nodeVoltagesV`, `components{voltageV,currentA,powerW}` e `warnings[{code,message,refs}]`.

## Implementation

1. `requirements.txt`: `numpy==2.5.4`.
2. `app/circuit/errors.py`: `SINGULAR_MATRIX` e `ILL_CONDITIONED_MATRIX`.
3. `app/solver/mna.py`: `ComponentResult`, `DcResult`, `simulate_dc`, `solve_dc` (montagem da matriz, resolução, verificação do número de condição e pós-processamento).
4. `tests/test_solver_mna.py`: fonte de 12 V + 100 Ω, série, paralelo, lâmpada, interruptor aberto e fechado, fonte de corrente, fontes em série, terras múltiplas, conservação de potência, erros de validação propagados, matriz mal condicionada e formato JSON.
5. README da API.

Verificação: `pytest apps/api`, `ruff check apps/api`, `ruff format --check apps/api`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/requirements.txt` | modify | Dependência NumPy |
| `apps/api/app/circuit/errors.py` | modify | Códigos de erro numéricos |
| `apps/api/app/solver/mna.py` | create | Solver MNA DC |
| `apps/api/tests/test_solver_mna.py` | create | Testes do solver |
| `apps/api/tests/factories.py` | create | Construtores de circuitos partilhados pelos testes do validador e do solver |
| `apps/api/tests/test_circuit_validate.py` | modify | Usar `tests/factories.py` |
| `apps/api/README.md` | modify | Documentação do solver e convenção de sinais |
