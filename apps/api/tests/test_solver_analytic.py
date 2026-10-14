"""Testes de aceitação do solver DC com resultados analíticos (arquitetura §7.1 e §12, 1–8).

Cada caso é uma fixture em `tests/fixtures/analytic/` com o circuito e o resultado esperado,
calculado à mão. Os casos de sucesso declaram `nets`, pelo que o normalizador confirma também
a partição em redes esperada (fios cruzados sem junção, junções explícitas).
"""

import copy
import math
from collections import defaultdict
from typing import Any

import pytest

from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import normalize
from app.models.circuit import CircuitDocument
from app.solver.mna import simulate_dc
from tests.factories import AnalyticCase, load_analytic_cases

TOLERANCE = 1e-9
CASES = load_analytic_cases()
SUCCESS = [c for c in CASES if not c.is_error]
ERRORS = [c for c in CASES if c.is_error]
GROUND_TYPE = "ground"


def simulate(data: dict[str, Any]) -> dict[str, Any]:
    return simulate_dc(CircuitDocument.model_validate(data)).to_json_dict()


@pytest.fixture(params=SUCCESS, ids=lambda c: c.name)
def success_case(request: pytest.FixtureRequest) -> AnalyticCase:
    return request.param


@pytest.fixture(params=ERRORS, ids=lambda c: c.name)
def error_case(request: pytest.FixtureRequest) -> AnalyticCase:
    return request.param


@pytest.fixture
def simulated(success_case: AnalyticCase) -> tuple[AnalyticCase, dict[str, Any]]:
    return success_case, simulate(success_case.circuit)


def test_fixtures_cover_essential_tests() -> None:
    assert len(SUCCESS) >= 10
    assert len(ERRORS) >= 9
    expected_codes = {code for c in ERRORS for code in c.expected["errors"]}
    assert {
        "MISSING_GROUND",
        "FLOATING_NET",
        "VOLTAGE_SOURCE_LOOP",
        "CURRENT_SOURCE_CUTSET",
        "INVALID_VALUE",
        "DUPLICATE_ID",
        "UNKNOWN_TERMINAL",
    } <= expected_codes


class TestAnalyticResults:
    def test_matches_expected_values(self, simulated: tuple[AnalyticCase, dict]) -> None:
        case, result = simulated
        expected = case.expected

        assert result["analysis"] == "dc_operating_point"
        assert result["status"] == "success"
        assert result["nodeVoltagesV"] == pytest.approx(expected["nodeVoltagesV"], abs=TOLERANCE)
        assert list(result["components"]) == list(expected["components"])
        for cid, values in expected["components"].items():
            assert result["components"][cid] == pytest.approx(values, abs=TOLERANCE), cid
        assert [w["code"] for w in result["warnings"]] == expected["warnings"]

    def test_kirchhoff_voltage_law(self, simulated: tuple[AnalyticCase, dict]) -> None:
        case, result = simulated
        normalized = normalize(CircuitDocument.model_validate(case.circuit))
        nodes = result["nodeVoltagesV"]

        for component in normalized.document.components:
            if component.type == GROUND_TYPE:
                continue
            pin1, pin2 = (normalized.terminal_to_net[component.terminal(p)] for p in component.pins)
            voltage = result["components"][component.id]["voltageV"]
            assert voltage == pytest.approx(nodes[pin1] - nodes[pin2], abs=TOLERANCE)

    def test_kirchhoff_current_law(self, simulated: tuple[AnalyticCase, dict]) -> None:
        case, result = simulated
        normalized = normalize(CircuitDocument.model_validate(case.circuit))
        components = normalized.document.components
        grounded = {
            normalized.terminal_to_net[c.terminal(p)]
            for c in components
            if c.type == GROUND_TYPE
            for p in c.pins
        }

        def node(terminal: str) -> str:
            net = normalized.terminal_to_net[terminal]
            return "GND" if net in grounded else net

        # Soma das correntes que entram em cada nó (as redes com terra formam um só nó).
        balance: dict[str, float] = defaultdict(float)
        for component in components:
            if component.type == GROUND_TYPE:
                continue
            current = result["components"][component.id]["currentA"]
            pin1, pin2 = component.pins
            balance[node(component.terminal(pin1))] -= current
            balance[node(component.terminal(pin2))] += current

        assert balance == pytest.approx(dict.fromkeys(balance, 0), abs=TOLERANCE)

    def test_power_is_conserved(self, simulated: tuple[AnalyticCase, dict]) -> None:
        _, result = simulated

        total = sum(r["powerW"] for r in result["components"].values())

        assert total == pytest.approx(0, abs=TOLERANCE)

    def test_values_are_finite_without_negative_zero(
        self, simulated: tuple[AnalyticCase, dict]
    ) -> None:
        _, result = simulated
        values = list(result["nodeVoltagesV"].values()) + [
            v for r in result["components"].values() for v in r.values()
        ]

        assert all(math.isfinite(v) for v in values)
        assert not any(v == 0 and math.copysign(1, v) < 0 for v in values)


class TestErrors:
    def test_is_rejected_with_expected_codes(self, error_case: AnalyticCase) -> None:
        with pytest.raises(CircuitValidationError) as exc:
            simulate(error_case.circuit)

        assert [e.code for e in exc.value.errors] == error_case.expected["errors"]
        assert all(e.message for e in exc.value.errors)


def case_by_name(name: str) -> AnalyticCase:
    return next(c for c in CASES if c.name == name)


class TestSwitchStability:
    """§12 teste 3: resultados consistentes e sem instabilidade ao abrir e fechar."""

    def test_toggling_gives_same_results_as_fresh_simulation(self) -> None:
        closed = case_by_name("interruptor-fechado")
        opened = case_by_name("interruptor-aberto")
        data = copy.deepcopy(closed.circuit)
        switch = next(c for c in data["components"] if c["id"] == "S1")

        runs = []
        for state in (False, True, False, True):
            switch["properties"]["closed"] = state
            runs.append(simulate(data))

        assert runs[0] == runs[2]
        assert runs[1] == runs[3]
        assert runs[0]["components"] == simulate(opened.circuit)["components"]
        assert runs[1]["components"] == simulate(closed.circuit)["components"]


class TestCrossingWires:
    """§12 teste 4: o cruzamento sem junção não une as redes; com junção passa a uni-las."""

    def test_adding_junction_at_crossing_connects_the_wires(self) -> None:
        data = copy.deepcopy(case_by_name("fios-cruzados").circuit)
        del data["nets"]
        wires = {w["id"]: w for w in data["wires"]}
        # W1 (V1.positive → R1.a) passa a ir por J9, no ponto de cruzamento, tal como W4.
        data["junctions"] = [{"id": "J9", "position": {"x": 240, "y": 80}}]
        wires["W1"]["to"] = "J9"
        wires["W4"]["to"] = "J9"
        data["wires"] += [
            {"id": "W7", "from": "J9", "to": "R1.a", "waypoints": [{"x": 400, "y": 80}]},
            {"id": "W8", "from": "J9", "to": "R2.a", "waypoints": []},
        ]

        with pytest.raises(CircuitValidationError) as exc:
            simulate(data)

        assert [e.code for e in exc.value.errors] == [CircuitErrorCode.VOLTAGE_SOURCE_LOOP]
