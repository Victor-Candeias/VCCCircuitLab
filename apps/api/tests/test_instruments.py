"""Instrumentos virtuais ideais (F2-03): voltímetro (aberto), amperímetro (curto com corrente) e
osciloscópio (sem ramo, lê as tensões das redes dos canais)."""

from typing import Any

import numpy as np
import pytest

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitErrorCode
from app.circuit.validate import validate
from app.models.circuit import CircuitDocument
from app.solver.mna import simulate_dc
from app.solver.transient import simulate_transient
from app.spice.netlist import build_netlist, build_transient_netlist
from tests.factories import circuit, comp

Code = CircuitErrorCode


def measured_divider() -> dict[str, Any]:
    """12 V → AM1 → R1 (100 Ω) → R2 (200 Ω) → terra, VM1 sobre R2, OSC1.ch1 no ponto médio e
    OSC1.ch2 desligado."""
    return circuit(
        [comp("V1", "dc_voltage_source"), comp("AM1", "ammeter"), comp("R1", "resistor")]
        + [comp("R2", "resistor", resistanceOhm=200), comp("VM1", "voltmeter")]
        + [comp("OSC1", "oscilloscope"), comp("GND1", "ground")],
        ("V1.positive", "AM1.positive"),
        ("AM1.negative", "R1.a"),
        ("R1.b", "R2.a"),
        ("R2.b", "V1.negative"),
        ("GND1.gnd", "V1.negative"),
        ("VM1.positive", "R2.a"),
        ("VM1.negative", "R2.b"),
        ("OSC1.ch1", "R2.a"),
    )


def document(data: dict[str, Any]) -> CircuitDocument:
    return CircuitDocument.model_validate(data)


class TestValidation:
    def test_unconnected_probe_pins_are_only_warnings(self) -> None:
        data = measured_divider()
        data["components"].append(comp("VM2", "voltmeter"))
        data["wires"].append({"id": "W9", "from": "VM2.positive", "to": "R1.a", "waypoints": []})

        report = validate(document(data))

        assert report.ok, report.errors
        assert codes_and_refs(report.warnings) == [
            (Code.UNCONNECTED_PIN, ("OSC1.ch2",)),
            (Code.UNCONNECTED_PIN, ("VM2.negative",)),
        ]

    def test_ammeter_across_voltage_source_is_a_short(self) -> None:
        data = measured_divider()
        data["components"].append(comp("AM2", "ammeter"))
        data["wires"] += [
            {"id": "W9", "from": "AM2.positive", "to": "V1.positive", "waypoints": []},
            {"id": "W10", "from": "AM2.negative", "to": "V1.negative", "waypoints": []},
        ]

        assert [e.code for e in validate(document(data)).errors] == [Code.VOLTAGE_SOURCE_LOOP]

    def test_voltmeter_does_not_close_a_circuit(self) -> None:
        data = measured_divider()
        data["components"] += [comp("R3", "resistor"), comp("VM2", "voltmeter")]
        data["wires"] += [
            {"id": "W9", "from": "R3.a", "to": "VM2.positive", "waypoints": []},
            {"id": "W10", "from": "VM2.negative", "to": "GND1.gnd", "waypoints": []},
        ]

        report = validate(document(data))

        assert [e.code for e in report.errors] == [Code.FLOATING_NET]
        assert "R3.a" in report.errors[0].refs


def codes_and_refs(issues: Any) -> list[tuple[Code, tuple[str, ...]]]:
    return [(i.code, i.refs) for i in issues]


class TestDc:
    def test_readings(self) -> None:
        result = simulate_dc(document(measured_divider()))

        ammeter, voltmeter = result.components["AM1"], result.components["VM1"]
        assert (ammeter.voltage_v, ammeter.current_a, ammeter.power_w) == (
            0,
            pytest.approx(0.04),
            0,
        )
        assert voltmeter.voltage_v == pytest.approx(8)
        assert (voltmeter.current_a, voltmeter.power_w) == (0, 0)
        assert result.components["R2"].current_a == pytest.approx(0.04)
        assert "OSC1" not in result.components

    def test_probe_only_nets_have_no_voltage(self) -> None:
        data = measured_divider()
        data["components"].append(comp("VM2", "voltmeter"))
        data["wires"].append({"id": "W9", "from": "VM2.positive", "to": "R1.a", "waypoints": []})

        result = simulate_dc(document(data))

        normalized = validate(document(data)).raise_for_errors()
        probe_only = {
            n.id
            for n in normalized.document.nets or []
            if n.terminals in (["VM2.negative"], ["OSC1.ch2"])
        }
        assert len(probe_only) == 2
        assert probe_only.isdisjoint(result.node_voltages_v)
        assert len(result.node_voltages_v) == len(normalized.document.nets or []) - 2
        assert "VM2" not in result.components


class TestTransient:
    def test_readings_follow_the_circuit(self) -> None:
        result = simulate_transient(
            document(measured_divider()), stop_time_s=1e-3, time_step_s=1e-4
        )

        assert np.allclose(result.components["VM1"].voltage_v, 8)
        assert np.allclose(result.components["AM1"].current_a, 0.04)
        assert "OSC1" not in result.components


class TestNetlist:
    def test_instruments_in_spice(self) -> None:
        catalog = load_catalog()
        normalized = validate(document(measured_divider()), catalog).raise_for_errors()

        netlist = build_netlist(normalized, catalog)
        transient = build_transient_netlist(
            normalized, catalog, stop_time_s=1e-3, time_step_s=1e-5, max_step_s=5e-7
        )

        elements = [line for line in netlist.text.splitlines() if line[:1] in "VRIC"]
        assert elements == ["V1 n1 0 DC 12.0", "V2 n1 n2 DC 0.0", "R3 n2 n3 100.0"] + [
            "R4 n3 0 200.0"
        ]
        assert netlist.sources == {"V1": "v1", "AM1": "v2"}
        assert len(netlist.nodes) == len(normalized.document.nets or []) - 1
        assert "V2 n1 n2 DC 0.0" in transient.text.splitlines()
