---
maestru: "0.4"
type: work-spec
id: e5-09-spec
title: "E5-09 Janela de login — plano de implementação"
template: implementation-plan-v1
work-item: etapa-5/E5-09
owner: developer
created: 2026-10-14
---

# E5-09 Janela de login — plano de implementação

## Overview

Sem sessão iniciada a aplicação mostra apenas o ecrã de login, e a API recusa os pedidos de circuitos e componentes. Autentica contra os utilizadores do E5-08.

Decisões:
- **Token de sessão opaco**, não JWT: `secrets.token_urlsafe(32)` entregue ao cliente. Na collection `sessions` fica apenas o SHA-256 (`tokenHash`, índice único), com `userId`, `createdAt` e `expiresAt`. Logout e expiração ficam imediatos no servidor.
- **Expiração:** `SESSION_TTL_HOURS` (por omissão 8 h). Um índice TTL em `expiresAt` faz o MongoDB apagar as sessões; a API também recusa as expiradas enquanto não forem apagadas.
- **Login sem fugas de informação:** a resposta é igual (`401 invalid-credentials`, "Email ou password incorretos.") quer o email exista ou não. Sem utilizador, a API verifica um hash scrypt fictício, para o tempo de resposta não revelar se o email está registado.
- **Proteção:**
  - A dependência `require_user` (Bearer) é aplicada aos routers de circuitos e componentes.
  - Ficam públicos `/health`, `POST /api/v1/users` e `POST /api/v1/auth/login`.
  - Sem token, a resposta é `401 not-authenticated` com `WWW-Authenticate: Bearer`, sem tocar na BD.
- **Frontend:**
  - O token fica no `sessionStorage`: sobrevive a um refresh e termina ao fechar o separador.
  - Ao arrancar, a sessão é validada com `GET /auth/me`.
  - Um `401` num pedido feito com sessão volta ao login com o aviso de sessão expirada.
  - Não há rota nova: a mesma URL mostra o login ou o editor.
- **Fora de âmbito:**
  - Limitar tentativas de login repetidas (E5-04).
  - Autosave separado por utilizador.
  - Proteger `/docs`.

## Implementation

1. `app/auth/`:
   - `errors.py`;
   - `sessions.py` (criar, validar e apagar sessões);
   - `service.py` (`authenticate`, `to_user_out`);
   - `dependencies.py` (`require_user`, `CurrentUser`).
2. `app/routes/auth.py`:
   - `POST /api/v1/auth/login` → `{ accessToken, tokenType, expiresAt, user }`;
   - `GET /api/v1/auth/me`;
   - `POST /api/v1/auth/logout` → 204.
3. `app/problems.py`: handlers 401 (`invalid-credentials`, `not-authenticated`) e o título "Dados inválidos" também em `/api/v1/auth`. `app/main.py` passa a proteger os routers.
4. Testes da API:
   - `tests/conftest.py` substitui `require_user` por um utilizador falso, exceto nos testes `real_auth`;
   - `tests/test_api_auth.py` cobre login, `/me`, expiração, logout, rotas protegidas e o hash do token.
5. Frontend:
   - `api/client.ts`: `requestJson` com GET ou POST e o header `Authorization`, `setAuthToken`, `setUnauthorizedHandler`, `login`, `getCurrentUser`, `logoutSession`;
   - `auth/authStore.ts` (zustand);
   - `auth/LoginScreen.tsx` (com "Criar conta", que pré-preenche o email);
   - `App.tsx` mostra o portão de login e, no cabeçalho, o nome do utilizador e "Terminar sessão".
6. E2E:
   - `e2e/auth.ts` regista e autentica o utilizador de teste e injeta o token antes de cada cenário;
   - `e2e/login.spec.ts` testa o ecrã de login.
7. Verificação manual na rede local (IP da máquina, através do proxy do `vite dev`):
   - 401 sem token;
   - registo → login → `/me` → acesso aos componentes → logout → 401.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/auth/*` | create | Sessões, autenticação e `require_user` |
| `apps/api/app/routes/auth.py` | create | Endpoints de login, `/me` e logout |
| `apps/api/app/problems.py`, `app/main.py` | update | Erros 401 e routers protegidos |
| `apps/api/tests/conftest.py`, `tests/test_api_auth.py`, `pyproject.toml` | create/update | Utilizador falso por omissão, marcador `real_auth`, testes de autenticação |
| `apps/web/src/api/client.ts` | update | Token Bearer, handler de 401 e funções de sessão |
| `apps/web/src/auth/{authStore.ts,LoginScreen.tsx,auth.css}` | create/update | Estado da sessão e ecrã de login |
| `apps/web/src/auth/RegisterDialog.tsx` | update | `onCreated` para pré-preencher o email no login |
| `apps/web/src/App.tsx` | update | Portão de login e "Terminar sessão" |
| `apps/web/e2e/auth.ts`, `e2e/login.spec.ts`, `e2e/*.spec.ts` | create/update | Sessão automática nos cenários E2E |
| `apps/{api,web}/README.md`, `.env.example` | update | Documentação e `SESSION_TTL_HOURS` |
