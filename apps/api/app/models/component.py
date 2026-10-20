"""Campos partilhados de definições de componentes.

Usados pelo catálogo estático (`GET /api/v1/components`, E2-06) e pela coleção `templates` em
BD, gerida só por administradores (`app/routes/templates.py`, F2-10).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.circuit import ComponentType, PropertyName

ComponentCategory = Literal["source", "passive", "switch", "load", "instrument", "reference"]
PinKind = Literal["passive", "positive", "negative", "reference"]
SimulationModel = (
    Literal[
        "dc_voltage_source",
        "dc_current_source",
        "resistor",
        "ideal_switch",
        "resistive_lamp",
        "capacitor",
        "inductor",
        "voltmeter",
        "ammeter",
        "oscilloscope",
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


class ComponentFields(BaseModel):
    """Campos editáveis de uma definição de componente (sem `supported`, calculado à parte)."""

    type: ComponentType
    label: str
    description: str | None = None
    category: ComponentCategory
    id_prefix: str = Field(alias="idPrefix")
    symbol: str
    size: Size
    pins: list[PinDefinition]
    properties: dict[PropertyName, PropertyDefinition]
    simulation_model: SimulationModel = Field(alias="simulationModel")

    model_config = {"populate_by_name": True}


class ComponentDefinition(ComponentFields):
    #: Verdadeiro se `simulationModel` não for `None` (o componente pode ser desenhado mesmo
    #: quando não é suportado pelo solver de simulação DC).
    supported: bool
