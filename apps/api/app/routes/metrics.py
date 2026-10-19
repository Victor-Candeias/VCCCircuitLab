"""Métricas Prometheus: `GET /metrics` (E5-05).

Protegido por `Authorization: Bearer <METRICS_TOKEN>`. Sem `METRICS_TOKEN` configurado, o
endpoint não existe (404), para não expor métricas por omissão.
"""

import os
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["health"], include_in_schema=False)

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics")
def metrics(request: Request) -> PlainTextResponse:
    token = os.environ.get("METRICS_TOKEN", "")
    if not token:
        raise HTTPException(status_code=404)
    sent = request.headers.get("authorization", "")
    if not secrets.compare_digest(sent.encode(), f"Bearer {token}".encode()):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    return PlainTextResponse(request.app.state.metrics.render(), media_type=PROMETHEUS_CONTENT_TYPE)
