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
