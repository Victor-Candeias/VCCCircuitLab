"""Condensadores, bobinas e análise transitória (F2-02): equivalentes DC, validação por análise
e o integrador BDF2 comparado com as soluções analíticas de circuitos RC, RL e RLC."""

import math
from typing import Any

import numpy as np
import pytest

from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.validate import validate
from app.models.circuit import CircuitDocument
from app.solver.mna import simulate_dc
from app.solver.transient import MIN_INTERNAL_STEPS, TransientResult, simulate_transient
from tests.factories import circuit, comp

Code = CircuitErrorCode


def series_circuit(*elements: dict[str, Any], voltage: float = 10.0) -> dict[str, Any]:
    """Fonte de tensão em série com `elements` (pino `a` → `b`), fechada pela terra."""
    components = [comp("V1", "dc_voltage_source", voltageV=voltage), *elements]
    components.append(comp("GND1", "ground"))
    links = [("V1.positive", f"{elements[0]['id']}.a")]
    links += [
        (f"{x['id']}.b", f"{y['id']}.a") for x, y in zip(elements, elements[1:], strict=False)
    ]
    links += [(f"{elements[-1]['id']}.b", "GND1.gnd"), ("V1.negative", "GND1.gnd")]
    return circuit(components, *links)


def run(data: dict[str, Any], stop: float, step: float, **kwargs: Any) -> TransientResult:
    document = CircuitDocument.model_validate(data)
    return simulate_transient(document, stop_time_s=stop, time_step_s=step, **kwargs)


def series(result: TransientResult, component: str, quantity: str) -> np.ndarray:
    return np.array(getattr(result.components[component], quantity))


class TestDc:
    def test_capacitor_is_open_and_inductor_is_short(self) -> None:
        data = series_circuit(
            comp("R1", "resistor", resistanceOhm=100), comp("L1", "inductor"), voltage=12
        )
        data["components"].append(comp("C1", "capacitor"))
        data["wires"].append({"id": "W9", "from": "C1.a", "to": "R1.a", "waypoints": []})
        data["wires"].append({"id": "W10", "from": "C1.b", "to": "GND1.gnd", "waypoints": []})

        result = simulate_dc(CircuitDocument.model_validate(data))

        assert result.components["L1"].voltage_v == 0.0
        assert result.components["L1"].current_a == pytest.approx(0.12)
        assert result.components["C1"].voltage_v == pytest.approx(12.0)
        assert result.components["C1"].current_a == 0.0

    def test_inductor_across_voltage_source_is_a_short_only_in_dc(self) -> None:
        data = series_circuit(comp("L1", "inductor"))
        document = CircuitDocument.model_validate(data)

        dc = validate(document)
        transient = validate(document, analysis="transient")

        assert [e.code for e in dc.errors] == [Code.VOLTAGE_SOURCE_LOOP]
        assert transient.ok

    def test_capacitors_in_series_float_only_in_dc(self) -> None:
        data = series_circuit(comp("C1", "capacitor"), comp("C2", "capacitor"))
        document = CircuitDocument.model_validate(data)

        dc = validate(document)
        transient = validate(document, analysis="transient")

        assert [e.code for e in dc.errors] == [Code.FLOATING_NET]
        assert transient.ok


