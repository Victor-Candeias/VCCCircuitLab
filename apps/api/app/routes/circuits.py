"""Circuitos: `POST /api/v1/circuits/{generate,validate,simulate}`."""

import os
from functools import partial
from typing import Annotated, Any, Literal

import anyio
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitError
from app.circuit.normalize import normalize
from app.circuit.validate import validate
from app.generation.errors import InvalidParametersError, UnknownTemplateError
from app.generation.registry import get_template
from app.models.circuit import CircuitDocument
from app.problems import CircuitIssue, SimulationTimeoutError, problem_responses
from app.solver.engine import simulate

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


class GenerateRequest(_AliasedModel):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, serialize_by_alias=True, extra="forbid"
    )
    #: Nome registado em `app.generation.registry.TEMPLATES` (`series_dc`, `parallel_dc`, …).
    template: Annotated[str, Field(min_length=1)]
    #: Parâmetros do template, validados por `app.generation.params` (nomes em camelCase).
    parameters: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/generate",
    response_model=CircuitDocument,
    response_model_exclude_none=True,
    responses=problem_responses(400, 415, 422),
    summary="Gerar um circuito editável a partir de um template",
)
def generate_circuit(body: GenerateRequest) -> CircuitDocument:
    try:
        spec = get_template(body.template)
    except KeyError as exc:
        raise UnknownTemplateError(body.template) from exc
    try:
        params = spec.params_model(**body.parameters)
    except ValidationError as exc:
        raise InvalidParametersError(body.template, exc) from exc
    return normalize(spec.build(params)).document


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
    description=(
        "Motor configurado por `SIMULATION_ENGINE` (`mna` por omissão, ou `ngspice`). "
        "503 se a simulação exceder `SIMULATION_TIMEOUT_S` ou o motor estiver indisponível."
    ),
)
async def simulate_circuit(document: CircuitDocument) -> dict[str, Any]:
    catalog = load_catalog()
    try:
        with anyio.fail_after(SIMULATION_TIMEOUT_S):
            # A thread não é interrompida: só deixa de se esperar por ela.
            result = await anyio.to_thread.run_sync(
                partial(simulate, document, catalog, timeout_s=SIMULATION_TIMEOUT_S),
                abandon_on_cancel=True,
            )
    except TimeoutError as exc:
        raise SimulationTimeoutError(SIMULATION_TIMEOUT_S) from exc
    return result.to_json_dict()
