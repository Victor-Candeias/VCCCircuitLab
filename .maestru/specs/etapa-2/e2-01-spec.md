---
maestru: "0.4"
type: work-spec
id: e2-01-spec
title: "E2-01 — Plano dos modelos Pydantic e normalizador de redes"
template: implementation-plan-v1
work-item: etapa-2/E2-01
owner: developer
created: 2026-10-12
---

# E2-01 — Plano dos modelos Pydantic e normalizador de redes

## Overview

Implementar os modelos Pydantic v2 do documento canónico (schemaVersion 1.0) e o normalizador que reconstrói as redes a partir de `wires` e `junctions` com union-find, rejeitando `nets` inconsistentes. Referência: arquitetura §4 e §7.1.

Decisões:
- Os modelos são estritos (`strict`, `extra="forbid"`, `allow_inf_nan=False`) e imutáveis (`frozen`). Inteiros são aceites como números; booleanos não.
- Usam os mesmos padrões e limites do JSON Schema. `from` mapeia para `from_`, com alias na entrada e na saída.
- A unicidade de IDs entre elementos e as regras elétricas ficam para o validador topológico (E2-02). Aqui só se tratam as referências dos fios e a coerência de `nets`.
- `nets` só contém terminais; as junções servem apenas de ponte. Um terminal isolado forma uma rede singleton. Uma junção sem terminais não gera rede.
- Com `nets` declarado, a partição tem de ser exatamente igual à calculada, e nesse caso preservam-se os IDs. Sem `nets`, geram-se `N1..Nk` pela ordem do primeiro terminal (componentes e pinos), saltando IDs já usados.
- Os erros são estruturados (`CircuitValidationError` → lista de `CircuitError{code, message, refs}`), prontos para o problem+json da API (E2-03/E3).

## Implementation

1. `app/models/circuit.py`: tipos anotados (padrões de ID, `Rotation`, `FiniteNumber`), `Point`, `Component`, `Junction`, `Wire`, `Net`, `CircuitDocument.to_json_dict()`.
2. `app/circuit/errors.py`: `CircuitErrorCode`, `CircuitError` e `CircuitValidationError`.
3. `app/circuit/normalize.py`: `UnionFind` (compressão de caminho + rank), `build_nets` (partição ou erros `UNKNOWN_TERMINAL`/`UNKNOWN_JUNCTION`), `_check_declared_nets` (`UNKNOWN_TERMINAL`, `NET_INCONSISTENT`) e `normalize` → `NormalizedCircuit`.
4. Testes pytest com as fixtures de `packages/circuit-schema/test/fixtures/valid`, casos limite (fios cruzados, junções em cadeia, fio em laço, singletons, determinismo, colisão de IDs) e rejeições do modelo.
5. Atualizar o README da API.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/models/circuit.py` | create | Modelos Pydantic do documento |
| `apps/api/app/circuit/errors.py` | create | Erros estruturados com código |
| `apps/api/app/circuit/normalize.py` | create | Union-find e reconstrução/validação de redes |
| `apps/api/tests/test_circuit_normalize.py` | create | Testes dos modelos e do normalizador |
| `apps/api/README.md` | update | Documentação do módulo |