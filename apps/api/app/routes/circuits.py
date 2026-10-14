"""Validação e simulação de circuitos: `POST /api/v1/circuits/{validate,simulate}`."""

import os
from typing import Any, Literal

import anyio
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitError
from app.circuit.validate import validate
from app.models.circuit import CircuitDocument
from app.problems import CircuitIssue, SimulationTimeoutError, problem_responses
from app.solver.mna import simulate_dc

#: Tempo máximo de uma simulação, em segundos (variável de ambiente `SIMULATION_TIMEOUT_S`).
SIMULATION_TIMEOUT_S = float(os.environ.get("SIMULATION_TIMEOUT_S", "5"))

router = APIRouter(prefix="/api/v1/circuits", tags=["circuits"])


class _AliasedModel(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, serialize_by_alias=True
    )


class NetOut(BaseModel):
    id: str
    terminals: list[str]


class ValidationResponse(BaseModel):
    valid: bool
    errors: list[CircuitIssue]
    warnings: list[CircuitIssue]
    nets: list[NetOut] | None = Field(
        description="Partição em redes, se a normalização foi possível."
    )


class ComponentValues(_AliasedModel):
    voltage_v: float = Field(alias="voltageV")
    current_a: float = Field(alias="currentA")
    power_w: float = Field(alias="powerW")


class SimulationResponse(_AliasedModel):
    analysis: Literal["dc_operating_point"]
    status: Literal["success"]
    node_voltages_v: dict[str, float] = Field(alias="nodeVoltagesV")
    components: dict[str, ComponentValues]
    warnings: list[CircuitIssue]


@router.post(
    "/validate",
    response_model=ValidationResponse,
    responses=problem_responses(400, 415, 422),
    summary="Verificar o JSON e a topologia do circuito",
)
def validate_circuit(document: CircuitDocument) -> dict[str, Any]:
    report = validate(document, load_catalog())
    nets = None
    if report.normalized is not None:
        nets = [n.model_dump() for n in report.normalized.document.nets or []]
    return {
        "valid": report.ok,
        "errors": [_issue(e) for e in report.errors],
        "warnings": [_issue(w) for w in report.warnings],
        "nets": nets,
    }


def _issue(error: CircuitError) -> dict[str, Any]:
    return {"code": str(error.code), "message": error.message, "refs": list(error.refs)}


@router.post(
    "/simulate",
    response_model=SimulationResponse,
    responses=problem_responses(400, 415, 422, 503),
    summary="Simular o ponto de funcionamento DC",
)
async def simulate_circuit(document: CircuitDocument) -> dict[str, Any]:
    catalog = load_catalog()
    try:
        with anyio.fail_after(SIMULATION_TIMEOUT_S):
            # A thread não é interrompida: só deixa de se esperar por ela.
            result = await anyio.to_thread.run_sync(
                simulate_dc, document, catalog, abandon_on_cancel=True
            )
    except TimeoutError as exc:
        raise SimulationTimeoutError(SIMULATION_TIMEOUT_S) from exc
    return result.to_json_dict()
