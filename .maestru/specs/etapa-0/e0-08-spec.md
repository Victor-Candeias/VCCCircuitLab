---
maestru: "0.4"
type: work-spec
id: e0-08-spec
title: "E0-08 — Plano do catálogo inicial de componentes"
template: implementation-plan-v1
work-item: etapa-0/E0-08
owner: developer
created: 2026-10-12
---

# E0-08 — Plano do catálogo inicial de componentes

## Overview

Catálogo inicial dos componentes do MVP (§1.1, §4.1 da arquitetura) em `packages/circuit-schema`: um ficheiro de dados (`catalog/components.json`) validado por um JSON Schema próprio (`schema/catalog.schema.json`), com tipos TypeScript gerados (`src/catalog.ts`). Cada definição separa símbolo, terminais (pinos com posição relativa), validação de propriedades e modelo elétrico. As convenções de IDs, unidades SI, grelha e polaridade ficam documentadas no README do pacote.

Decisões:

- Limites das propriedades usam as palavras-chave do JSON Schema (`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`) em vez do `minExclusive` do exemplo da arquitetura — o mesmo validador (Ajv/Pydantic) aplica-as diretamente.
- `simulationModel: null` representa "não suportado pelo solver" (§1.1).
- Grelha de 20 unidades; posições de pinos múltiplas da grelha, relativas à âncora com rotação 0.
- Prefixo `H` para lâmpadas (evita colisão com `L` de bobinas na fase 2); `GND` para terra.
- Fonte de corrente: a corrente entra por `negative` e sai por `positive` para o circuito externo.
- Lâmpada: R = `ratedVoltageV`² / `ratedPowerW`.

## Implementation

1. `schema/catalog.schema.json` (draft 2020-12): `ComponentCatalog` → `ComponentDefinition` (`type`, `label`, `category`, `idPrefix`, `symbol`, `size`, `pins`, `properties`, `simulationModel`), `PinDefinition`, `PropertyDefinition` (`oneOf` número/booleano).
2. `catalog/components.json` com os 6 componentes do MVP: `dc_voltage_source`, `dc_current_source`, `resistor`, `switch`, `lamp`, `ground`.
3. `scripts/generate-types.mjs` generalizado para vários alvos (circuito e catálogo); `src/index.ts` reexporta os tipos e `CATALOG_VERSION`.
4. Exports `./catalog.schema.json` e `./catalog.json` no `package.json`.
5. `test/catalog.test.mjs`: catálogo válido, tipos do MVP presentes, tipos/prefixos únicos, pinos únicos, na grelha e dentro do símbolo, defaults dentro dos limites, rejeição de tipos/modelos inválidos e fixtures de circuito coerentes com o catálogo. O teste de sincronização de tipos cobre os dois schemas.
6. README do pacote com a tabela do catálogo e as convenções.

Verificação: `pnpm test` (43 testes + `tsc --noEmit`), `pnpm build`, `pnpm lint`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/schema/catalog.schema.json` | create | Schema do catálogo |
| `packages/circuit-schema/catalog/components.json` | create | Definições dos componentes do MVP |
| `packages/circuit-schema/src/catalog.ts` | create | Tipos gerados do catálogo |
| `packages/circuit-schema/src/index.ts` | modify | Reexportar tipos do catálogo e `CATALOG_VERSION` |
| `packages/circuit-schema/scripts/generate-types.mjs` | modify | Gerar tipos de vários schemas |
| `packages/circuit-schema/package.json` | modify | Exports do catálogo |
| `packages/circuit-schema/test/catalog.test.mjs` | create | Testes do catálogo |
| `packages/circuit-schema/test/schema.test.mjs` | modify | Sincronização de tipos para ambos os schemas |
| `packages/circuit-schema/README.md` | modify | Documentar catálogo e convenções |
