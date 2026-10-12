# 0007. pnpm com workspaces via Corepack

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

O monorepo tem vários pacotes JavaScript/TypeScript. Misturar gestores de pacotes (npm, yarn, pnpm) produz lockfiles divergentes e instalações não reprodutíveis.

## Decisão

Usar **pnpm com workspaces**, ativado via **Corepack**:

- versão fixada em `packageManager` no `package.json` raiz (`pnpm@10.x`);
- `pnpm-workspace.yaml` com `apps/web` e `packages/*`;
- **único lockfile** `pnpm-lock.yaml`; não usar npm/yarn nem outros lockfiles;
- `engine-strict=true` em `.npmrc`.

## Consequências

- Os contribuidores precisam de `corepack enable` (ou `corepack pnpm@10 <comando>`).
- Os scripts raiz (`dev`, `build`, `lint`, `format`, `test`) delegam nos pacotes com `pnpm -r --if-present`.
- O CI deve usar `pnpm install --frozen-lockfile`.
