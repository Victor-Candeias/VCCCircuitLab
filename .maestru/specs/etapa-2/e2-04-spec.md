---
maestru: "0.4"
type: work-spec
id: e2-04-spec
title: "E2-04 — Plano de testes do solver com resultados analíticos"
template: testing-plan-v1
work-item: etapa-2/E2-04
owner: developer
created: 2026-10-14
---

# E2-04 — Plano de testes do solver com resultados analíticos

## Scope

Testes de aceitação do solver DC (E2-03) de ponta a ponta: documento JSON → `simulate_dc()` → `to_json_dict()`. Os valores esperados são calculados à mão (lei de Ohm, divisores e paralelos), nunca a partir do solver. Referências: arquitetura §7.1 e §12, testes 1–8.

- **Dentro do âmbito:** casos analíticos e de erro guardados como fixtures JSON em `apps/api/tests/fixtures/analytic/`, invariantes físicas (Kirchhoff e Tellegen) e estabilidade do interruptor.
- **Fora do âmbito:** testes unitários do normalizador, do validador e do solver, que já existem em `test_circuit_*.py` e `test_solver_mna.py`. Também ficam de fora o round-trip, o desempenho e a segurança (§12, testes 9–12, noutros itens).
- **NaN:** não é representável em JSON estrito e já é rejeitado pelo modelo (`test_circuit_validate.py`).

Formato de cada fixture: `{ "description", "reference", "circuit", "expected" }`.

- **Sucesso:** `expected` traz `nodeVoltagesV`, `components{voltageV,currentA,powerW}` e `warnings` (códigos).
- **Erro:** `expected` traz `errors`, a lista ordenada de códigos.

Os circuitos de sucesso declaram `nets` com IDs legíveis (por exemplo `N_PLUS`), o que obriga o normalizador a confirmar a partição esperada. As mesmas fixtures servem para os testes HTTP do E2-05 (`load_analytic_cases()` em `tests/factories.py`).

## Test Cases

| Fixture | §12 | Esperado |
|---|---|---|
| `serie-fonte-resistencia` | §7.1 | 12 V + 100 Ω → R1: 0,12 A, 1,44 W; V1: −0,12 A, −1,44 W |
| `serie-duas-resistencias` | 1 | 100 Ω + 200 Ω → 0,04 A; 4 V e 8 V; N_MID = 8 V |
| `paralelo-duas-resistencias` | 2 | 100 Ω ‖ 300 Ω → 0,12 A + 0,04 A; 1,44 W + 0,48 W |
| `serie-paralelo` | 1–2 | 100 Ω + (200 Ω ‖ 200 Ω) → 0,06 A; N_MID = 6 V; 0,03 A por ramo |
| `interruptor-fechado` | 3 | Lâmpada 12 V/6 W (24 Ω) → 0,5 A, 6 W; S1: 0 V |
| `interruptor-aberto` | 3 | Corrente 0 em todo o circuito; S1 com os 12 V |
| `fios-cruzados` | 4 | Duas malhas (12 V/100 Ω e 6 V/60 Ω) cujos fios se cruzam sem junção → independentes |
| `juncao-explicita` | 5 | J1 une 4 terminais (com J3 em cadeia) → 0,12 + 0,06 + 0,04 = 0,22 A |
| `fonte-corrente` | — | 0,1 A em 100 Ω ‖ 400 Ω → 8 V; 0,08 A e 0,02 A |
| `aviso-pino-desligado` | 6 | R2 com um pino solto → aviso `UNCONNECTED_PIN`, R2 sem corrente |
| `erro-terra-ausente` | 6 | `MISSING_GROUND` |
| `erro-no-flutuante` | 6 | `FLOATING_NET` |
| `erro-fontes-tensao-paralelo` | 7 | `VOLTAGE_SOURCE_LOOP` |
| `erro-fonte-curto-interruptor` | 7 | `VOLTAGE_SOURCE_LOOP` |
| `erro-fontes-corrente-serie` | 7 | `CURRENT_SOURCE_CUTSET` |
| `erro-resistencia-zero` | 8 | `INVALID_VALUE` |
| `erro-resistencia-negativa` | 8 | `INVALID_VALUE` |
| `erro-ids-duplicados` | 8 | `DUPLICATE_ID` |
| `erro-pino-desconhecido` | 8 | `UNKNOWN_TERMINAL` |

Verificações transversais aos casos de sucesso:

- valores iguais aos esperados (tolerância absoluta de 1e-9), com as mesmas redes e os mesmos componentes;
- **KVL:** `voltageV` = V(pino1) − V(pino2);
- **KCL:** a soma das correntes é 0 em cada rede (as redes com terra agrupadas num único nó de referência);
- **Tellegen:** a soma das potências é 0;
- todos os valores finitos e sem `-0.0`.

Testes específicos:

- **Interruptor:** alternar aberto → fechado → aberto dá resultados idênticos aos de uma simulação nova (sem estado e sem instabilidade).
- **Fios cruzados:** juntar os dois fios com uma junção no ponto de cruzamento passa a dar `VOLTAGE_SOURCE_LOOP`, o que prova que o cruzamento sem junção não os ligava.

## Verification

`pytest apps/api`, `ruff check apps/api` e `ruff format --check apps/api`. Todos os casos têm de passar.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/tests/fixtures/analytic/*.json` | create | Casos analíticos e de erro com o resultado esperado |
| `apps/api/tests/factories.py` | modify | `load_analytic_cases()` partilhado (E2-04, E2-05) |
| `apps/api/tests/test_solver_analytic.py` | create | Testes de aceitação parametrizados pelas fixtures |
| `apps/api/README.md` | modify | Secção sobre os testes analíticos |