class TestTransient:
    def test_rc_charge(self) -> None:
        tau = 1e-3  # 1 kΩ × 1 µF
        data = series_circuit(
            comp("R1", "resistor", resistanceOhm=1000), comp("C1", "capacitor", capacitanceF=1e-6)
        )

        result = run(data, 5 * tau, 1e-5)

        t = np.array(result.time_s)
        assert len(t) == 501
        assert t[-1] == 5 * tau
        np.testing.assert_allclose(
            series(result, "C1", "voltage_v"), 10 * (1 - np.exp(-t / tau)), atol=1e-3
        )
        np.testing.assert_allclose(
            series(result, "C1", "current_a"), 0.01 * np.exp(-t / tau), atol=1e-6
        )
        # Convenção passiva: a fonte fornece energia (potência negativa).
        assert all(p <= 0 for p in result.components["V1"].power_w)
        assert result.node_voltages_v.keys() == {n["id"] for n in result_nets(data)}

    def test_rl_current_rise(self) -> None:
        tau = 0.01  # 0.1 H / 10 Ω
        data = series_circuit(
            comp("R1", "resistor", resistanceOhm=10), comp("L1", "inductor", inductanceH=0.1)
        )

        result = run(data, 5 * tau, 1e-4)

        t = np.array(result.time_s)
        np.testing.assert_allclose(
            series(result, "L1", "current_a"), 1 - np.exp(-t / tau), atol=1e-4
        )
        assert result.components["L1"].voltage_v[0] == pytest.approx(10.0)

    def test_underdamped_rlc(self) -> None:
        r, inductance, c = 10.0, 0.01, 1e-5
        data = series_circuit(
            comp("R1", "resistor", resistanceOhm=r),
            comp("L1", "inductor", inductanceH=inductance),
            comp("C1", "capacitor", capacitanceF=c),
        )

        result = run(data, 0.01, 1e-5)

        t = np.array(result.time_s)
        alpha, w0 = r / (2 * inductance), 1 / math.sqrt(inductance * c)
        wd = math.sqrt(w0**2 - alpha**2)
        expected = 10 * (1 - np.exp(-alpha * t) * (np.cos(wd * t) + alpha / wd * np.sin(wd * t)))
        vc = series(result, "C1", "voltage_v")
        assert vc.max() > 15  # sobre-elevação
        np.testing.assert_allclose(vc, expected, atol=1e-2)

    def test_initial_conditions(self) -> None:
        data = circuit(
            [comp("R1", "resistor", resistanceOhm=1000)]
            + [comp("C1", "capacitor", capacitanceF=1e-6, initialVoltageV=5)]
            + [comp("R2", "resistor", resistanceOhm=10)]
            + [comp("L1", "inductor", inductanceH=0.1, initialCurrentA=2)]
            + [comp("GND1", "ground")],
            ("C1.a", "R1.a"),
            ("C1.b", "GND1.gnd"),
            ("R1.b", "GND1.gnd"),
            ("L1.a", "R2.a"),
            ("L1.b", "GND1.gnd"),
            ("R2.b", "GND1.gnd"),
        )

        result = run(data, 5e-3, 1e-5)

        t = np.array(result.time_s)
        vc, il = series(result, "C1", "voltage_v"), series(result, "L1", "current_a")
        np.testing.assert_allclose(vc, 5 * np.exp(-t / 1e-3), atol=1e-3)
        np.testing.assert_allclose(il, 2 * np.exp(-t / 0.01), atol=1e-4)
        assert result.components["C1"].current_a[0] == pytest.approx(-0.005)
        assert result.components["R2"].current_a[0] == pytest.approx(-2.0)

    def test_capacitor_across_source_jumps_at_zero(self) -> None:
        data = series_circuit(comp("C1", "capacitor"))

        result = run(data, 1e-3, 1e-4)

        assert result.components["C1"].voltage_v[0] == pytest.approx(10.0)
        assert result.components["C1"].voltage_v[1:] == pytest.approx([10.0] * 10)
        assert result.components["C1"].current_a[1:] == pytest.approx([0.0] * 10, abs=1e-9)

    def test_output_grid_ends_at_stop_time(self) -> None:
        data = series_circuit(comp("R1", "resistor"))

        result = run(data, 1e-3, 3e-4)

        assert result.time_s == pytest.approx([0, 0.25e-3, 0.5e-3, 0.75e-3, 1e-3])
        assert result.components["R1"].current_a == pytest.approx([0.1] * 5)

    def test_to_json_dict(self) -> None:
        data = series_circuit(comp("R1", "resistor"), comp("C1", "capacitor"))

        body = run(data, 1e-3, 5e-4).to_json_dict()

        assert body["analysis"] == "transient"
        assert body["status"] == "success"
        assert len(body["timeS"]) == 3
        assert body["components"]["C1"].keys() == {"voltageV", "currentA", "powerW"}

    def test_invalid_circuit(self) -> None:
        data = series_circuit(comp("C1", "capacitor"))
        data["components"] = [c for c in data["components"] if c["id"] != "GND1"]
        data["wires"] = [w for w in data["wires"] if "GND1" not in w["from"] + w["to"]]

        with pytest.raises(CircuitValidationError) as exc:
            run(data, 1e-3, 1e-4)

        assert Code.MISSING_GROUND in [e.code for e in exc.value.errors]

    def test_deadline(self) -> None:
        data = series_circuit(comp("R1", "resistor"), comp("C1", "capacitor"))

        with pytest.raises(TimeoutError):
            run(data, 1.0, 1.0 / MIN_INTERNAL_STEPS, timeout_s=0)


def result_nets(data: dict[str, Any]) -> list[dict[str, Any]]:
    report = validate(CircuitDocument.model_validate(data), analysis="transient")
    return [n.model_dump() for n in report.raise_for_errors().document.nets or []]
