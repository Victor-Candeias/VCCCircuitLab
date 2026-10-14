# VCCCircuitLab API

Backend Python (FastAPI) do VCCCircuitLab. Não pertence ao workspace pnpm; as dependências estão fixadas em `requirements.txt` (execução) e `requirements-dev.txt` (testes e lint).

## Estrutura

```text
apps/api/
├── app/
│   ├── main.py        # app = FastAPI()
│   ├── problems.py    # Erros application/problem+json
│   ├── routes/        # Rotas HTTP (GET /health, POST /api/v1/circuits/…)
│   ├── models/        # Modelos Pydantic
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
- O catálogo é lido de `app/circuit/data/components.json` (`app/circuit/catalog.py`). É uma cópia de `packages/circuit-schema/catalog/components.json`, porque a imagem Docker só inclui `app/`. Um teste falha se as duas versões divergirem: depois de alterar o catálogo, copiar o ficheiro.

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

O corpo é sempre o documento canónico (`CircuitDocument`), enviado como `application/json`. A documentação interativa está em `/docs` e o esquema em `/openapi.json`.

| Método | Endpoint | Resposta `200` |
|---|---|---|
| `POST` | `/api/v1/circuits/generate` | Documento canónico gerado (`CircuitDocument`, com `nets` já calculado). Corpo: `{ template, parameters }` (ver [Geração por templates](#geração-por-templates)). |
| `POST` | `/api/v1/circuits/validate` | `{ valid, errors[], warnings[], nets[] \| null }`. Os erros de circuito fazem parte do relatório e não são erros HTTP. `nets` traz a partição em redes quando a normalização foi possível. |
| `POST` | `/api/v1/circuits/simulate` | Resultado DC (ver [Solver MNA DC](#solver-mna-dc)). |
| `GET` | `/api/v1/components` | Catálogo de componentes (E2-06): `{ catalogVersion, gridSize, components[] }`. Cada componente traz o schema completo de propriedades (`NumberPropertyDefinition`/`BooleanPropertyDefinition`, com `unit`, `default` e limites) e `supported` (`simulationModel !== null`), para clientes assinalarem componentes desenháveis mas não simuláveis. Fonte: `app/circuit/data/components.json` (cópia de `packages/circuit-schema/catalog/components.json`, ver [Validação topológica e de valores](#validação-topológica-e-de-valores)). |

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
| `…:simulation-timeout` | 503 | `SIMULATION_TIMEOUT` |
| `about:blank` | 404, 405, … | Nome do estado HTTP (`NOT_FOUND`, `METHOD_NOT_ALLOWED`, …) |
| `…:internal-error` | 500 | `INTERNAL_ERROR` |

## Imagem Docker

O `Dockerfile` usa um build em duas fases sobre `python:3.12-slim`: o venv é criado em `/opt/venv` só com `requirements.txt`, e apenas `app/` é copiado (ver `.dockerignore`). O contexto de build é `apps/api`. A imagem corre `uvicorn` em `0.0.0.0:8000` como `app` (uid/gid 10001), sem cabeçalho `Server`, e o `HEALTHCHECK` consulta `GET /health`. O número de processos define-se com `UVICORN_WORKERS`. Para correr com as restrições de segurança, usar o `docker-compose.yml` da raiz (ver README principal).

```bash
docker build -t vcccircuitlab-api:local apps/api
```
