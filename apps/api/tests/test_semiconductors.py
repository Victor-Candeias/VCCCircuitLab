"""Semicondutores (F2-04): díodo/LED e transístores NPN/PNP resolvidos pelo método de Newton,
comparados com soluções independentes (bisseção escalar e relações do modelo)."""

import math
from typing import Any

import numpy as np
import pytest

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.validate import validate
from app.models.circuit import CircuitDocument
from app.solver import semiconductors
from app.solver.mna import simulate_dc
from app.solver.semiconductors import GMIN, THERMAL_VOLTAGE_V
from app.solver.transient import simulate_transient
from app.spice.netlist import build_netlist, build_transient_netlist
from tests.factories import circuit, comp, load_fixture

Code = CircuitErrorCode
DIODE_VT = 2 * THERMAL_VOLTAGE_V


def document(data: dict[str, Any]) -> CircuitDocument:
    return CircuitDocument.model_validate(data)


def saturation(forward_voltage: float, forward_current: float) -> float:
    return forward_current / math.expm1(forward_voltage / DIODE_VT)


def diode_current(v: float, is_: float) -> float:
    return is_ * math.expm1(v / DIODE_VT) + GMIN * v


def bisect(f: Any, low: float, high: float) -> float:
    for _ in range(200):
        mid = (low + high) / 2
        if f(low) * f(mid) <= 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def source_resistor_diode(
    volts: float = 5.0, ohms: float = 1000.0, diode: str = "diode", **props: Any
) -> dict[str, Any]:
    """V1 → R1 → D1 (ânodo) → terra."""
    return circuit(
        [
            comp("V1", "dc_voltage_source", voltageV=volts),
            comp("R1", "resistor", resistanceOhm=ohms),
        ]
        + [comp("D1", diode, **props), comp("GND1", "ground")],
        ("V1.positive", "R1.a"),
        ("R1.b", "D1.anode"),
        ("D1.cathode", "V1.negative"),
        ("GND1.gnd", "V1.negative"),
    )


def npn_stage(base_current: float = 1e-5, vcc: float = 10.0, rc: float = 1000.0) -> dict:
    """Emissor comum: Vcc → Rc → coletor; fonte de corrente na base; emissor à terra."""
    return circuit(
        [comp("V1", "dc_voltage_source", voltageV=vcc), comp("R1", "resistor", resistanceOhm=rc)]
        + [comp("I1", "dc_current_source", currentA=base_current)]
        + [comp("Q1", "npn_transistor"), comp("GND1", "ground")],
        ("V1.positive", "R1.a"),
        ("R1.b", "Q1.collector"),
        ("I1.positive", "Q1.base"),
        ("I1.negative", "V1.negative"),
        ("Q1.emitter", "V1.negative"),
        ("GND1.gnd", "V1.negative"),
    )


