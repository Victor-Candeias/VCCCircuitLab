from fastapi import Depends, FastAPI

from app.auth.dependencies import require_user
from app.problems import install_problem_handlers, problem_responses
from app.routes import auth, circuits, components, health, templates, users

app = FastAPI(title="VCCCircuitLab API", version="0.1.0")
install_problem_handlers(app)

# Públicas: health check, criar conta e iniciar sessão. Tudo o resto exige sessão válida.
app.include_router(health.router)
app.include_router(users.router)
app.include_router(auth.router)

_protected = {"dependencies": [Depends(require_user)], "responses": problem_responses(401)}
app.include_router(circuits.router, **_protected)
app.include_router(components.router, **_protected)
app.include_router(templates.router, **_protected)
