---
maestru: "0.4"
type: work-spec
id: e5-04-spec
title: "E5-04 — Segurança operacional da API"
template: implementation-plan-v1
work-item: etapa-5/E5-04
owner: developer
created: 2026-10-19
---

# E5-04 — Segurança operacional da API

## Overview

Endurecer a API para exposição pública (§12 teste 12, §13): CORS restrito ao domínio do
frontend, rate limiting por IP, limite de tamanho do corpo dos pedidos, timeout de simulação
(já existente: `SIMULATION_TIMEOUT_S`) e garantia de que nenhum dado do cliente é executado
como código. Tudo configurável por variáveis de ambiente, com valores por omissão seguros.

## Implementation

### Phase 1: Middlewares de segurança

| Action | File | Details |
|---|---|---|
| Create | `apps/api/app/http_security.py` | `SecuritySettings.from_env()` (`CORS_ALLOWED_ORIGINS`, `MAX_REQUEST_BODY_BYTES`=1 MiB, `RATE_LIMIT_PER_MINUTE`=120, `AUTH_RATE_LIMIT_PER_MINUTE`=20; 0 desativa). `BodySizeLimitMiddleware` (ASGI puro: `Content-Length` acima do limite → 413 imediato; corpos em streaming contados ao ler → 413). `RateLimitMiddleware` (janela deslizante de 60 s por IP e por grupo: `auth` = `POST /api/v1/auth/login` e `POST /api/v1/users`, `api` = resto; `/health` e `OPTIONS` isentos; 429 com `Retry-After`). `install_security(app)` adiciona, de fora para dentro: CORS → rate limit → limite de corpo. Respostas 413/429 em `application/problem+json` (`PAYLOAD_TOO_LARGE`, `RATE_LIMITED`). |
| Modify | `apps/api/app/main.py` | Chamar `install_security(app)`. |
| Modify | `apps/api/app/problems.py` | Novos códigos `PAYLOAD_TOO_LARGE` e `RATE_LIMITED`. |

### Phase 2: Proxy, deploy e documentação

| Action | File | Details |
|---|---|---|
| Modify | `docker-compose.yml` | `CORS_ALLOWED_ORIGINS` e limites por variável; `UVICORN_FORWARDED_ALLOW_IPS` para o IP real do cliente chegar via `X-Forwarded-For` (porta só publicada em loopback). |
| Modify | `apps/web/playwright.config.ts` | Limite de autenticação alto no backend dos E2E (cada teste regista/inicia sessão). |
| Modify | `apps/api/README.md` | Secção "Segurança operacional". |

### Phase 3: Testes

| Action | File | Details |
|---|---|---|
| Create | `apps/api/tests/test_http_security.py` | CORS (origem permitida/recusada, preflight), 413 por `Content-Length` e por streaming, 429 com `Retry-After` e isenção de `/health`, grupo `auth` separado, e dados com aparência de código tratados como dados (template desconhecido → 422). |
| Modify | `apps/api/tests/conftest.py` | Repor o estado do rate limiter entre testes. |

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/http_security.py` | Create | CORS, limite de corpo e rate limiting |
| `apps/api/app/main.py` | Modify | Instalar os middlewares |
| `apps/api/app/problems.py` | Modify | Códigos de erro 413/429 |
| `apps/api/tests/test_http_security.py` | Create | Testes |
| `apps/api/tests/conftest.py` | Modify | Isolamento do rate limiter |
| `docker-compose.yml` | Modify | Configuração de produção |
| `apps/web/playwright.config.ts` | Modify | Limites nos E2E |
| `apps/api/README.md` | Modify | Documentação |
