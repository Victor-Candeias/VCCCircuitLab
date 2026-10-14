"""Catálogo de componentes usado pelo validador e pelo layout de geração (E3-03).

`data/components.json` é uma cópia de `packages/circuit-schema/catalog/components.json` (a
imagem Docker só inclui `app/`); um teste garante que se mantém sincronizada. Carregam-se os
campos de que o backend precisa: pinos (posição incluída), tamanho do símbolo, propriedades
(tipo e limites), modelo elétrico e o passo da grelha (`gridSize`).
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

CATALOG_PATH = Path(__file__).with_name("data") / "components.json"


@dataclass(frozen=True)
class PropertySpec:
    name: str
    type: Literal["number", "boolean"]
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = None
    exclusive_maximum: float | None = None

    def type_matches(self, value: object) -> bool:
        if self.type == "boolean":
            return isinstance(value, bool)
        return isinstance(value, int | float) and not isinstance(value, bool)

    def range_violation(self, value: float) -> str | None:
        """Descrição do limite violado por `value` (numérico), ou `None` se for válido."""
        if not math.isfinite(value):
            return "tem de ser um número finito"
        if self.exclusive_minimum is not None and not value > self.exclusive_minimum:
            return f"tem de ser > {self.format(self.exclusive_minimum)}"
        if self.minimum is not None and not value >= self.minimum:
            return f"tem de ser ≥ {self.format(self.minimum)}"
        if self.exclusive_maximum is not None and not value < self.exclusive_maximum:
            return f"tem de ser < {self.format(self.exclusive_maximum)}"
        if self.maximum is not None and not value <= self.maximum:
            return f"tem de ser ≤ {self.format(self.maximum)}"
        return None

    def format(self, value: object) -> str:
        text = f"{value:g}" if isinstance(value, float) else str(value)
        return f"{text} {self.unit}" if self.unit else text


@dataclass(frozen=True)
class ComponentSpec:
    type: str
    label: str
    pins: tuple[str, ...]
    properties: dict[str, PropertySpec]
    simulation_model: str | None
    size: tuple[float, float]
    """Largura/altura do símbolo à rotação 0 (usadas pelo layout, E3-03)."""
    pin_positions: dict[str, tuple[float, float]]
    """Deslocamento `(x, y)` de cada pino face ao centro, à rotação 0 (idem)."""


@dataclass(frozen=True)
class ComponentCatalog:
    version: str
    components: dict[str, ComponentSpec]
    grid_size: float = 20.0
    """Passo da grelha do editor (`gridSize`), usado para alinhar o layout gerado (E3-03)."""

    def get(self, component_type: str) -> ComponentSpec | None:
        return self.components.get(component_type)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComponentCatalog":
        components: dict[str, ComponentSpec] = {}
        for item in data["components"]:
            properties = {
                name: PropertySpec(
                    name=name,
                    type=prop["type"],
                    unit=prop.get("unit"),
                    minimum=prop.get("minimum"),
                    maximum=prop.get("maximum"),
                    exclusive_minimum=prop.get("exclusiveMinimum"),
                    exclusive_maximum=prop.get("exclusiveMaximum"),
                )
                for name, prop in item["properties"].items()
            }
            size = item["size"]
            components[item["type"]] = ComponentSpec(
                type=item["type"],
                label=item["label"],
                pins=tuple(pin["id"] for pin in item["pins"]),
                properties=properties,
                simulation_model=item["simulationModel"],
                size=(size["width"], size["height"]),
                pin_positions={
                    pin["id"]: (pin["position"]["x"], pin["position"]["y"]) for pin in item["pins"]
                },
            )
        return cls(
            version=data["catalogVersion"],
            components=components,
            grid_size=data.get("gridSize", 20.0),
        )


@cache
def load_catalog() -> ComponentCatalog:
    """Catálogo incluído na aplicação (carregado uma vez)."""
    return ComponentCatalog.from_dict(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
