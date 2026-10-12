---
maestru: "0.4"
type: work-spec
id: e0-04-spec
title: "E0-04 — Plano de implementação de apps/api"
template: implementation-plan-v1
work-item: etapa-0/E0-04
owner: developer
created: 2026-10-12
---

# E0-04 — Plano de implementação de apps/api

## Overview

Criar o backend Python em `apps/api` (fora do workspace pnpm) com FastAPI, a estrutura de pacotes da `Docs/arquitetura_simulador_circuitos.md` §9, o endpoint `GET /health` (§8) e dependências com versões fixadas (§13).

## Implementation

### Fase 1 — Estrutura

1. `apps/api/app/` com subpacotes `routes`, `models`, `generation`, `circuit`, `solver` e `export` (cada um com `__init__.py`).
2. `app/main.py` exporta `app = FastAPI(...)` e inclui o router de health.

### Fase 2 — Health check

1. `app/routes/health.py`: `GET /health` → `{"status": "ok"}` com modelo Pydantic `HealthResponse`.
2. `tests/test_health.py` com `fastapi.testclient.TestClient`.

### Fase 3 — Dependências e configuração

1. `requirements.txt` (execução): `fastapi`, `pydantic`, `uvicorn[standard]` fixados.
2. `requirements-dev.txt`: `-r requirements.txt`, `pytest`, `httpx2` (a Starlette 1.x depreca `httpx` no TestClient).
3. `pyproject.toml` com `requires-python >= 3.12` e configuração do pytest (`pythonpath`, `testpaths`).
4. `apps/api/README.md` com comandos de venv, arranque e testes.

### Verificação

- `pytest apps/api -W error` passa num venv limpo instalado de `requirements-dev.txt`.
- `uvicorn app.main:app --app-dir apps/api` responde `{"status":"ok"}` em `/health`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/**/__init__.py` | create | Pacotes da arquitetura |
| `apps/api/app/main.py` | create | Aplicação FastAPI |
| `apps/api/app/routes/health.py` | create | `GET /health` |
| `apps/api/tests/test_health.py` | create | Teste do health check |
| `apps/api/requirements.txt` | create | Dependências de execução fixadas |
| `apps/api/requirements-dev.txt` | create | Dependências de teste fixadas |
| `apps/api/pyproject.toml` | create | Metadados e configuração do pytest |
| `apps/api/README.md` | create | Instruções do backend |
