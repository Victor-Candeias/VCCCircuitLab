"""Construtores de circuitos para os testes (componentes conformes com o catálogo)."""

import json
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[3] / "packages/circuit-schema"
FIXTURES = PACKAGE / "test/fixtures/valid"

PINS = {
    "dc_voltage_source": ["positive", "negative"],
    "dc_current_source": ["positive", "negative"],
    "resistor": ["a", "b"],
    "switch": ["a", "b"],
    "lamp": ["a", "b"],
    "ground": ["gnd"],
}
PROPERTIES: dict[str, dict[str, Any]] = {
    "dc_voltage_source": {"voltageV": 12},
    "dc_current_source": {"currentA": 0.1},
    "resistor": {"resistanceOhm": 100},
    "switch": {"closed": True},
    "lamp": {"ratedVoltageV": 12, "ratedPowerW": 5},
    "ground": {},
}


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def comp(cid: str, ctype: str, **properties: Any) -> dict[str, Any]:
    return {
        "id": cid,
        "type": ctype,
        "position": {"x": 0, "y": 0},
        "rotation": 0,
        "properties": {**PROPERTIES[ctype], **properties},
        "pins": list(PINS[ctype]),
    }


def circuit(components: list[dict[str, Any]], *links: tuple[str, str], **extra: Any) -> dict:
    """Circuito com um fio por ligação (`W1`, `W2`, ...)."""
    wires = [
        {"id": f"W{i}", "from": a, "to": b, "waypoints": []} for i, (a, b) in enumerate(links, 1)
    ]
    return {
        "schemaVersion": "1.0",
        "id": "teste",
        "name": "Teste",
        "units": "SI",
        "components": components,
        "wires": wires,
        **extra,
    }


def source_resistor(**resistor_props: Any) -> dict[str, Any]:
    """12 V + R1 (100 Ω por omissão) com terra no negativo."""
    return circuit(
        [comp("V1", "dc_voltage_source"), comp("R1", "resistor", **resistor_props)]
        + [comp("GND1", "ground")],
        ("V1.positive", "R1.a"),
        ("R1.b", "V1.negative"),
        ("GND1.gnd", "V1.negative"),
    )
