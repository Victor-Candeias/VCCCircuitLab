---
maestru: "0.4"
type: work-spec
id: e5-08-spec
title: "E5-08 — Plano do registo de utilizadores"
template: implementation-plan-v1
work-item: etapa-5/E5-08
owner: developer
created: 2026-10-14
---

# E5-08 — Plano do registo de utilizadores

## Overview

Criar contas de utilizador gravadas no MongoDB com os dados protegidos, e uma janela "Criar conta" no frontend com barra de qualidade da password. Depende da ligação à BD (E5-07, feita no mesmo trabalho).

Decisões:
- **Password:** nunca é encriptada nem guardada; fica só um hash scrypt com sal aleatório (N=2^15, r=8, p=1). Um hash não se desencripta, o que é o desejado para passwords.
- **Nome e email:** encriptados com Fernet (AES-128-CBC + HMAC), chave em `DATA_ENCRYPTION_KEY` (só em `.env`, ignorado pelo git).
- **Unicidade do email:** `emailIndex` = HMAC-SHA256 do email em minúsculas, com chave derivada da chave principal e índice único. Permite recusar duplicados sem guardar o email em claro.
- **Qualidade da password (0–4):** igual no backend (`password_level`) e no frontend (`passwordLevel`), com os mesmos casos de teste. O registo exige nível ≥ 2. A barra vai de vermelho a verde.
- **Erros:** `application/problem+json` (409 email já registado, 422 dados inválidos com `pointer`, 503 BD indisponível sem expor a causa).
- O CRUD genérico de collections (`app/db/collections.py`) não é exposto por HTTP.

## Implementation

1. `app/db/` — `mongo.py` (cliente único a partir do `.env`), `collections.py` (criar/ler/alterar/apagar), `errors.py`.
2. `app/security/` — `crypto.py` (Fernet + índice cego) e `passwords.py` (scrypt e nível da password).
3. `app/models/user.py`, `app/users/` (serviço e erro) e `app/routes/users.py` (`POST /api/v1/users` → 201).
4. `app/problems.py` — handlers 409 e 503 e título "Dados inválidos" nos erros de `/api/v1/users`.
5. Frontend: `src/auth/passwordStrength.ts`, `RegisterDialog.tsx` (inclui a barra), `createUser` em `api/client.ts` e botão "Criar conta" na `App`.
6. Testes: API (collections com mongomock, segurança, endpoint) e web (nível, barra, diálogo, cliente, App). Verificação manual contra o MongoDB local: documento gravado só com campos encriptados.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/db/*` | create | Ligação ao MongoDB e CRUD de collections |
| `apps/api/app/security/*` | create | Encriptação de campos e hash/qualidade de passwords |
| `apps/api/app/models/user.py`, `app/users/*`, `app/routes/users.py` | create | Endpoint de criação de utilizador |
| `apps/api/app/problems.py`, `app/main.py` | update | Novos erros e router |
| `apps/api/requirements*.txt` | update | pymongo, cryptography, python-dotenv, mongomock (dev) |
| `.env.example` | create | Variáveis necessárias (sem segredos) |
| `apps/web/src/auth/*` | create | Qualidade da password e diálogo de registo |
| `apps/web/src/api/{client,types}.ts`, `App.tsx` | update | `createUser` e botão "Criar conta" |
