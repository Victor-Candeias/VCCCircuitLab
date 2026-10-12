"""Modelos Pydantic do documento canónico de circuito (schemaVersion 1.0).

Espelham `packages/circuit-schema/schema/circuit.schema.json`. A validação é estrita: sem
campos extra, sem coerção de tipos (ex.: `"12"` não é um número) e sem `inf`/`nan`.
Regras entre elementos (IDs únicos, referências, consistência de redes) não pertencem a estes
modelos: as redes são verificadas pelo normalizador (`app.circuit.normalize`) e as restantes
pelo validador topológico.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StringConstraints

DOCUMENT_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
ELEMENT_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"
PIN_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{0,31}$"
TERMINAL_REF_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,63}\.[A-Za-z][A-Za-z0-9_]{0,31}$"
WIRE_ENDPOINT_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,63}(\.[A-Za-z][A-Za-z0-9_]{0,31})?$"
COMPONENT_TYPE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
PROPERTY_NAME_PATTERN = r"^[a-z][A-Za-z0-9]{0,63}$"

DocumentId = Annotated[str, StringConstraints(pattern=DOCUMENT_ID_PATTERN)]
ElementId = Annotated[str, StringConstraints(pattern=ELEMENT_ID_PATTERN)]
PinId = Annotated[str, StringConstraints(pattern=PIN_ID_PATTERN)]
TerminalRef = Annotated[str, StringConstraints(pattern=TERMINAL_REF_PATTERN)]
WireEndpoint = Annotated[str, StringConstraints(pattern=WIRE_ENDPOINT_PATTERN)]
ComponentType = Annotated[str, StringConstraints(pattern=COMPONENT_TYPE_PATTERN)]
PropertyName = Annotated[str, StringConstraints(pattern=PROPERTY_NAME_PATTERN)]

FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]
PropertyValue = StrictBool | FiniteNumber
Rotation = Literal[0, 90, 180, 270]


def _unique[T](items: list[T]) -> list[T]:
    if len(set(items)) != len(items):
        raise ValueError("os itens têm de ser únicos")
    return items


class CircuitModel(BaseModel):
    """Base comum: estrita, imutável e com nomes JSON (camelCase, `from`) na entrada e na saída."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


class Point(CircuitModel):
    x: FiniteNumber
    y: FiniteNumber


class Component(CircuitModel):
    id: ElementId
    type: ComponentType
    label: Annotated[str, Field(max_length=64)] | None = None
    position: Point
    rotation: Rotation
    properties: dict[PropertyName, PropertyValue]
    pins: Annotated[list[PinId], Field(min_length=1), AfterValidator(_unique)]

    def terminal(self, pin: str) -> str:
        return f"{self.id}.{pin}"


class Junction(CircuitModel):
    id: ElementId
    position: Point


class Wire(CircuitModel):
    id: ElementId
    from_: WireEndpoint = Field(alias="from")
    to: WireEndpoint
    waypoints: list[Point]


class Net(CircuitModel):
    id: ElementId
    terminals: Annotated[list[TerminalRef], Field(min_length=1), AfterValidator(_unique)]


class CircuitDocument(CircuitModel):
    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    id: DocumentId
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(max_length=2000)] | None = None
    units: Literal["SI"]
    components: list[Component]
    junctions: list[Junction] | None = None
    wires: list[Wire]
    nets: list[Net] | None = None

    def to_json_dict(self) -> dict:
        """Representação JSON canónica (aliases, sem campos opcionais ausentes)."""
        return self.model_dump(mode="json", exclude_none=True)
