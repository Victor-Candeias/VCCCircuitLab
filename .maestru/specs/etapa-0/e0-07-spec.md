---
maestru: "0.4"
type: work-spec
id: e0-07-spec
title: "E0-07 — Plano de implementação do JSON Schema 1.0"
template: implementation-plan-v1
work-item: etapa-0/E0-07
owner: developer
created: 2026-10-12
---

# E0-07 — Plano de implementação do JSON Schema 1.0

## Overview

Definir o JSON Schema 1.0 do documento canónico de circuito em `packages/circuit-schema` (`Docs/arquitetura_simulador_circuitos.md` §3.1, §4), com junções explícitas, regras de IDs (`Componente.pino`), unidade de rotação e fonte de verdade `wires`/`junctions` vs. `nets`, e gerar tipos TypeScript partilhados.

## Implementation

### Fase 1 — Schema

1. `schema/circuit.schema.json` (draft 2020-12, `$id` `urn:vcccircuitlab:circuit-schema:1.0`): `schemaVersion: "1.0"`, `units: "SI"`, `components`, `junctions` (opcional), `wires`, `nets` (opcional, derivado); `additionalProperties: false`.
2. `$defs`: `ElementId` (sem `.`), `PinId`, `TerminalRef` (`Componente.pino`), `WireEndpoint` (terminal ou junção), `ComponentType` (snake_case), `Point`, `Rotation` (0/90/180/270, graus, sentido horário), `ComponentProperties` (camelCase com sufixo SI; `number | boolean`).

### Fase 2 — Tipos TypeScript

1. `scripts/generate-types.mjs` com `json-schema-to-typescript` → `src/circuit.ts` (gerado, versionado).
2. `src/index.ts` reexporta os tipos e `SCHEMA_VERSION`; `package.json` exporta `.` e `./circuit.schema.json`.

### Fase 3 — Testes e documentação

1. `test/schema.test.mjs` (node:test + Ajv 2020 em modo estrito): fixtures válidas (fonte+resistência; paralelo com junções e interruptor), 18 casos inválidos e verificação de que `src/circuit.ts` está sincronizado; `tsc --noEmit`.
2. `README.md` com estrutura, convenções e regras verificadas fora do schema (validador E2-02).

### Verificação

- `pnpm test` na raiz: 23 testes passam e `tsc --noEmit` sem erros.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/package.json` | create | Pacote, exports e scripts |
| `packages/circuit-schema/schema/circuit.schema.json` | create | JSON Schema 1.0 |
| `packages/circuit-schema/scripts/generate-types.mjs` | create | Geração de tipos TS |
| `packages/circuit-schema/src/circuit.ts` | create | Tipos gerados |
| `packages/circuit-schema/src/index.ts` | create | Ponto de entrada |
| `packages/circuit-schema/tsconfig.json` | create | Typecheck |
| `packages/circuit-schema/test/**` | create | Testes e fixtures |
| `packages/circuit-schema/README.md` | create | Convenções |
| `pnpm-lock.yaml` | update | ajv, json-schema-to-typescript, typescript |
