# @vcccircuitlab/web

Frontend do VCCCircuitLab: React + TypeScript + Vite.

## Comandos (a partir da raiz do repositório)

```bash
pnpm install
pnpm --filter @vcccircuitlab/web dev       # servidor de desenvolvimento
pnpm --filter @vcccircuitlab/web build     # tsc -b + vite build → apps/web/dist
pnpm --filter @vcccircuitlab/web lint
pnpm --filter @vcccircuitlab/web preview
```

## GitHub Pages

O `base` do Vite é `/VCCCircuitLab/` por omissão (site servido em `https://<utilizador>.github.io/VCCCircuitLab/`).
Para um domínio próprio na raiz, definir `BASE_PATH=/` no build.
