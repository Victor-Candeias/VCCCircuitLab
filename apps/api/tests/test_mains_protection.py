"""Rede 230/400 V, comutador, disjuntor, diferencial e relé (F2-07)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.validate import validate
from app.main import app
from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, simulate_dc
from app.solver.transient import simulate_transient
from app.spice.exchange import export_netlist, import_netlist
from app.spice.netlist import build_netlist
from tests.factories import circuit, comp

Code = CircuitErrorCode
client = TestClient(app)
LAMP_CURRENT = 60 / 230


def document(data: dict[str, Any]) -> CircuitDocument:
    return CircuitDocument.model_validate(data)


def simulate(data: dict[str, Any]) -> DcResult:
    return simulate_dc(document(data))


def codes(issues: Any) -> list[Code]:
    return [issue.code for issue in issues]


def mains_lamp(*extra: dict[str, Any], breaker: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rede 230 V → disjuntor Q1 → lâmpada de 60 W → neutro (ligado à terra)."""
    components = [
        comp("AC1", "mains_source"),
        comp("QF1", "circuit_breaker", **(breaker or {})),
        comp("H1", "mains_lamp"),
        comp("GND1", "ground"),
        *extra,
    ]
    return circuit(
        components,
        ("AC1.line", "QF1.a"),
        ("QF1.b", "H1.a"),
        ("H1.b", "AC1.neutral"),
        ("GND1.gnd", "AC1.neutral"),
    )


def staircase(a_to_l2: bool, b_to_l2: bool) -> dict[str, Any]:
    """Iluminação de escada: dois comutadores ligados pelos dois condutores de ida e volta."""
    return circuit(
        [comp("AC1", "mains_source"), comp("QF1", "circuit_breaker")]
        + [comp("SC1", "changeover_switch", toL2=a_to_l2)]
        + [comp("SC2", "changeover_switch", toL2=b_to_l2)]
        + [comp("H1", "mains_lamp"), comp("GND1", "ground")],
        ("AC1.line", "QF1.a"),
        ("QF1.b", "SC1.common"),
        ("SC1.l1", "SC2.l1"),
        ("SC1.l2", "SC2.l2"),
        ("SC2.common", "H1.a"),
        ("H1.b", "AC1.neutral"),
        ("GND1.gnd", "AC1.neutral"),
    )


def rcd_circuit(*extra: dict[str, Any], links: tuple[tuple[str, str], ...] = (), **rcd: Any):
    """Rede 230 V → diferencial ID1 (fase e neutro) → lâmpada de 60 W."""
    return circuit(
        [comp("AC1", "mains_source"), comp("QF1", "circuit_breaker")]
        + [comp("ID1", "rcd", **rcd), comp("H1", "mains_lamp"), comp("GND1", "ground"), *extra],
        ("AC1.line", "QF1.a"),
        ("QF1.b", "ID1.line_in"),
        ("ID1.line_out", "H1.a"),
        ("H1.b", "ID1.neutral_out"),
        ("ID1.neutral_in", "AC1.neutral"),
        ("GND1.gnd", "AC1.neutral"),
        *links,
    )