class TestDiode:
    def test_forward_point_matches_the_catalog_properties(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source", currentA=0.01), comp("D1", "diode")]
            + [comp("GND1", "ground")],
            ("I1.positive", "D1.anode"),
            ("D1.cathode", "I1.negative"),
            ("GND1.gnd", "I1.negative"),
        )

        d1 = simulate_dc(document(data)).components["D1"]

        assert d1.current_a == pytest.approx(0.01, rel=1e-9)
        assert d1.voltage_v == pytest.approx(0.7, abs=1e-6)

    @pytest.mark.parametrize(
        ("volts", "ohms", "diode", "props"),
        [
            (5.0, 1000.0, "diode", {}),
            (0.3, 10.0, "diode", {}),
            (9.0, 350.0, "led", {}),
            (12.0, 50.0, "led", {"forwardVoltageV": 3.2, "forwardCurrentA": 0.02}),
        ],
    )
    def test_series_resistor_matches_scalar_solution(
        self, volts: float, ohms: float, diode: str, props: dict[str, float]
    ) -> None:
        defaults = {"diode": (0.7, 0.01), "led": (2.0, 0.02)}[diode]
        is_ = saturation(
            props.get("forwardVoltageV", defaults[0]), props.get("forwardCurrentA", defaults[1])
        )
        vd = bisect(lambda v: (volts - v) / ohms - diode_current(v, is_), 0.0, volts)

        result = simulate_dc(document(source_resistor_diode(volts, ohms, diode, **props)))

        d1, r1 = result.components["D1"], result.components["R1"]
        assert d1.voltage_v == pytest.approx(vd, abs=1e-9)
        assert d1.current_a == pytest.approx((volts - vd) / ohms, rel=1e-6)
        assert r1.current_a == pytest.approx(d1.current_a, rel=1e-9)
        assert d1.power_w == pytest.approx(d1.voltage_v * d1.current_a)
        assert list(result.components) == ["V1", "R1", "D1"]

    def test_reverse_bias_only_leaks(self) -> None:
        data = source_resistor_diode()
        data["wires"][1:3] = [
            {"id": "W2", "from": "R1.b", "to": "D1.cathode", "waypoints": []},
            {"id": "W3", "from": "D1.anode", "to": "V1.negative", "waypoints": []},
        ]

        d1 = simulate_dc(document(data)).components["D1"]

        is_ = saturation(0.7, 0.01)
        assert d1.current_a == pytest.approx(-is_ - GMIN * 5.0, rel=1e-3)
        assert d1.voltage_v == pytest.approx(-5.0 - 1000.0 * d1.current_a, abs=1e-9)

    def test_source_stepping_rescues_a_non_converging_newton(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        direct = simulate_dc(document(source_resistor_diode(volts=50.0, ohms=1.0)))
        monkeypatch.setattr(semiconductors, "MAX_ITERATIONS", 8)

        stepped = simulate_dc(document(source_resistor_diode(volts=50.0, ohms=1.0)))

        assert stepped.components["D1"].current_a == pytest.approx(
            direct.components["D1"].current_a, rel=1e-9
        )

    def test_no_convergence_is_a_structured_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(semiconductors, "MAX_ITERATIONS", 1)

        with pytest.raises(CircuitValidationError) as exc:
            simulate_dc(document(source_resistor_diode()))

        assert [e.code for e in exc.value.errors] == [Code.NO_CONVERGENCE]


class TestBipolarTransistor:
    def test_npn_active_region_follows_beta(self) -> None:
        result = simulate_dc(document(npn_stage(base_current=1e-5)))

        q1 = result.components["Q1"]
        ic = q1.current_a
        assert ic == pytest.approx(100 * 1e-5, rel=1e-6)
        assert q1.voltage_v == pytest.approx(10.0 - 1000.0 * ic, abs=1e-9)
        vbe = result.node_voltages_v[_net(npn_stage(), "Q1.base")]
        assert vbe == pytest.approx(THERMAL_VOLTAGE_V * math.log(ic / 1e-14 + 1), abs=1e-6)
        assert q1.power_w == pytest.approx(q1.voltage_v * ic + vbe * 1e-5, rel=1e-9)

    def test_npn_saturates_when_the_base_is_overdriven(self) -> None:
        result = simulate_dc(document(npn_stage(base_current=1e-3)))

        q1 = result.components["Q1"]
        assert 0 < q1.voltage_v < 0.2
        assert q1.current_a < 100 * 1e-3
        assert q1.current_a == pytest.approx((10.0 - q1.voltage_v) / 1000.0, rel=1e-9)

    def test_pnp_mirrors_the_npn(self) -> None:
        npn = simulate_dc(document(npn_stage(base_current=1e-5)))
        data = npn_stage(base_current=1e-5)
        data["components"][3] = comp("Q1", "pnp_transistor")
        for wire in data["wires"]:
            for end in ("from", "to"):
                wire[end] = {
                    "V1.positive": "V1.negative",
                    "V1.negative": "V1.positive",
                    "I1.positive": "I1.negative",
                    "I1.negative": "I1.positive",
                }.get(wire[end], wire[end])

        pnp = simulate_dc(document(data))

        assert pnp.components["Q1"].current_a == pytest.approx(
            -npn.components["Q1"].current_a, rel=1e-9
        )
        assert pnp.components["Q1"].voltage_v == pytest.approx(
            -npn.components["Q1"].voltage_v, rel=1e-9
        )
        assert pnp.components["Q1"].power_w == pytest.approx(npn.components["Q1"].power_w, rel=1e-9)


class TestExample:
    def test_transistor_switches_the_led(self) -> None:
        data = load_fixture("transistor-led")

        on = simulate_dc(document(data)).components
        data["components"][1]["properties"]["closed"] = False
        off = simulate_dc(document(data)).components

        assert on["D1"].current_a == pytest.approx(0.02, rel=0.05)
        assert on["Q1"].current_a == pytest.approx(on["D1"].current_a, rel=1e-9)
        assert on["Q1"].voltage_v < 0.2
        assert on["RB"].current_a * 100 > on["Q1"].current_a
        assert abs(off["D1"].current_a) < 1e-6
        assert off["RB"].current_a == 0.0


class TestValidation:
    def test_nets_joined_only_by_junctions_are_not_floating(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source", voltageV=5.0), comp("D1", "diode")]
            + [comp("D2", "led"), comp("GND1", "ground")],
            ("V1.positive", "D1.anode"),
            ("D1.cathode", "D2.anode"),
            ("D2.cathode", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        report = validate(document(data))
        result = simulate_dc(document(data))

        assert report.ok, report.errors
        assert report.warnings == ()
        d1, d2 = result.components["D1"], result.components["D2"]
        assert d1.current_a == pytest.approx(d2.current_a, rel=1e-9)
        assert d1.voltage_v + d2.voltage_v == pytest.approx(5.0, abs=1e-9)

    def test_missing_transistor_pin_is_rejected(self) -> None:
        data = npn_stage()
        data["components"][3]["pins"] = ["collector", "base"]

        report = validate(document(data))

        assert Code.MISSING_PIN in [e.code for e in report.errors]


class TestTransient:
    def test_capacitor_across_diode_settles_on_the_operating_point(self) -> None:
        data = source_resistor_diode()
        data["components"].append(comp("C1", "capacitor", capacitanceF=1e-6))
        data["wires"] += [
            {"id": "W8", "from": "C1.a", "to": "D1.anode", "waypoints": []},
            {"id": "W9", "from": "C1.b", "to": "D1.cathode", "waypoints": []},
        ]
        dc = simulate_dc(document(data))

        result = simulate_transient(document(data), stop_time_s=0.01, time_step_s=1e-4)

        d1, r1, c1 = (result.components[c] for c in ("D1", "R1", "C1"))
        assert d1.voltage_v[0] == pytest.approx(0.0, abs=1e-12)
        assert np.all(np.diff(d1.voltage_v) >= -1e-12)
        assert d1.voltage_v[-1] == pytest.approx(dc.components["D1"].voltage_v, abs=1e-6)
        np.testing.assert_allclose(
            np.array(r1.current_a), np.array(c1.current_a) + np.array(d1.current_a), atol=1e-9
        )
        assert list(result.components) == ["V1", "R1", "D1", "C1"]

    def test_transistor_switch_is_steady(self) -> None:
        dc = simulate_dc(document(npn_stage()))

        result = simulate_transient(document(npn_stage()), stop_time_s=1e-3, time_step_s=1e-4)

        np.testing.assert_allclose(
            result.components["Q1"].current_a, dc.components["Q1"].current_a, rtol=1e-9
        )


class TestNetlist:
    def test_devices_have_models_and_sense_sources(self) -> None:
        data = npn_stage()
        data["components"].append(comp("D1", "led"))
        data["wires"] += [
            {"id": "W8", "from": "D1.anode", "to": "Q1.collector", "waypoints": []},
            {"id": "W9", "from": "D1.cathode", "to": "Q1.emitter", "waypoints": []},
        ]
        catalog = load_catalog()
        normalized = validate(document(data), catalog).raise_for_errors()

        netlist = build_netlist(normalized, catalog)

        lines = netlist.text.splitlines()
        net_of = normalized.terminal_to_net
        collector, base = (netlist.nodes[net_of[t]] for t in ("Q1.collector", "Q1.base"))
        assert f"VQC1 {collector} qc1 DC 0" in lines
        assert f"VQB1 {base} qb1 DC 0" in lines
        assert "Q1 qc1 qb1 0 QM1" in lines
        assert ".model QM1 NPN(IS=1e-14 BF=100.0 BR=1.0)" in lines
        assert f"VD2 {collector} d2 DC 0" in lines
        assert "D2 d2 0 DM2" in lines
        assert any(line.startswith(".model DM2 D(IS=") and "N=2.0)" in line for line in lines)
        assert netlist.device_sources == {"Q1": ("vqc1", "vqb1"), "D1": ("vd2",)}

        transient = build_transient_netlist(
            normalized, catalog, stop_time_s=1e-3, time_step_s=1e-5, max_step_s=1e-6
        )
        assert "Q1 qc1 qb1 0 QM1" in transient.text.splitlines()


def _net(data: dict[str, Any], terminal: str) -> str:
    return validate(document(data)).raise_for_errors().terminal_to_net[terminal]
