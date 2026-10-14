"""Catálogo: `GET /api/v1/components` (E2-06)."""

import json
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.circuit.catalog import CATALOG_PATH
from app.circuit.catalog import load_catalog as load_catalog_specs

router = APIRouter(prefix="/api/v1", tags=["components"])

ComponentCategory = Literal["source", "passive", "switch", "load", "reference"]
PinKind = Literal["passive", "positive", "negative", "reference"]
SimulationModel = (
    Literal[
        "dc_voltage_source",
        "dc_current_source",
        "resistor",
        "ideal_switch",
        "resistive_lamp",
        "ground",
    ]
    | None
)


class RelativePoint(BaseModel):
    x: float
    y: float


class Size(BaseModel):
    width: float
    height: float


class PinDefinition(BaseModel):
    id: str
    kind: PinKind
    position: RelativePoint


class NumberPropertyDefinition(BaseModel):
    type: Literal["number"]
    title: str
    description: str | None = None
    unit: str
    default: float
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = Field(default=None, alias="exclusiveMinimum")
    exclusive_maximum: float | None = Field(default=None, alias="exclusiveMaximum")

    model_config = {"populate_by_name": True}


class BooleanPropertyDefinition(BaseModel):
    type: Literal["boolean"]
    title: str
    description: str | None = None
    default: bool


PropertyDefinition = Annotated[
    NumberPropertyDefinition | BooleanPropertyDefinition, Field(discriminator="type")
]


class ComponentDefinition(BaseModel):
    type: str
    label: str
    description: str | None = None
    category: ComponentCategory
    id_prefix: str = Field(alias="idPrefix")
    symbol: str
    size: Size
    pins: list[PinDefinition]
    properties: dict[str, PropertyDefinition]
    simulation_model: SimulationModel = Field(alias="simulationModel")
    #: Verdadeiro se `simulationModel` não for `None` (o componente pode ser desenhado mesmo
    #: quando não é suportado pelo solver de simulação DC).
    supported: bool

    model_config = {"populate_by_name": True}


class ComponentCatalogResponse(BaseModel):
    catalog_version: str = Field(alias="catalogVersion")
    grid_size: float = Field(alias="gridSize")
    components: list[ComponentDefinition]

    model_config = {"populate_by_name": True}


def _load_catalog_response() -> ComponentCatalogResponse:
    # Lê o JSON em bruto (não o `ComponentSpec` reduzido usado pelo solver) para expor também
    # `description`, `category`, `idPrefix` e `symbol`, necessários à paleta de componentes.
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    supported_types = {
        spec.type for spec in load_catalog_specs().components.values() if spec.simulation_model
    }
    components = [
        ComponentDefinition.model_validate({**item, "supported": item["type"] in supported_types})
        for item in data["components"]
    ]
    return ComponentCatalogResponse.model_validate(
        {
            "catalogVersion": data["catalogVersion"],
            "gridSize": data.get("gridSize", 20.0),
            "components": components,
        }
    )


@router.get(
    "/components",
    response_model=ComponentCatalogResponse,
    response_model_by_alias=True,
    summary="Catálogo de componentes e schemas de propriedades",
)
def get_components() -> ComponentCatalogResponse:
    return _load_catalog_response()
