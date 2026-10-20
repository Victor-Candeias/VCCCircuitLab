"""Construtores de circuitos para os testes (componentes conformes com o catálogo)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[3] / "packages/circuit-schema"
FIXTURES = PACKAGE / "test/fixtures/valid"
ANALYTIC_FIXTURES = Path(__file__).resolve().parent / "fixtures/analytic"

PINS = {
    "dc_voltage_source": ["positive", "negative"],
    "dc_current_source": ["positive", "negative"],
    "resistor": ["a", "b"],
    "switch": ["a", "b"],
    "lamp": ["a", "b"],
    "capacitor": ["a", "b"],
    "inductor": ["a", "b"],
    "voltmeter": ["positive", "negative"],
    "ammeter": ["positive", "negative"],
    "oscilloscope": ["ch1", "ch2"],
    "diode": ["anode", "cathode"],
    "led": ["anode", "cathode"],
    "npn_transistor": ["collector", "base", "emitter"],
    "pnp_transistor": ["collector", "base", "emitter"],
    "ground": ["gnd"],
    "mains_source": ["line", "neutral"],
    "mains_lamp": ["a", "b"],
    "changeover_switch": ["common", "l1", "l2"],
    "relay": ["coil_a", "coil_b", "com", "no"],
    "circuit_breaker": ["a", "b"],
    "rcd": ["line_in", "line_out", "neutral_in", "neutral_out"],
}
PROPERTIES: dict[str, dict[str, Any]] = {
    "dc_voltage_source": {"voltageV": 12},
    "dc_current_source": {"currentA": 0.1},
    "resistor": {"resistanceOhm": 100},
    "switch": {"closed": True},
    "lamp": {"ratedVoltageV": 12, "ratedPowerW": 5},
    "capacitor": {"capacitanceF": 1e-4, "initialVoltageV": 0},
    "inductor": {"inductanceH": 0.1, "initialCurrentA": 0},
    "voltmeter": {},
    "ammeter": {},
    "oscilloscope": {},
    "diode": {"forwardVoltageV": 0.7, "forwardCurrentA": 0.01},
    "led": {"forwardVoltageV": 2.0, "forwardCurrentA": 0.02},
    "npn_transistor": {"currentGain": 100, "saturationCurrentA": 1e-14},
    "pnp_transistor": {"currentGain": 100, "saturationCurrentA": 1e-14},
    "ground": {},
    "mains_source": {"voltageV": 230, "frequencyHz": 50},
    "mains_lamp": {"ratedVoltageV": 230, "ratedPowerW": 60},
    "changeover_switch": {"toL2": False},
    "relay": {"coilVoltageV": 12},
    "circuit_breaker": {"closed": True, "ratedCurrentA": 10},
    "rcd": {"closed": True, "ratedCurrentA": 40, "residualCurrentA": 0.03},
}


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class AnalyticCase:
    """Circuito com o resultado esperado calculado à mão (`tests/fixtures/analytic/*.json`)."""

    name: str
    description: str
    circuit: dict[str, Any]
    expected: dict[str, Any]

    @property
    def is_error(self) -> bool:
        return "errors" in self.expected


def load_analytic_cases() -> list[AnalyticCase]:
    cases = []
    for path in sorted(ANALYTIC_FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        description, circuit, expected = data["description"], data["circuit"], data["expected"]
        cases.append(AnalyticCase(path.stem, description, circuit, expected))
    return cases


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
