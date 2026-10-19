---
maestru: "0.4"
type: work-spec
id: e5-05-spec
title: "E5-05 — Monitorização, logs e health check"
template: implementation-plan-v1
work-item: etapa-5/E5-05
owner: developer
created: 2026-10-19
---

# E5-05 — Monitorização, logs e health check

## Overview

Dar visibilidade operacional à API em produção (§13): logs de pedidos e métricas **sem dados
sensíveis** (sem corpos, tokens, emails, query strings nem IPs), um health check de prontidão
que verifica o MongoDB, e monitorização periódica do health check no servidor Debian.

## Implementation

### Phase 1: Logs e métricas

| Action | File | Details |
|---|---|---|
| Create | `apps/api/app/observability.py` | `ObservabilityMiddleware` (ASGI puro): `X-Request-ID` (aceita o do proxy se for seguro, senão gera), log `app.access` numa linha `key=value` (`request_id method route status duration_ms`; rota = template, ex. `/api/v1/templates/{template_id}`, sem query string nem IP). `Metrics` em memória, formato Prometheus: `http_requests_total{method,route,status}`, `http_request_duration_seconds` (histograma), `http_requests_in_progress`, `process_uptime_seconds`. `configure_logging()` com `LOG_LEVEL`. |
| Create | `apps/api/app/routes/metrics.py` | `GET /metrics` (texto Prometheus) protegido por `Authorization: Bearer <METRICS_TOKEN>` (comparação em tempo constante); sem `METRICS_TOKEN` responde 404. |
| Modify | `apps/api/app/routes/health.py` | `GET /health` (liveness, inalterado) e `GET /health/ready` (readiness: `ping` ao MongoDB → 200 / 503, sem detalhes do erro). |
| Modify | `apps/api/app/main.py`, `app/http_security.py` | Instalar o middleware (por fora de tudo, para medir também 413/429) e isentar `/health/ready` e `/metrics` do rate limiting. |

### Phase 2: Operação

| Action | File | Details |
|---|---|---|
| Create | `deploy/healthcheck.sh`, `deploy/vcccircuitlab-healthcheck.{service,timer}` | A cada minuto: `/health` falha → `docker compose restart api`; `/health/ready` falha → aviso no journal. |
| Modify | `apps/api/Dockerfile` | `--no-access-log` (o access log do uvicorn tem IP e query string; passa a ser o `app.access`). |
| Modify | `docker-compose.yml`, `.env.example`, `apps/api/README.md` | `LOG_LEVEL`, `METRICS_TOKEN` e documentação. |

### Phase 3: Testes

| Action | File | Details |
|---|---|---|
| Create | `apps/api/tests/test_observability.py` | Request ID, log sem dados sensíveis (sem token/email/query), métricas por template de rota, `/metrics` com/sem token, `/health/ready` com BD ok/indisponível. |

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/observability.py` | Create | Logs, request ID e métricas |
| `apps/api/app/routes/metrics.py` | Create | Endpoint de métricas |
| `apps/api/app/routes/health.py` | Modify | Readiness |
| `apps/api/app/main.py` | Modify | Instalação |
| `apps/api/app/http_security.py` | Modify | Isenções do rate limiting |
| `apps/api/tests/test_observability.py` | Create | Testes |
| `deploy/*` | Create | Monitorização do health check |
| `apps/api/Dockerfile`, `docker-compose.yml`, `.env.example`, `apps/api/README.md` | Modify | Configuração e documentação |
