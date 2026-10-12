# 0006. Nome VCCCircuitLab e estrutura monorepo

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

Frontend, backend, schema partilhado, exemplos e documentação evoluem em conjunto; o JSON Schema do circuito tem de ser o mesmo para o editor e para a API.

## Decisão

A aplicação chama-se **VCCCircuitLab** e usa um **monorepo** com a estrutura de `Docs/arquitetura_simulador_circuitos.md` §9:

- `apps/web` — frontend React + Vite + TypeScript;
- `apps/api` — backend Python + FastAPI;
- `packages/circuit-schema` — JSON Schema versionado e tipos TS;
- `examples/`, `tests/`, `Docs/` e `.github/workflows/`.

## Consequências

- Alterações ao modelo canónico ficam num único sítio e numa única revisão.
- Pipelines de CI separados para frontend e backend.
- O backend Python não faz parte do workspace pnpm (ver ADR 0007).
