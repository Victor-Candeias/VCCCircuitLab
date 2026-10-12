# VCCCircuitLab API

Backend Python (FastAPI) do VCCCircuitLab. Não pertence ao workspace pnpm; as dependências estão fixadas em `requirements.txt` (execução) e `requirements-dev.txt` (testes e lint).

## Estrutura

```text
apps/api/
├── app/
│   ├── main.py        # app = FastAPI()
│   ├── routes/        # Rotas HTTP (GET /health)
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
  - Os erros são lançados como `CircuitValidationError` com `UNKNOWN_TERMINAL`, `UNKNOWN_JUNCTION` ou `NET_INCONSISTENT` (`app/circuit/errors.py`).   Cada erro inclui os `refs` envolvidos.

  ## Imagem Docker

O `Dockerfile` usa um build em duas fases sobre `python:3.12-slim`: o venv é criado em `/opt/venv` só com `requirements.txt`, e apenas `app/` é copiado (ver `.dockerignore`). O contexto de build é `apps/api`. A imagem corre `uvicorn` em `0.0.0.0:8000` como `app` (uid/gid 10001), sem cabeçalho `Server`, e o `HEALTHCHECK` consulta `GET /health`. O número de processos define-se com `UVICORN_WORKERS`. Para correr com as restrições de segurança, usar o `docker-compose.yml` da raiz (ver README principal).

```bash
docker build -t vcccircuitlab-api:local apps/api
```