class TestMainsValidation:
    def test_safety_warnings(self) -> None:
        report = validate(document(mains_lamp()))

        assert report.errors == ()
        assert codes(report.warnings) == [Code.MAINS_VOLTAGE]
        assert "AC1: 230 V" in report.warnings[0].message
        assert report.warnings[0].refs == ("AC1",)

    def test_missing_breaker_is_a_warning(self) -> None:
        data = circuit(
            [comp("AC1", "mains_source"), comp("H1", "mains_lamp"), comp("GND1", "ground")],
            ("AC1.line", "H1.a"),
            ("H1.b", "AC1.neutral"),
            ("GND1.gnd", "AC1.neutral"),
        )

        assert codes(validate(document(data)).warnings) == [
            Code.MAINS_VOLTAGE,
            Code.MISSING_PROTECTION,
        ]

    def test_transient_is_not_supported(self) -> None:
        report = validate(document(mains_lamp()), analysis="transient")

        assert codes(report.errors) == [Code.UNSUPPORTED_ANALYSIS]
        assert report.errors[0].refs == ("AC1",)

    def test_only_resistive_loads(self) -> None:
        data = mains_lamp(comp("C1", "capacitor"), comp("V1", "dc_voltage_source"))
        data["wires"] += [
            {"id": "W9", "from": "C1.a", "to": "H1.a", "waypoints": []},
            {"id": "W10", "from": "C1.b", "to": "H1.b", "waypoints": []},
            {"id": "W11", "from": "V1.positive", "to": "V1.negative", "waypoints": []},
        ]

        errors = validate(document(data)).errors

        assert Code.UNSUPPORTED_ANALYSIS in codes(errors)
        error = next(e for e in errors if e.code is Code.UNSUPPORTED_ANALYSIS)
        assert error.refs == ("AC1", "C1", "V1")

    def test_voltage_limited_to_400_v(self) -> None:
        data = mains_lamp()
        data["components"][0]["properties"]["voltageV"] = 690

        assert codes(validate(document(data)).errors) == [Code.INVALID_VALUE]

    def test_relay_is_symbol_only(self) -> None:
        data = circuit([comp("K1", "relay"), comp("GND1", "ground")], ("K1.coil_b", "GND1.gnd"))

        errors = validate(document(data)).errors

        assert codes(errors)[0] is Code.UNSUPPORTED_MODEL
        assert "não é suportado pelo solver" in errors[0].message

    def test_relay_is_listed_as_unsupported(self) -> None:
        response = client.get("/api/v1/components")

        by_type = {c["type"]: c for c in response.json()["components"]}
        assert by_type["relay"]["supported"] is False
        assert by_type["rcd"]["supported"] is True
        assert by_type["circuit_breaker"]["category"] == "protection"


class TestMainsSolver:
    def test_rms_equivalent(self) -> None:
        result = simulate(mains_lamp())

        lamp = result.components["H1"]
        assert lamp.voltage_v == pytest.approx(230)
        assert lamp.current_a == pytest.approx(LAMP_CURRENT)
        assert lamp.power_w == pytest.approx(60)
        assert result.components["QF1"].current_a == pytest.approx(LAMP_CURRENT)
        assert codes(result.warnings) == [Code.MAINS_VOLTAGE]

    def test_open_breaker(self) -> None:
        result = simulate(mains_lamp(breaker={"closed": False}))

        assert result.components["H1"].current_a == 0
        assert result.components["QF1"].voltage_v == pytest.approx(230)

    def test_breaker_overcurrent(self) -> None:
        heater = comp("R1", "resistor", resistanceOhm=10)
        data = mains_lamp(heater)
        data["wires"] += [
            {"id": "W9", "from": "R1.a", "to": "H1.a", "waypoints": []},
            {"id": "W10", "from": "R1.b", "to": "H1.b", "waypoints": []},
        ]

        result = simulate(data)

        assert codes(result.warnings) == [Code.MAINS_VOLTAGE, Code.OVERCURRENT]
        assert result.warnings[1].refs == ("QF1",)
        assert "23.3 A" in result.warnings[1].message
        assert "In = 10 A" in result.warnings[1].message

        data["components"][1]["properties"]["ratedCurrentA"] = 32
        assert codes(simulate(data).warnings) == [Code.MAINS_VOLTAGE]

    @pytest.mark.parametrize(
        ("a_to_l2", "b_to_l2", "lit"),
        [(False, False, True), (False, True, False), (True, False, False), (True, True, True)],
    )
    def test_staircase(self, a_to_l2: bool, b_to_l2: bool, lit: bool) -> None:
        result = simulate(staircase(a_to_l2, b_to_l2))

        expected = LAMP_CURRENT if lit else 0
        assert result.components["H1"].current_a == pytest.approx(expected)
        assert result.components["SC1"].voltage_v == 0
        assert result.components["SC1"].current_a == pytest.approx(expected)
        # condutor de ida e volta ligado só a contactos inativos: potencial indefinido
        assert len(result.node_voltages_v) == (5 if lit else 6)

    def test_rcd_without_leakage(self) -> None:
        result = simulate(rcd_circuit())

        assert "ID1:L" not in result.components
        rcd = result.components["ID1"]
        assert (rcd.voltage_v, rcd.power_w) == (0, 0)
        assert rcd.current_a == pytest.approx(LAMP_CURRENT)
        assert list(result.components) == ["AC1", "QF1", "ID1", "H1"]
        assert codes(result.warnings) == [Code.MAINS_VOLTAGE]

    def test_rcd_residual_current(self) -> None:
        leak = comp("R1", "resistor", resistanceOhm=4600)  # 50 mA da fase para a terra
        data = rcd_circuit(comp("GND2", "ground"), leak, links=(("R1.a", "H1.a"),))
        data["wires"].append({"id": "W99", "from": "R1.b", "to": "GND2.gnd", "waypoints": []})

        result = simulate(data)

        assert codes(result.warnings) == [Code.MAINS_VOLTAGE, Code.RESIDUAL_CURRENT]
        assert "50 mA" in result.warnings[1].message
        assert "IΔn = 30 mA" in result.warnings[1].message

    def test_rcd_overcurrent(self) -> None:
        result = simulate(rcd_circuit(ratedCurrentA=0.1))

        assert codes(result.warnings) == [Code.MAINS_VOLTAGE, Code.OVERCURRENT]
        assert "diferencial ID1" in result.warnings[1].message

    def test_open_rcd_isolates_like_a_switch(self) -> None:
        with pytest.raises(CircuitValidationError) as exc:
            simulate(rcd_circuit(closed=False))

        assert Code.FLOATING_NET in codes(exc.value.errors)


