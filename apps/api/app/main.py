from fastapi import FastAPI

from app.problems import install_problem_handlers
from app.routes import circuits, health

app = FastAPI(title="VCCCircuitLab API", version="0.1.0")
install_problem_handlers(app)
app.include_router(health.router)
app.include_router(circuits.router)
