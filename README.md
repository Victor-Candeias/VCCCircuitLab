# VCCCircuitLab

Laboratório de circuitos elétricos e eletrónicos: aplicação web para **desenhar, gerar, editar, validar e simular** circuitos, com um editor manual e um gerador automático em Python que partilham o mesmo modelo canónico JSON.

> **Aviso:** os resultados de simulação são educativos e aproximados; não substituem projeto, inspeção ou ensaios de instalações reais por profissionais qualificados.

## Estrutura

```text
apps/web/                  # Frontend React + Vite + TypeScript
apps/api/                  # Backend Python + FastAPI (fora do workspace pnpm)
packages/circuit-schema/   # JSON Schema 1.0 do circuito e tipos TS
Docs/                      # Arquitetura e ADRs
```

## Pré-requisitos

- Node.js ≥ 20 (inclui Corepack)
- pnpm 10 via Corepack — versão fixada em `packageManager` no `package.json` raiz
- Python ≥ 3.12 (backend)

O repositório é um monorepo pnpm (`apps/web`, `packages/*`) com um único lockfile `pnpm-lock.yaml`. Não usar npm nem yarn.

## Instalação

### Frontend e pacotes partilhados

```bash
corepack enable          # disponibiliza o comando pnpm (necessário para os scripts raiz)
pnpm install
```

Sem `corepack enable` é possível usar `corepack pnpm@10 install`, mas os scripts raiz precisam do comando `pnpm` no PATH.

### Backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1            # Linux: source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt
```

## Desenvolvimento

```bash
pnpm dev                 # frontend em http://localhost:5173/VCCCircuitLab/
pnpm build
pnpm lint                # ESLint (apps/web)
pnpm format              # Prettier em todo o workspace JS/TS/JSON/CSS
pnpm format:check        # verificação sem escrever (para CI)
pnpm test                # Vitest + Testing Library (apps/web) e node:test (packages/circuit-schema)

uvicorn app.main:app --app-dir apps/api --reload   # API em http://127.0.0.1:8000/health
pytest apps/api
ruff check apps/api      # lint Python
ruff format apps/api     # formatação Python
```

Configuração: Prettier em `.prettierrc.json`/`.prettierignore` (Markdown, `.maestru/`, `Docs/`, `apps/api/` e tipos gerados ficam de fora); ESLint em `apps/web/eslint.config.js` (com `eslint-config-prettier`); ruff em `apps/api/pyproject.toml`.

### API em Docker

```bash
docker compose up -d --build     # http://127.0.0.1:8000/health
docker compose ps                # estado (healthy) do health check
docker compose down
```

O `docker-compose.yml` constrói `apps/api/Dockerfile` e corre a API como utilizador não privilegiado (uid 10001). O sistema de ficheiros é só de leitura (exceto `/tmp` em tmpfs), sem capabilities e com `no-new-privileges`, limites de memória, CPU e PIDs, health check e `restart: unless-stopped`. A porta só é publicada em `127.0.0.1`; o acesso externo deve passar por um reverse proxy HTTPS ou Cloudflare Tunnel. As variáveis `API_PORT` (8000) e `API_WORKERS` (1) permitem ajustar a porta e o número de processos.

Mais detalhes em [`apps/web`](apps/web/README.md), [`apps/api`](apps/api/README.md) e [`packages/circuit-schema`](packages/circuit-schema/README.md).

## Documentação

- [Arquitetura e plano de desenvolvimento](Docs/arquitetura_simulador_circuitos.md)
- [Decisões de arquitetura (ADRs)](Docs/adr/README.md)

## Licença

[MIT](LICENSE)
