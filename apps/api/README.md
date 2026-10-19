# VCCCircuitLab API

Backend Python (FastAPI) do VCCCircuitLab. Não pertence ao workspace pnpm; as dependências estão fixadas em `requirements.txt` (execução) e `requirements-dev.txt` (testes e lint).

## Estrutura

```text
apps/api/
├── app/
│   ├── main.py        # app = FastAPI()
│   ├── problems.py    # Erros application/problem+json
│   ├── routes/        # Rotas HTTP (GET /health, /health/ready, /metrics, /api/v1/circuits/…, /api/v1/users, /api/v1/auth/…)
│   ├── models/        # Modelos Pydantic
│   ├── db/            # Ligação ao MongoDB e CRUD de collections
│   ├── security/      # Encriptação de campos, hash e qualidade de passwords
│   ├── users/         # Criação de utilizadores
│   ├── auth/          # Login, sessões e dependência require_user
│   ├── component_templates/  # CRUD da coleção `templates` (F2-10), só para admin
│   ├── generation/    # Templates e layout
│   ├── circuit/       # Redes, normalização, validação
│   ├── solver/        # MNA DC
│   └── export/        # Schemdraw e SVG
└── tests/
```

## Comandos (a partir da raiz do repositório)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1            # Linux: source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt

uvicorn app.main:app --app-dir apps/api --reload   # http://127.0.0.1:8000/health
pytest apps/api
ruff check apps/api                    # lint (pycodestyle, pyflakes, isort, pyupgrade, bugbear…)
ruff format apps/api                   # formatação (--check para verificar sem escrever)
```

Requer Python ≥ 3.12. Ferramentas de desenvolvimento em `requirements-dev.txt` (pytest, httpx2 para o `TestClient`, ruff); configuração em `pyproject.toml`.

## Modelo do circuito e normalização de redes

- `app/models/circuit.py`: `CircuitDocument` e os restantes modelos Pydantic espelham `packages/circuit-schema/schema/circuit.schema.json`. São estritos (sem campos extra, sem coerção de `"12"` para número, sem `inf`/`nan`) e imutáveis. Os nomes JSON (`schemaVersion`, `from`) são usados na entrada e na saída (`to_json_dict()`); em Python, `from` passa a `from_`.
- `app/circuit/normalize.py`: `normalize(doc)` usa union-find sobre os terminais `Componente.pino` e as junções ligados por fios, e devolve `NormalizedCircuit` com `nets` preenchido e o mapa `terminal_to_net`.
  - As junções servem só de ponte. Fios que se cruzam sem junção não ficam ligados, e um terminal sem fios forma uma rede própria.
  - Se o documento trouxer `nets`, a partição declarada tem de coincidir com a calculada (os IDs declarados mantêm-se). Sem `nets`, os IDs `N1`, `N2`, … são gerados de forma determinística e evitam colisões com outros IDs.
  - Os erros são lançados como `CircuitValidationError` com `UNKNOWN_TERMINAL`, `UNKNOWN_JUNCTION` ou `NET_INCONSISTENT` (`app/circuit/errors.py`). Cada erro inclui os `refs` envolvidos.

## Validação topológica e de valores

`app/circuit/validate.py`: `validate(doc)` devolve um `ValidationReport` com `errors`, `warnings` e `normalized` (o `NormalizedCircuit`, quando a normalização foi possível). Não lança exceções. `report.raise_for_errors()` lança `CircuitValidationError` se houver erros e, caso contrário, devolve o circuito normalizado; é a entrada prevista para o solver. Os problemas são todos recolhidos numa só passagem, por fases:

| Fase | Códigos |
|---|---|
| Documento | `DUPLICATE_ID` (IDs únicos entre componentes, junções, fios e redes), `SELF_LOOP_WIRE` (`from` = `to`) |
| Componentes vs catálogo | `UNKNOWN_COMPONENT_TYPE`, `UNSUPPORTED_MODEL`, `UNKNOWN_PIN`, `MISSING_PIN`, `UNKNOWN_PROPERTY`, `MISSING_PROPERTY`, `INVALID_PROPERTY_TYPE`, `INVALID_VALUE` (fora dos limites do catálogo: zero, negativos, acima do máximo, não finitos) |
| Normalização (sem IDs duplicados) | `UNKNOWN_TERMINAL`, `UNKNOWN_JUNCTION`, `NET_INCONSISTENT` |
| Topologia (com componentes interpretáveis) | `UNCONNECTED_PIN` (aviso), `MISSING_GROUND`, `VOLTAGE_SOURCE_LOOP`, `FLOATING_NET`, `CURRENT_SOURCE_CUTSET` |

- Na topologia, cada rede é um nó e a terra liga a sua rede a um nó de referência. Resistências e lâmpadas são condutoras. Interruptores fechados, fontes de tensão e terra têm impedância nula. Interruptores abertos e fontes de corrente não fixam potencial.
- `VOLTAGE_SOURCE_LOOP`: malha só de impedância nula que inclui uma fonte de tensão, como uma fonte em curto, fontes em paralelo ou uma fonte entre duas terras. Os `refs` dão a malha. As malhas só de interruptores ou de terras são aceites.
- `FLOATING_NET`: grupo de redes sem caminho condutor até à terra, porque o potencial fica indefinido. Se o grupo toca numa fonte de corrente, o erro é `CURRENT_SOURCE_CUTSET` (fonte em aberto ou fontes em série). Sem terra, só se reporta `MISSING_GROUND`.
- O catálogo é lido da coleção `templates` do MongoDB (`app/circuit/catalog.py::load_catalog()`, sem cache de processo), gerida por administradores (ver [Templates de componentes](#templates-de-componentes-f2-10)).

## Solver MNA DC

`app/solver/mna.py`: `simulate_dc(doc)` valida o circuito (lança `CircuitValidationError` se houver erros) e calcula o ponto de funcionamento DC por análise nodal modificada com NumPy. Devolve um `DcResult`; `to_json_dict()` produz o formato da arquitetura (§8):

```json
{
  "analysis": "dc_operating_point",
  "status": "success",
  "nodeVoltagesV": { "N_PLUS": 12, "N_GND": 0 },
  "components": {
    "V1": { "voltageV": 12, "currentA": -0.12, "powerW": -1.44 },
    "R1": { "voltageV": 12, "currentA": 0.12, "powerW": 1.44 }
  },
  "warnings": []
}
```

- **Modelos:** a resistência e a lâmpada são condutâncias (lâmpada: R = `ratedVoltageV`² / `ratedPowerW`). Um interruptor fechado é uma fonte de 0 V; um interruptor aberto não entra na matriz (sem R = 0 nem R = ∞). A fonte de corrente injeta `currentA` na rede de `positive`. Todas as redes com terra ficam a 0 V.
- **Sinais (convenção passiva, pinos pela ordem do catálogo):** `voltageV = V(pino1) − V(pino2)`. `currentA` entra pelo pino 1 e atravessa o componente. `powerW = voltageV × currentA` é a potência absorvida, negativa quando o componente fornece energia. A soma das potências é 0. A terra não tem resultado próprio.
- **Erros numéricos:** `SINGULAR_MATRIX` e `ILL_CONDITIONED_MATRIX` (número de condição > 1e12) são erros, para nunca devolver resultados falsos. Com o validador, só ocorrem com valores extremos (por exemplo, resistências de 1e-13 Ω).
- **Avisos:** os avisos do validador (por exemplo `UNCONNECTED_PIN`) passam para `warnings`.

### Testes com resultados analíticos

`tests/test_solver_analytic.py` corre os casos de `tests/fixtures/analytic/*.json` (arquitetura §7.1 e §12, testes 1–8) de ponta a ponta. Cada fixture tem `description`, `reference`, `circuit` e `expected`. Os valores esperados são calculados à mão e nunca a partir do solver.

- **Sucesso:** `expected` traz `nodeVoltagesV`, `components` e `warnings` (códigos). O circuito declara `nets` com nomes legíveis, para o normalizador confirmar também a partição esperada. Por exemplo, fios que se cruzam sem junção ficam em redes diferentes, e uma junção une todos os seus terminais.
- **Erro:** `expected.errors` lista os códigos, por ordem.
- **Verificações extra nos casos de sucesso:** KVL (`voltageV` = V(pino1) − V(pino2)), KCL por nó (as redes com terra formam um só nó), soma das potências igual a 0, valores finitos e sem `-0.0`.

Para acrescentar um caso, basta criar um novo ficheiro JSON. `load_analytic_cases()` (`tests/factories.py`) disponibiliza as mesmas fixtures a outros testes.

## Endpoints `/api/v1/circuits`

Exigem sessão iniciada (`Authorization: Bearer <token>`, ver [Sessão e autenticação](#sessão-e-autenticação)); sem ela a resposta é `401 not-authenticated`.

O corpo é sempre o documento canónico (`CircuitDocument`), enviado como `application/json`. A documentação interativa está em `/docs` e o esquema em `/openapi.json`.

| Método | Endpoint | Resposta `200` |
|---|---|---|
| `POST` | `/api/v1/circuits/generate` | Documento canónico gerado (`CircuitDocument`, com `nets` já calculado). Corpo: `{ template, parameters }` (ver [Geração por templates](#geração-por-templates)). |
| `POST` | `/api/v1/circuits/validate` | `{ valid, errors[], warnings[], nets[] \| null }`. Os erros de circuito fazem parte do relatório e não são erros HTTP. `nets` traz a partição em redes quando a normalização foi possível. |
| `POST` | `/api/v1/circuits/simulate` | Resultado DC (ver [Solver MNA DC](#solver-mna-dc)). |
| `GET` | `/api/v1/components` | Catálogo de componentes (E2-06): `{ catalogVersion, gridSize, components[] }`. Cada componente traz o schema completo de propriedades (`NumberPropertyDefinition`/`BooleanPropertyDefinition`, com `unit`, `default` e limites) e `supported` (`simulationModel !== null`), para clientes assinalarem componentes desenháveis mas não simuláveis. Fonte: coleção `templates` do MongoDB (ver [Templates de componentes](#templates-de-componentes-f2-10)); `catalogVersion`/`gridSize` são constantes (`app/circuit/catalog.py`). |

### Geração por templates

`POST /api/v1/circuits/generate` recebe `{ "template": "<nome>", "parameters": { … } }` e devolve o documento canónico correspondente, já normalizado (com `nets`). As posições e os fios (incluindo waypoints ortogonais, quando necessários para fechar a malha sem cruzar componentes) são calculados pelo algoritmo de layout (`app/generation/layout.py`), alinhado à grelha do editor (`gridSize` do catálogo). Os templates disponíveis (`app/generation/registry.py`, parâmetros em `app/generation/params.py`) são:

| `template` | Parâmetros (camelCase) |
|---|---|
| `series_dc` | `voltageV` (> 0), `resistorsOhm` (1 a 12 valores > 0) |
| `parallel_dc` | `voltageV` (> 0), `resistorsOhm` (1 a 12 valores > 0) |
| `voltage_divider` | `voltageV` (> 0), `resistorsOhm` (2 a 12 valores > 0) |
| `switch_circuit` | `voltageV` (> 0), `loadOhm` (> 0), `closed` (opcional, por omissão `true`) |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/circuits/generate \
  -H 'content-type: application/json' \
  --data '{"template": "series_dc", "parameters": {"voltageV": 12, "resistorsOhm": [100, 220]}}'
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/circuits/simulate \
  -H 'content-type: application/json' \
  --data @packages/circuit-schema/test/fixtures/valid/fonte-resistencia.json
```

A simulação tem um limite de tempo, `SIMULATION_TIMEOUT_S` (variável de ambiente, 5 s por omissão). O solver corre numa thread que não é interrompida: esgotado o tempo, a API só deixa de esperar por ela. O isolamento em processo, o limite de payload, o rate limiting e o CORS ficam para o E5-04.

## Templates de componentes (F2-10)

Coleção `templates` (MongoDB): fonte da verdade do catálogo de componentes, geríveis só por administradores (deixou de haver cópia estática em `app/circuit/data/`). O corpo tem os campos de um componente do catálogo (`type`, `label`, `category`, `idPrefix`, `symbol`, `size`, `pins`, `properties`, `simulationModel`; ver `app/models/component.py`, partilhado com `GET /api/v1/components`).

| Método | Endpoint | Acesso | Resposta |
|---|---|---|---|
| `GET` | `/api/v1/templates` | Qualquer sessão válida | `200 TemplateOut[]` |
| `GET` | `/api/v1/templates/{id}` | Qualquer sessão válida | `200 TemplateOut`, `404 template-not-found` |
| `POST` | `/api/v1/templates` | `ADMIN` (`CurrentAdmin`) | `201 TemplateOut`, `403 forbidden`, `409 template-type-already-exists`, `422 invalid-document` |
| `PUT` | `/api/v1/templates/{id}` | `ADMIN` (`CurrentAdmin`) | `200 TemplateOut`, `403 forbidden`, `404 template-not-found`, `409 template-type-already-exists`, `422 invalid-document` |
| `DELETE` | `/api/v1/templates/{id}` | `ADMIN` (`CurrentAdmin`) | `204`, `403 forbidden`, `404 template-not-found` |

`TemplateOut` acrescenta `id`, `createdAt`, `updatedAt` e `createdBy` (email do administrador). O campo `type` tem um índice único (`app/component_templates/service.py`): não pode haver dois templates para o mesmo tipo de componente.

`app/circuit/catalog.py::load_catalog()` lê a coleção a cada chamada (sem cache de processo), para que alterações de administradores (`POST`/`PUT`/`DELETE`) fiquem visíveis de imediato em `GET /api/v1/components` e na validação/simulação/geração de circuitos.

### Erros (`application/problem+json`, RFC 9457)

Todos os erros da API, incluindo 404, 405 e 500, usam o mesmo formato:

```json
{
  "type": "urn:vcccircuitlab:problem:invalid-circuit",
  "title": "Circuito inválido",
  "status": 422,
  "detail": "O circuito não tem terra (referência de 0 V): adicione um componente de terra.",
  "instance": "/api/v1/circuits/simulate",
  "code": "MISSING_GROUND",
  "errors": [{ "code": "MISSING_GROUND", "message": "…", "refs": [] }]
}
```

- `code` é o código do primeiro erro, e `errors` lista todos os erros.
- `refs` são os IDs ou terminais envolvidos, para o editor os poder destacar.
- Nos erros de esquema, `pointer` é o JSON Pointer (RFC 6901) do campo inválido.
- Os erros 500 nunca incluem detalhes internos.

| `type` | HTTP | `code` |
|---|---|---|
| `…:malformed-json` | 400 | `MALFORMED_JSON` |
| `about:blank` | 415 | `UNSUPPORTED_MEDIA_TYPE` (corpo que não é JSON) |
| `…:invalid-document` | 422 | `INVALID_COMPONENT` (erro de esquema em `components[i]`, com `refs: [id]`), `INVALID_DOCUMENT` (restantes, incluindo `NaN` e `Infinity`) |
| `…:unknown-template` | 422 | `UNKNOWN_TEMPLATE` (nome de `template` não existe no registo) |
| `…:invalid-parameters` | 422 | `INVALID_PARAMETERS` (campo em falta, extra ou fora dos limites, com `pointer` em `/parameters/…`) |
| `…:invalid-circuit` | 422 | Códigos do validador: `UNKNOWN_TERMINAL`, `FLOATING_NET`, `MISSING_GROUND`, `UNSUPPORTED_MODEL`, `INVALID_VALUE`, … |
| `…:simulation-failed` | 422 | `SINGULAR_MATRIX`, `ILL_CONDITIONED_MATRIX` |
| `…:invalid-credentials` | 401 | `INVALID_CREDENTIALS` (login com email ou password errados) |
| `…:not-authenticated` | 401 | `NOT_AUTHENTICATED` (sem token, ou token inválido, expirado ou terminado; com `WWW-Authenticate: Bearer`) |
| `…:forbidden` | 403 | `FORBIDDEN` (sessão válida sem o role necessário, ex.: não `ADMIN`) |
| `…:template-not-found` | 404 | `TEMPLATE_NOT_FOUND` (id de template inexistente) |
| `…:template-type-already-exists` | 409 | `TEMPLATE_TYPE_ALREADY_EXISTS` (já existe um template com o mesmo `type`) |
| `…:payload-too-large` | 413 | `PAYLOAD_TOO_LARGE` (corpo acima de `MAX_REQUEST_BODY_BYTES`) |
| `…:rate-limited` | 429 | `RATE_LIMITED` (com `Retry-After`, ver [Segurança operacional](#segurança-operacional-e5-04)) |
| `…:simulation-timeout` | 503 | `SIMULATION_TIMEOUT` |
| `about:blank` | 404, 405, … | Nome do estado HTTP (`NOT_FOUND`, `METHOD_NOT_ALLOWED`, …) |
| `…:internal-error` | 500 | `INTERNAL_ERROR` |

## Base de dados e utilizadores

Configuração em `.env` na raiz (ignorado pelo git; modelo em `.env.example`): `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_DATABASE`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`, `MONGODB_AUTH_SOURCE` e `DATA_ENCRYPTION_KEY` (chave Fernet; sem ela os dados encriptados não se recuperam). Dentro do contentor Docker o `127.0.0.1` é o próprio contentor, por isso é preciso passar estas variáveis e um `MONGODB_HOST` acessível.

- `app/db/mongo.py`: cliente único (`get_database()`), com timeout de 3 s. Sem configuração ou sem BD, a API responde `503 service-unavailable` sem expor a causa (fica no log).
- `app/db/collections.py`: CRUD genérico (`create_collection`, `drop_collection`, `list_collections`, `insert_one/many`, `find`, `find_one`, `update_many`, `delete_many`). Valida o nome da collection e não está exposto por HTTP.
- `POST /api/v1/users` (`{ name, email, password, passwordConfirm }` → `201 { id, name, email, role, createdAt }`): grava na collection `users` o nome e o email **encriptados** (Fernet), `emailIndex` (HMAC do email, índice único), `passwordHash` (scrypt com sal) e `role: "USER"` (o registo não aceita `role`). A password tem de ter qualidade ≥ 2 (≥ 8 caracteres com 3 classes de caracteres, ou ≥ 12 caracteres) e coincidir com `passwordConfirm`. Erros: `409 email-already-registered`, `422 invalid-document` (com `pointer`), `503 service-unavailable`.

## Sessão e autenticação

Públicos: `GET /health`, `GET /health/ready`, `POST /api/v1/users` e `POST /api/v1/auth/login`. Tudo o resto (`/api/v1/circuits/…`, `/api/v1/components`, `/api/v1/templates`) exige `Authorization: Bearer <token>` — dependência `require_user` (`app/auth/dependencies.py`), aplicada aos routers em `app/main.py`. A escrita em `/api/v1/templates` (`POST`/`PUT`/`DELETE`) exige ainda `role: "ADMIN"` (ver [Templates de componentes](#templates-de-componentes-f2-10)).

| Método | Endpoint | Resposta |
|---|---|---|
| `POST` | `/api/v1/auth/login` | `{ email, password }` → `200 { accessToken, tokenType: "bearer", expiresAt, user }`. Credenciais erradas → `401 invalid-credentials`, com a mesma mensagem e o mesmo custo (hash scrypt) quer o email exista ou não. |
| `GET` | `/api/v1/auth/me` | Utilizador da sessão (`{ id, name, email, role, createdAt }`, desencriptado). |
| `POST` | `/api/v1/auth/logout` | `204`; o token deixa de ser válido. |

- O token é aleatório (256 bits, `secrets.token_urlsafe`); na collection `sessions` fica apenas o seu SHA-256 (`tokenHash`, índice único), com `userId`, `createdAt` e `expiresAt`.
- Duração: `SESSION_TTL_HOURS` (por omissão 8 h). O índice TTL em `expiresAt` faz o MongoDB apagar as sessões expiradas; até lá, a API recusa-as.
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` (e `ADMIN_NAME`, opcional) no `.env` definem o administrador. Criar ou repor (idempotente; repõe `role: "ADMIN"` e a password) com `python -m app.users.seed_admin`, a partir de `apps/api`. A password do admin não passa pela política de qualidade do registo e nunca é guardada em claro.
- Roles: `USER` (registo) e `ADMIN` (só pelo seed). Contas sem `role` contam como `USER`. A dependência `CurrentAdmin` (`app/auth/dependencies.py`) responde `403 forbidden` (`FORBIDDEN`) a sessões sem role `ADMIN`.
- Nos testes, `tests/conftest.py` substitui `require_user` por um utilizador falso; os testes marcados com `@pytest.mark.real_auth` (ex.: `test_api_auth.py`) usam a autenticação real.
- Limitar tentativas de login repetidas fica para o E5-04. `/docs` e `/openapi.json` continuam públicos.

## Segurança operacional (E5-04)

Instalada em `app/http_security.py` (de fora para dentro: CORS → rate limiting → limite do corpo) e configurada por variáveis de ambiente, lidas no arranque:

| Variável | Omissão | Efeito |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | vazio | Origens autorizadas no browser, separadas por vírgulas (ex.: `https://utilizador.github.io`). Vazio = só a mesma origem (o `vite dev` usa proxy). Métodos `GET/POST/PUT/DELETE`, cabeçalhos `Authorization`, `Content-Type`, `Accept`, sem cookies. |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | Corpo acima do limite → `413 PAYLOAD_TOO_LARGE` (pelo `Content-Length` ou ao ler um corpo em streaming). |
| `RATE_LIMIT_PER_MINUTE` | `120` | Pedidos por minuto e por IP (janela deslizante) → `429 RATE_LIMITED` com `Retry-After`. |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `20` | Idem, contado à parte, para `POST /api/v1/auth/login` e `POST /api/v1/users` (força bruta). |
| `SIMULATION_TIMEOUT_S` | `5` | Tempo máximo de uma simulação → `503 SIMULATION_TIMEOUT`. |

- `0` desativa o limite correspondente. `/health`, `/health/ready`, `/metrics` e os preflight `OPTIONS` não contam para o rate limiting.
- O rate limiting é em memória e por processo (com `UVICORN_WORKERS=N` o limite efetivo é N×). O IP é o de `scope["client"]`: atrás de um reverse proxy, o uvicorn tem de confiar no `X-Forwarded-For` do proxy (`--proxy-headers`, ativo por omissão, e `FORWARDED_ALLOW_IPS`/`UVICORN_FORWARDED_ALLOW_IPS`); o `docker-compose.yml` já o configura.
- Nunca se executa código do cliente: não há `eval`/`exec`/`pickle` sobre dados recebidos; os templates de geração são procurados num registo fixo (`app/generation/registry.py`) e os parâmetros validados por Pydantic.

## Observabilidade (E5-05)

`app/observability.py` instala o middleware mais exterior (mede também os `413`/`429`):

- **Request ID:** cada resposta traz `X-Request-ID`. Um `X-Request-ID` recebido (ex.: do reverse proxy) é reutilizado se tiver 1–64 caracteres `[A-Za-z0-9._-]`; caso contrário gera-se um UUID.
- **Log de pedidos** (logger `app.access`, uma linha por pedido): `request_id=… method=GET route=/api/v1/templates/{template_id} status=200 duration_ms=12.3`. Regista-se o *template* da rota (`unmatched` se nenhuma corresponder), nunca o caminho concreto, a query string, o corpo, cabeçalhos, tokens, emails ou IPs. `/health`, `/health/ready` e `/metrics` não são registados. O nível dos loggers `app.*` define-se com `LOG_LEVEL` (por omissão `INFO`); a imagem Docker desliga o access log do uvicorn (`--no-access-log`), que incluiria IP e query string.
- **Métricas Prometheus** em `GET /metrics`, protegido por `Authorization: Bearer <METRICS_TOKEN>` (`401` se faltar ou estiver errado; `404` se `METRICS_TOKEN` não estiver definido): `http_requests_total{method,route,status}`, o histograma `http_request_duration_seconds{method,route}`, `http_requests_in_progress` e `process_uptime_seconds`. São em memória e por processo.

| Método | Endpoint | Resposta |
|---|---|---|
| `GET` | `/health` | Liveness: `200 {"status":"ok"}` sem consultar dependências. Usado pelo `HEALTHCHECK` da imagem e para reiniciar a API. |
| `GET` | `/health/ready` | Readiness: `ping` ao MongoDB → `200 {"status":"ok","checks":{"database":"ok"}}`, ou `503 {"status":"unavailable","checks":{"database":"unavailable"}}` (o erro fica no log só com o tipo da exceção). |

No servidor, `deploy/healthcheck.sh` corre a cada minuto via `deploy/vcccircuitlab-healthcheck.timer`: se `/health` falhar, reinicia o serviço `api` (`docker compose restart api`); se só `/health/ready` falhar, regista um aviso no journal (`journalctl -u vcccircuitlab-healthcheck.service`). Instalação nos comentários de `deploy/vcccircuitlab-healthcheck.service`.

## Imagem Docker

O `Dockerfile` usa um build em duas fases sobre `python:3.12-slim`: o venv é criado em `/opt/venv` só com `requirements.txt`, e apenas `app/` é copiado (ver `.dockerignore`). O contexto de build é `apps/api`. A imagem corre `uvicorn` em `0.0.0.0:8000` como `app` (uid/gid 10001), sem cabeçalho `Server` nem access log do uvicorn, e o `HEALTHCHECK` consulta `GET /health`. O número de processos define-se com `UVICORN_WORKERS`. Para correr com as restrições de segurança, usar o `docker-compose.yml` da raiz (ver README principal).

```bash
docker build -t vcccircuitlab-api:local apps/api
```
