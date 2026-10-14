---
maestru: "0.4"
type: work-spec
id: e2-05-spec
title: "E2-05 — Plano dos endpoints /validate e /simulate"
template: implementation-plan-v1
work-item: etapa-2/E2-05
owner: developer
created: 2026-10-14
---

# E2-05 — Plano dos endpoints /validate e /simulate

## Overview

Este item expõe o validador (E2-02) e o solver DC (E2-03) por HTTP (arquitetura §8). Todas as respostas de erro da API passam a usar `application/problem+json` (RFC 9457).

Endpoints, cujo corpo é sempre o documento canónico (`CircuitDocument`):

- **`POST /api/v1/circuits/validate`** devolve `200` com um relatório: `{ valid, errors[], warnings[], nets[] | null }`. Os erros de circuito (topologia, valores, terminais) fazem parte da resposta e não são erros HTTP, porque validar é o objetivo do pedido. `nets` traz a partição em redes quando a normalização foi possível, para o editor poder destacar as redes (E2-07).
- **`POST /api/v1/circuits/simulate`** devolve `200` com o resultado DC no formato da §8 (`DcResult.to_json_dict()`). Se o circuito não for simulável, devolve problem+json.

Formato problem+json:

```json
{
  "type": "urn:vcccircuitlab:problem:invalid-circuit",
  "title": "Circuito inválido",
  "status": 422,
  "detail": "A rede N3 não tem caminho condutor até à terra.",
  "instance": "/api/v1/circuits/simulate",
  "code": "FLOATING_NET",
  "errors": [{ "code": "FLOATING_NET", "message": "…", "refs": ["N3"] }]
}
```

- `code` é o código do primeiro erro. `errors` lista todos os erros, cada um com `code`, `message`, `refs` e, nos erros de esquema, `pointer` (JSON Pointer, RFC 6901).
- `detail` é a mensagem do primeiro erro, ou um resumo quando há vários.

| `type` (sufixo) | HTTP | Códigos |
|---|---|---|
| `malformed-json` | 400 | `MALFORMED_JSON` |
| `about:blank` | 415 | `UNSUPPORTED_MEDIA_TYPE` (corpo que não é `application/json` nem `*+json`) |
| `invalid-document` | 422 | `INVALID_DOCUMENT`; `INVALID_COMPONENT` (erro de esquema dentro de `components[i]`, com `refs: [id]`) |
| `invalid-circuit` | 422 | Códigos do validador: `UNKNOWN_TERMINAL`, `FLOATING_NET`, `UNSUPPORTED_MODEL`, `INVALID_VALUE`, … |
| `simulation-failed` | 422 | `SINGULAR_MATRIX`, `ILL_CONDITIONED_MATRIX` |
| `simulation-timeout` | 503 | `SIMULATION_TIMEOUT` |
| `about:blank` | 404, 405, … | Nome do estado HTTP (`NOT_FOUND`, `METHOD_NOT_ALLOWED`) |
| `internal-error` | 500 | `INTERNAL_ERROR` (sem detalhes internos) |

Decisões:

- O corpo é declarado como `CircuitDocument`, para o OpenAPI ter o esquema. Os erros de `RequestValidationError` são convertidos em problem+json: `json_invalid` dá 400, e os restantes dão 422 com JSON Pointer. Os erros repetidos no mesmo ponteiro (alternativas de uma união, como `bool | number`) juntam-se num só, e as mensagens mais comuns são traduzidas para português.
- `NaN` e `Infinity` no JSON são rejeitados pelo modelo (`INVALID_COMPONENT`), cumprindo o teste 8 da §12.
- **Timeout:** o solver corre numa thread com `anyio.fail_after(SIMULATION_TIMEOUT_S)`, 5 s por omissão e configurável pela variável de ambiente `SIMULATION_TIMEOUT_S`. Esgotado o tempo, a resposta é `503 SIMULATION_TIMEOUT`, mas a thread não é interrompida. O isolamento em processo com limites de CPU e memória, o limite de payload, o rate limiting e o CORS ficam para o E5-04 e o F2-01.
- O catálogo é obtido no módulo de rotas (`load_catalog()`), para os testes o poderem substituir (`UNSUPPORTED_MODEL`).

## Implementation

1. `app/problems.py`: códigos da API (`ApiErrorCode`), modelo `Problem` (OpenAPI), `problem_response()`, conversão de `CircuitValidationError` e de `RequestValidationError`, e `install_problem_handlers(app)` (validação do pedido, `HTTPException` e exceções não tratadas).
2. `app/routes/circuits.py`: router `/api/v1/circuits` com `validate` e `simulate`, modelos de resposta (`ValidationResponse`, `SimulationResponse`) e timeout.
3. `app/main.py`: registar os handlers e o router.
4. `tests/test_api_circuits.py`: casos analíticos do E2-04 (`load_analytic_cases()`) pelos dois endpoints; erros de esquema (campo em falta ou extra, tipo errado, `NaN`/`Infinity`, JSON malformado, raiz que não é objeto, content-type errado); `UNSUPPORTED_MODEL` (catálogo substituído); `ILL_CONDITIONED_MATRIX`; timeout; 404 e 405; 500 sem fuga de detalhes; OpenAPI.
5. README da API: endpoints, formato problem+json e tabela de tipos.

Verificação: `pytest apps/api`, `ruff check apps/api`, `ruff format --check apps/api` e um pedido real com `uvicorn` e `curl`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/problems.py` | create | Respostas problem+json e handlers de exceções |
| `apps/api/app/routes/circuits.py` | create | Endpoints `/validate` e `/simulate` |
| `apps/api/app/main.py` | modify | Registar router e handlers |
| `apps/api/tests/test_api_circuits.py` | create | Testes HTTP |
| `apps/api/README.md` | modify | Documentação dos endpoints e dos erros |
