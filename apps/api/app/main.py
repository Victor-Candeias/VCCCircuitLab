from fastapi import FastAPI

from app.problems import install_problem_handlers
from app.routes import circuits, components, health, users

app = FastAPI(title="VCCCircuitLab API", version="0.1.0")
install_problem_handlers(app)
app.include_router(health.router)
app.include_router(circuits.router)
app.include_router(components.router)
app.include_router(users.router)
