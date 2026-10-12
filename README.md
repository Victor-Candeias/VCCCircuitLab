# VCCCircuitLab
Laboratório de circuitos elétricos e eletrónicos

## Pré-requisitos

- Node.js ≥ 20 (inclui Corepack)
- pnpm 10 via Corepack — versão fixada em `packageManager` no `package.json` raiz

O repositório é um monorepo pnpm (`apps/web`, `packages/*`) com um único lockfile `pnpm-lock.yaml`. Não usar npm nem yarn. O backend Python (`apps/api`) não pertence ao workspace pnpm.

## Comandos iniciais

```bash
corepack enable          # disponibiliza o comando pnpm (necessário para os scripts raiz)
pnpm install

pnpm dev                 # arranca os pacotes do workspace em paralelo
pnpm build
pnpm lint
pnpm format
pnpm test
```

Sem `corepack enable` é possível usar `corepack pnpm@10 install`, mas os scripts raiz precisam do comando `pnpm` no PATH.

Ver `Docs/arquitetura_simulador_circuitos.md` para a arquitetura e o plano de desenvolvimento.
