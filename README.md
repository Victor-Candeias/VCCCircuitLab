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

### Arrancar API + frontend acessíveis na rede (Linux)

```bash
./start.sh     # API (uvicorn) + frontend (vite dev) em segundo plano; mostra os URLs
./stop.sh      # para ambos
```

O frontend escuta em todas as interfaces (`http://<IP-da-máquina>:5173/VCCCircuitLab/`) e encaminha `/api` para a API, que só escuta em `127.0.0.1:8000` (não fica exposta diretamente). Requer o venv em `apps/api/.venv`, `pnpm install` feito e o `.env` configurado. Logs e PIDs em `.run/` (ignorado pelo git). Variáveis opcionais: `WEB_PORT`, `API_PORT` e `API_HOST` (`0.0.0.0` expõe também a API). Se houver firewall, abrir a porta 5173.

### API em Docker

```bash
docker compose up -d --build     # http://127.0.0.1:8000/health
docker compose ps                # estado (healthy) do health check
docker compose down
```

O `docker-compose.yml` constrói `apps/api/Dockerfile` e corre a API como utilizador não privilegiado (uid 10001). O sistema de ficheiros é só de leitura (exceto `/tmp` em tmpfs), sem capabilities e com `no-new-privileges`, limites de memória, CPU e PIDs, health check e `restart: unless-stopped`. A porta só é publicada em `127.0.0.1`; o acesso externo deve passar por um reverse proxy HTTPS ou Cloudflare Tunnel. As variáveis `API_PORT` (8000) e `API_WORKERS` (1) permitem ajustar a porta e o número de processos.

Monitorização (E5-05): `GET /health/ready` verifica o MongoDB, `GET /metrics` expõe métricas Prometheus (com `METRICS_TOKEN`) e os logs não incluem dados sensíveis. O timer systemd `deploy/vcccircuitlab-healthcheck.timer` verifica a API a cada minuto e reinicia-a se `/health` falhar (ver [`apps/api`](apps/api/README.md#observabilidade-e5-05)).

Motor de simulação (F2-01): por omissão a API usa o solver MNA interno. Com `SIMULATION_ENGINE=ngspice` usa o ngspice, num processo isolado e com limites. Neste caso a imagem é construída com `WITH_NGSPICE=true` (ver [`apps/api`](apps/api/README.md#motor-ngspice-f2-01)).

Análises (F2-02): ponto de funcionamento DC e análise transitória (condensadores e bobinas, resposta ao degrau em t = 0), escolhidas no painel de simulação. A transitória mostra um gráfico das tensões e correntes e os valores finais (ver [`apps/api`](apps/api/README.md#análise-transitória-f2-02)). O exemplo «Carga de um condensador (RC)» do menu Projeto mostra a carga de um condensador.

Instrumentos virtuais (F2-03): voltímetro, amperímetro e osciloscópio ideais, no grupo «Instrumentos» da paleta. Depois de simular, a leitura aparece junto ao instrumento no canvas e na tabela «Instrumentos» do painel (valores finais na transitória). Na transitória, o gráfico abre no osciloscópio, com um traço por canal (tensão em relação à terra). O exemplo «Instrumentos: voltímetro, amperímetro e osciloscópio (RC)» do menu Projeto usa os três.

Semicondutores (F2-04): díodo, LED e transístores bipolares NPN e PNP, no grupo «Semicondutores» da paleta. Os modelos são os do SPICE: o díodo e o LED passam no ponto de condução do catálogo (`forwardVoltageV` a `forwardCurrentA`) e o transístor usa `currentGain` e `saturationCurrentA`. O solver resolve-os pelo método de Newton-Raphson, em DC e na transitória (detalhes em [`apps/api/README.md`](apps/api/README.md)). O exemplo «Transístor NPN a comandar um LED» do menu Projeto liga o LED com o interruptor S1.

Netlists SPICE (F2-05): no menu Projeto, «Exportar SPICE» descarrega o circuito como netlist `.cir` (legível pelo ngspice) e «Importar SPICE…» abre uma netlist com elementos R, C, L, V/I DC, D e Q. Uma netlist exportada pelo VCCCircuitLab e não editada reabre o circuito original, com o mesmo desenho. As outras são desenhadas numa grelha e mostram avisos para o que foi ignorado ou aproximado. Os elementos não suportados dão erro com o número da linha (detalhes em [`apps/api/README.md`](apps/api/README.md#importaçãoexportação-spice-f2-05)).

Geração por texto livre (F2-06): em «Gerar…», o modo «Texto livre» aceita uma descrição em português, por exemplo «divisor de tensão de 9 V com 10k e 4,7k». A API interpreta-a com um parser de intenções determinístico (sem LLM nem serviços externos) e valida o resultado com o schema do template e as regras elétricas. Antes de abrir o circuito no editor, o diálogo mostra o resumo, os valores assumidos e uma pré-visualização (detalhes em [`apps/api/README.md`](apps/api/README.md#geração-por-linguagem-natural-f2-06)).

Mais detalhes em [`apps/web`](apps/web/README.md), [`apps/api`](apps/api/README.md) e [`packages/circuit-schema`](packages/circuit-schema/README.md).

## Documentação

- [Arquitetura e plano de desenvolvimento](Docs/arquitetura_simulador_circuitos.md)
- [Decisões de arquitetura (ADRs)](Docs/adr/README.md)

## Licença

[MIT](LICENSE)
