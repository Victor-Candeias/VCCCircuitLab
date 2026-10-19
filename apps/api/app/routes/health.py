"""Health checks (E5-05): `GET /health` (liveness) e `GET /health/ready` (readiness)."""

import logging
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.mongo import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, Literal["ok", "unavailable"]]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """O processo responde (sem dependências): usado para reiniciar a API se falhar."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Dependência indisponível"}},
)
def ready() -> JSONResponse:
    """A API consegue servir pedidos: o MongoDB responde a `ping`. Sem detalhes do erro."""
    try:
        get_client().admin.command("ping")
        database = "ok"
    except Exception as exc:  # noqa: BLE001 - qualquer falha da BD conta como indisponível
        logger.warning("Readiness: MongoDB indisponível (%s)", type(exc).__name__)
        database = "unavailable"
    status = "ok" if database == "ok" else "unavailable"
    body = ReadinessResponse(status=status, checks={"database": database})
    return JSONResponse(body.model_dump(), status_code=200 if status == "ok" else 503)
