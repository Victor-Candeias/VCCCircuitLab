from fastapi import Depends, FastAPI

from app.auth.dependencies import require_user
from app.http_security import install_security
from app.observability import Metrics, ObservabilityMiddleware, configure_logging
from app.problems import install_problem_handlers, problem_responses
from app.routes import auth, circuits, components, health, metrics, templates, users

app = FastAPI(title="VCCCircuitLab API", version="0.1.0")
install_problem_handlers(app)
install_security(app)
# Por fora de tudo (incluindo CORS, rate limiting e limite do corpo), para medir também 413/429.
app.state.metrics = Metrics()
app.add_middleware(ObservabilityMiddleware, metrics=app.state.metrics)
configure_logging()

# Públicas: health check, criar conta e iniciar sessão. Tudo o resto exige sessão válida.
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(users.router)
app.include_router(auth.router)

_protected = {"dependencies": [Depends(require_user)], "responses": problem_responses(401)}
app.include_router(circuits.router, **_protected)
app.include_router(components.router, **_protected)
app.include_router(templates.router, **_protected)
