---
maestru: "0.4"
type: work-spec
id: e2-02-spec
title: "E2-02 — Plano do validador topológico e de valores"
template: implementation-plan-v1
work-item: etapa-2/E2-02
owner: developer
created: 2026-10-13
---

# E2-02 — Plano do validador topológico e de valores

## Overview

Validador que corre antes do solver (E2-03). Recolhe numa só passagem todos os erros e avisos estruturados, para nunca se produzirem resultados arbitrários. Cobre os testes 6–8 da arquitetura (§12) e as "Regras fora do JSON Schema" do README de `packages/circuit-schema`. Referência: arquitetura §7.1.

Decisões:
- `validate(doc, catalog=None)` devolve `ValidationReport` (`errors`, `warnings`, `normalized`) e não lança exceções. `report.raise_for_errors()` lança `CircuitValidationError` e devolve o `NormalizedCircuit`; é a entrada prevista para o solver e para a API (E2-05).
- O catálogo (`packages/circuit-schema/catalog/components.json`) é copiado para `app/circuit/data/components.json`, porque a imagem Docker só inclui `app/`. Um teste garante que a cópia se mantém igual ao original.
- A verificação faz-se por fases, e cada fase só corre se as anteriores permitirem interpretar o circuito:
  1. **Documento:** IDs únicos em todo o documento (componentes, junções, fios, redes → `DUPLICATE_ID`); fios com `from` = `to` (`SELF_LOOP_WIRE`).
  2. **Componentes vs catálogo:** `UNKNOWN_COMPONENT_TYPE`, `UNSUPPORTED_MODEL` (`simulationModel` nulo ou desconhecido do validador), `UNKNOWN_PIN`/`MISSING_PIN` (os pinos têm de coincidir com o catálogo), `UNKNOWN_PROPERTY`/`MISSING_PROPERTY`, `INVALID_PROPERTY_TYPE` e `INVALID_VALUE` (fora de `minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum`, ou não finito). Zero e valores negativos caem em `exclusiveMinimum: 0`. O NaN já é rejeitado pelo modelo Pydantic e é verificado também aqui, como defesa.
  3. **Normalização (E2-01):** só corre sem `DUPLICATE_ID`. Os erros do normalizador (`UNKNOWN_TERMINAL`, `UNKNOWN_JUNCTION`, `NET_INCONSISTENT`) entram no relatório.
  4. **Topologia:** só corre com redes normalizadas e todos os componentes interpretáveis (tipo, modelo e pinos válidos). Cada rede é um nó; a terra liga a sua rede a um nó de referência virtual.
     - `UNCONNECTED_PIN` (aviso): terminal sozinho na sua rede.
     - `MISSING_GROUND` (erro): nenhum componente `ground`. Neste caso não se reportam redes flutuantes, que seriam todas.
     - `VOLTAGE_SOURCE_LOOP` (erro): malha só de elementos de impedância nula (fontes de tensão, interruptores fechados, terra) com pelo menos uma fonte de tensão. Inclui a fonte curto-circuitada, as fontes em paralelo e a fonte entre duas terras. As malhas só de interruptores e terras não são erro. Deteção: union-find, acrescentando primeiro as arestas sem fonte e depois as fontes. Cada fonte que fecha um ciclo é reportada com o caminho (BFS) como `refs`.
     - `FLOATING_NET`/`CURRENT_SOURCE_CUTSET` (erro): os grupos de redes sem caminho condutor até à terra, considerando resistências, lâmpadas, interruptores fechados, fontes de tensão e terra (as fontes de corrente não fixam potencial), têm potencial indefinido. Se o grupo toca numa fonte de corrente, o erro é `CURRENT_SOURCE_CUTSET` (fonte em aberto ou fontes em série); caso contrário, `FLOATING_NET`.
- Interruptor aberto = sem aresta. Interruptor fechado = aresta de impedância nula, coerente com "estados explícitos, sem R = ∞" (§7.3).

## Implementation

1. `app/circuit/errors.py`: novos códigos em `CircuitErrorCode`.
2. `app/circuit/data/components.json` (cópia) e `app/circuit/catalog.py`: `ComponentCatalog`, `ComponentSpec`, `PropertySpec` (com `check(value)`) e `load_catalog()` em cache.
3. `app/circuit/validate.py`: `ValidationReport` e `validate()` com as fases acima.
4. `tests/test_circuit_validate.py`: fixtures válidas sem erros; cópia do catálogo sincronizada; cada código com casos positivos e negativos (série, paralelo e interruptor aberto válidos; terra ausente; nós flutuantes; fontes em paralelo e curto; fontes de corrente em série ou em aberto; valores zero, negativos, acima do máximo, NaN e de tipo errado; IDs duplicados; pinos desconhecidos e em falta).
5. READMEs da API e do pacote `circuit-schema` (cópia do catálogo).

Verificação: `pytest apps/api`, `ruff check apps/api`, `ruff format --check apps/api`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/circuit/errors.py` | modify | Novos códigos de erro/aviso |
| `apps/api/app/circuit/data/components.json` | create | Cópia do catálogo incluída na imagem |
| `apps/api/app/circuit/catalog.py` | create | Carregamento e validação de propriedades do catálogo |
| `apps/api/app/circuit/validate.py` | create | Validador topológico e de valores |
| `apps/api/tests/test_circuit_validate.py` | create | Testes do validador |
| `apps/api/README.md` | modify | Documentação do validador |
| `packages/circuit-schema/README.md` | modify | Nota sobre a cópia do catálogo na API |