class TestProtectionTransient:
    def test_poles_merged_and_peak_current(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("ID1", "rcd", ratedCurrentA=0.1)]
            + [comp("SC1", "changeover_switch", toL2=True)]
            + [comp("R1", "resistor"), comp("C1", "capacitor"), comp("GND1", "ground")],
            ("V1.positive", "ID1.line_in"),
            ("ID1.line_out", "SC1.common"),
            ("SC1.l2", "R1.a"),
            ("R1.b", "C1.a"),
            ("C1.b", "ID1.neutral_out"),
            ("ID1.neutral_in", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        result = simulate_transient(document(data), stop_time_s=0.01, time_step_s=1e-3)

        assert list(result.components) == ["V1", "ID1", "SC1", "R1", "C1"]
        assert result.components["ID1"].current_a[0] == pytest.approx(0.12)
        assert result.components["ID1"].current_a[-1] < 0.1
        assert codes(result.warnings) == [Code.UNCONNECTED_PIN, Code.OVERCURRENT]


class TestSpice:
    def test_netlist_has_one_source_per_pole(self) -> None:
        catalog = load_catalog()
        normalized = validate(document(rcd_circuit()), catalog).raise_for_errors()

        netlist = build_netlist(normalized, catalog)

        assert {"ID1:L", "ID1:N", "QF1", "AC1"} <= set(netlist.sources)
        assert netlist.text.count(" DC 0.0\n") == 3

    def test_export_and_round_trip(self) -> None:
        data = staircase(False, True)
        data["components"][2:2] = [comp("ID1", "rcd")]
        data["wires"] = [
            w for w in data["wires"] if (w["from"], w["to"]) != ("QF1.b", "SC1.common")
        ] + [
            {"id": "W20", "from": "QF1.b", "to": "ID1.line_in", "waypoints": []},
            {"id": "W21", "from": "ID1.line_out", "to": "SC1.common", "waypoints": []},
            {"id": "W22", "from": "ID1.neutral_in", "to": "GND1.gnd", "waypoints": []},
            {"id": "W23", "from": "ID1.neutral_out", "to": "H1.b", "waypoints": []},
        ]
        data["wires"] = [
            w for w in data["wires"] if (w["from"], w["to"]) != ("H1.b", "AC1.neutral")
        ]
        catalog = load_catalog()

        text = export_netlist(document(data), catalog)

        assert "VAC1 N1 0 SIN(0 325.2691193458119 50.0)" in text
        assert "VID1_L " in text
        assert "VID1_N " in text
        assert "VSC1 " in text
        assert import_netlist(text, catalog).circuit == document(data)
