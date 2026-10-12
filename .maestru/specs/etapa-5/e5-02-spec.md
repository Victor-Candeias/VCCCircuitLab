---
maestru: "0.4"
type: work-spec
id: e5-02-spec
title: "E5-02 — Plano de containerização da API"
template: implementation-plan-v1
work-item: etapa-5/E5-02
owner: developer
created: 2026-10-12
---

# E5-02 — Plano de containerização da API

## Overview

Empacotar a API FastAPI numa imagem Docker que corre com um utilizador não privilegiado, e acrescentar um `docker-compose.yml` na raiz com endurecimento de segurança. Referência: arquitetura §9 e §13.

Decisões:
- Uvicorn sem Gunicorn: evita uma dependência extra. O número de processos fica configurável com `UVICORN_WORKERS` (no compose, `API_WORKERS`).
- Build em duas fases sobre `python:3.12-slim`: venv em `/opt/venv` instalado só a partir de `requirements.txt`. O contexto é `apps/api`, e o `.dockerignore` em lista branca deixa entrar apenas `app/` e `requirements.txt`.
- O utilizador `app` (uid/gid 10001) não tem shell nem home. O código pertence a root e é só de leitura para o processo.
- `HEALTHCHECK` em Python (urllib) a `GET /health`, sem curl na imagem. Uvicorn com `--no-server-header`.
- Compose:
  - porta publicada só em `127.0.0.1` (o acesso externo passa por proxy HTTPS ou tunnel);
  - `read_only`, com tmpfs `/tmp`;
  - `cap_drop: ALL` e `no-new-privileges`;
  - `init`;
  - limites `pids`/`mem`/`cpus`;
  - rotação de logs;
  - `restart: unless-stopped`.

## Implementation

1. `apps/api/Dockerfile` (fases build e runtime) e `apps/api/.dockerignore`.
2. `docker-compose.yml` na raiz (serviço `api`, imagem `vcccircuitlab-api:local`, variáveis `API_PORT` e `API_WORKERS`).
3. Validação com Docker 29 (WSL): `docker compose config`, build, `up`.
   - Estado `healthy`; `GET /health` devolve 200 sem cabeçalho `Server`.
   - Dentro do contentor: `id` = 10001, escrita em `/srv/api` recusada (só de leitura), `/tmp` gravável, `CapEff` = 0 e `NoNewPrivs` = 1.
   - `API_WORKERS=2` arranca 2 workers; a porta fica ligada a 127.0.0.1.
4. Documentação: README raiz (secção "API em Docker") e README da API (secção "Imagem Docker").

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/Dockerfile` | create | Imagem não privilegiada da API |
| `apps/api/.dockerignore` | create | Contexto de build mínimo |
| `docker-compose.yml` | create | Execução endurecida da API |
| `README.md` | update | Instruções Docker |
| `apps/api/README.md` | update | Descrição da imagem |