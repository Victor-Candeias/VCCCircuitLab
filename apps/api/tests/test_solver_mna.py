from typing import Any

import pytest

from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import normalize
from app.models.circuit import CircuitDocument
from app.solver.mna import ComponentResult, DcResult, simulate_dc, solve_dc
from tests.factories import circuit, comp, load_fixture, source_resistor

Code = CircuitErrorCode


def simulate(data: dict[str, Any]) -> DcResult:
    return simulate_dc(CircuitDocument.model_validate(data))


def assert_result(actual: ComponentResult, voltage: float, current: float, power: float) -> None:
    assert actual.voltage_v == pytest.approx(voltage, abs=1e-12)
    assert actual.current_a == pytest.approx(current, abs=1e-12)
    assert actual.power_w == pytest.approx(power, abs=1e-12)


def total_power(result: DcResult) -> float:
    return sum(r.power_w for r in result.components.values())


class TestAnalytic:
    def test_source_and_resistor(self) -> None:
        result = simulate(load_fixture("fonte-resistencia"))

        assert result.node_voltages_v == pytest.approx({"N_PLUS": 12, "N_GND": 0})
        assert_result(result.components["R1"], 12, 0.12, 1.44)
        assert_result(result.components["V1"], 12, -0.12, -1.44)
        assert "GND1" not in result.components
        assert result.warnings == ()

    def test_series_divides_voltage(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor")]
            + [comp("R2", "resistor", resistanceOhm=200), comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "R2.a"),
            ("R2.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate(data)

        assert_result(result.components["R1"], 4, 0.04, 0.16)
        assert_result(result.components["R2"], 8, 0.04, 0.32)
        assert sorted(result.node_voltages_v.values()) == pytest.approx([0, 8, 12])

    def test_parallel_with_closed_switch(self) -> None:
        result = simulate(load_fixture("paralelo-juncao"))
        i1, i2 = 9 / 220, 9 / 330.5

        assert_result(result.components["R1"], 9, i1, 9 * i1)
        assert_result(result.components["R2"], 9, i2, 9 * i2)
        assert_result(result.components["S1"], 0, i1 + i2, 0)
        assert_result(result.components["V1"], 9, -(i1 + i2), -9 * (i1 + i2))
        assert total_power(result) == pytest.approx(0, abs=1e-12)

    def test_lamp_is_equivalent_resistance(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("H1", "lamp"), comp("GND1", "ground")],
            ("V1.positive", "H1.a"),
            ("H1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate(data)

        assert_result(result.components["H1"], 12, 5 / 12, 5)

    def test_open_switch_blocks_current(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("S1", "switch", closed=False)]
            + [comp("H1", "lamp"), comp("GND1", "ground")],
            ("V1.positive", "S1.a"),
            ("S1.b", "H1.a"),
            ("H1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate(data)

        assert_result(result.components["S1"], 12, 0, 0)
        assert_result(result.components["H1"], 0, 0, 0)
        assert_result(result.components["V1"], 12, 0, 0)

    def test_closed_switch_shorts_parallel_resistor(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor"), comp("R2", "resistor")]
            + [comp("S1", "switch"), comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "R2.a"),
            ("R1.b", "S1.a"),
            ("R2.b", "V1.negative"),
            ("S1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate(data)

        assert_result(result.components["R1"], 12, 0.12, 1.44)
        assert_result(result.components["R2"], 0, 0, 0)
        assert_result(result.components["S1"], 0, 0.12, 0)

    def test_current_source(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source"), comp("R1", "resistor"), comp("GND1", "ground")],
            ("I1.positive", "R1.a"),
            ("R1.b", "I1.negative"),
            ("GND1.gnd", "I1.negative"),
        )

        result = simulate(data)

        assert_result(result.components["R1"], 10, 0.1, 1)
        assert_result(result.components["I1"], 10, -0.1, -1)

    def test_current_source_and_voltage_source(self) -> None:
        # V1 (12 V) — R1 (100 Ω) — nó X; I1 injeta 0,1 A em X; R2 (100 Ω) de X à terra.
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor"), comp("R2", "resistor")]
            + [comp("I1", "dc_current_source"), comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "R2.a"),
            ("I1.positive", "R1.b"),
            ("I1.negative", "V1.negative"),
            ("R2.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate(data)

        # Vx = (12/100 + 0,1) / (2/100) = 11 V
        assert_result(result.components["R1"], 1, 0.01, 0.01)
        assert_result(result.components["R2"], 11, 0.11, 1.21)
        assert_result(result.components["I1"], 11, -0.1, -1.1)
        assert_result(result.components["V1"], 12, -0.01, -0.12)
        assert total_power(result) == pytest.approx(0, abs=1e-12)

    def test_voltage_sources_in_series(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("V2", "dc_voltage_source", voltageV=5)]
            + [comp("R1", "resistor"), comp("GND1", "ground")],
            ("V1.positive", "V2.negative"),
            ("V2.positive", "R1.a"),
            ("R1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate(data)

        assert_result(result.components["R1"], 17, 0.17, 2.89)
        assert_result(result.components["V2"], 5, -0.17, -0.85)

    def test_ground_on_positive_terminal_gives_negative_voltages(self) -> None:
        data = source_resistor()
        data["wires"][2]["to"] = "V1.positive"

        result = simulate(data)

        assert sorted(result.node_voltages_v.values()) == pytest.approx([-12, 0])
        assert_result(result.components["R1"], 12, 0.12, 1.44)

    def test_independent_grounded_subcircuits(self) -> None:
        data = source_resistor()
        data["components"] += [comp("V2", "dc_voltage_source", voltageV=6)]
        data["components"] += [comp("R2", "resistor", resistanceOhm=60), comp("GND2", "ground")]
        data["wires"] += [
            {"id": "W4", "from": "V2.positive", "to": "R2.a", "waypoints": []},
            {"id": "W5", "from": "R2.b", "to": "V2.negative", "waypoints": []},
            {"id": "W6", "from": "GND2.gnd", "to": "V2.negative", "waypoints": []},
        ]

        result = simulate(data)

        assert_result(result.components["R1"], 12, 0.12, 1.44)
        assert_result(result.components["R2"], 6, 0.1, 0.6)

    def test_only_ground(self) -> None:
        result = simulate(circuit([comp("GND1", "ground")]))

        assert result.components == {}
        assert list(result.node_voltages_v.values()) == [0]


class TestWarningsAndErrors:
    def test_validation_warnings_are_kept(self) -> None:
        data = source_resistor()
        data["components"].append(comp("R2", "resistor"))
        data["wires"].append({"id": "W4", "from": "R2.a", "to": "R1.a", "waypoints": []})

        result = simulate(data)

        assert [w.code for w in result.warnings] == [Code.UNCONNECTED_PIN]
        assert_result(result.components["R2"], 0, 0, 0)

    @pytest.mark.parametrize(
        ("data", "code"),
        [
            ({**source_resistor(), "wires": source_resistor()["wires"][:2]}, Code.FLOATING_NET),
            (
                circuit(
                    [comp("V1", "dc_voltage_source"), comp("R1", "resistor")],
                    ("V1.positive", "R1.a"),
                    ("R1.b", "V1.negative"),
                ),
                Code.MISSING_GROUND,
            ),
            (source_resistor(resistanceOhm=0), Code.INVALID_VALUE),
        ],
    )
    def test_validation_errors_prevent_simulation(self, data: dict[str, Any], code: Code) -> None:
        with pytest.raises(CircuitValidationError) as exc:
            simulate(data)

        assert [e.code for e in exc.value.errors] == [code]

    def test_conflicting_sources_prevent_simulation(self) -> None:
        data = source_resistor()
        data["components"].append(comp("V2", "dc_voltage_source", voltageV=5))
        data["wires"] += [
            {"id": "W4", "from": "V2.positive", "to": "V1.positive", "waypoints": []},
            {"id": "W5", "from": "V2.negative", "to": "V1.negative", "waypoints": []},
        ]

        with pytest.raises(CircuitValidationError) as exc:
            simulate(data)

        assert [e.code for e in exc.value.errors] == [Code.VOLTAGE_SOURCE_LOOP]

    def test_singular_matrix_without_validation(self) -> None:
        data = source_resistor()
        data["components"] += [comp("R2", "resistor"), comp("R3", "resistor")]
        data["wires"] += [
            {"id": "W4", "from": "R2.a", "to": "R3.a", "waypoints": []},
            {"id": "W5", "from": "R2.b", "to": "R3.b", "waypoints": []},
        ]

        with pytest.raises(CircuitValidationError) as exc:
            solve_dc(normalize(CircuitDocument.model_validate(data)))

        assert [e.code for e in exc.value.errors] == [Code.SINGULAR_MATRIX]

    def test_ill_conditioned_matrix(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor", resistanceOhm=1e-13)]
            + [comp("R2", "resistor", resistanceOhm=1e9), comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "R2.a"),
            ("R2.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        with pytest.raises(CircuitValidationError) as exc:
            simulate(data)

        assert [e.code for e in exc.value.errors] == [Code.ILL_CONDITIONED_MATRIX]
        assert "mal condicionado" in exc.value.errors[0].message


class TestJson:
    def test_result_format(self) -> None:
        data = source_resistor()
        data["components"].append(comp("R2", "resistor"))
        data["wires"].append({"id": "W4", "from": "R2.a", "to": "R1.a", "waypoints": []})

        dumped = simulate(data).to_json_dict()

        assert dumped["analysis"] == "dc_operating_point"
        assert dumped["status"] == "success"
        assert dumped["nodeVoltagesV"] == pytest.approx({"N1": 12, "N2": 0, "N3": 12})
        assert dumped["components"]["R1"] == pytest.approx(
            {"voltageV": 12, "currentA": 0.12, "powerW": 1.44}
        )
        assert dumped["warnings"] == [
            {
                "code": "UNCONNECTED_PIN",
                "message": "O terminal R2.b não está ligado a nada.",
                "refs": ["R2.b"],
            }
        ]

    def test_no_negative_zero(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("S1", "switch", closed=False)]
            + [comp("H1", "lamp"), comp("GND1", "ground")],
            ("V1.positive", "S1.a"),
            ("S1.b", "H1.a"),
            ("H1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        dumped = simulate(data).to_json_dict()

        assert "-0.0" not in repr(dumped)
