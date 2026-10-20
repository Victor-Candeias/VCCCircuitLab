"""ngspice real vs. solvers internos (F2-01 DC, F2-02 transitória) e netlists exportadas
(F2-05). Só corre se o `ngspice` estiver instalado (CI)."""

import shutil
from typing import Any

import numpy as np
import pytest

from app.circuit.catalog import load_catalog
from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, simulate_dc
from app.solver.transient import TransientResult, simulate_transient
from app.spice.engine import simulate_dc_ngspice, simulate_transient_ngspice
from app.spice.exchange import export_netlist
from app.spice.netlist import RAWFILE_NAME
from app.spice.runner import run_ngspice
from tests.factories import FIXTURES, circuit, comp, load_analytic_cases, load_fixture

pytestmark = pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice não instalado")

TOLERANCE = 1e-6
CIRCUITS = {f"fixture-{p.stem}": p.stem for p in sorted(FIXTURES.glob("*.json"))}
ANALYTIC = {f"analytic-{c.name}": c.circuit for c in load_analytic_cases() if not c.is_error}


def both(data: dict[str, Any]) -> tuple[DcResult, DcResult]:
    document = CircuitDocument.model_validate(data)
    return simulate_dc(document), simulate_dc_ngspice(document, timeout_s=10)


def assert_same(mna: DcResult, spice: DcResult) -> None:
    assert spice.node_voltages_v == pytest.approx(mna.node_voltages_v, rel=TOLERANCE, abs=1e-9)
    assert spice.components.keys() == mna.components.keys()
    for cid, expected in mna.components.items():
        actual = spice.components[cid]
        for field in ("voltage_v", "current_a", "power_w"):
            assert getattr(actual, field) == pytest.approx(
                getattr(expected, field), rel=TOLERANCE, abs=1e-9
            ), f"{cid}.{field}"
    assert spice.warnings == mna.warnings


@pytest.mark.parametrize("name", list(CIRCUITS.values()), ids=list(CIRCUITS))
def test_fixtures_match_mna(name: str) -> None:
    assert_same(*both(load_fixture(name)))


@pytest.mark.parametrize("data", list(ANALYTIC.values()), ids=list(ANALYTIC))
def test_analytic_cases_match_mna(data: dict[str, Any]) -> None:
    assert_same(*both(data))


def _series_circuit(*elements: dict[str, Any], initial: dict[str, Any] | None = None) -> dict:
    components = [comp("V1", "dc_voltage_source", voltageV=10), *elements, comp("GND1", "ground")]
    links = [("V1.positive", f"{elements[0]['id']}.a")]
    links += [
        (f"{x['id']}.b", f"{y['id']}.a") for x, y in zip(elements, elements[1:], strict=False)
    ]
    links += [(f"{elements[-1]['id']}.b", "GND1.gnd"), ("V1.negative", "GND1.gnd")]
    return circuit(components, *links)


TRANSIENT = {
    "rc": (
        _series_circuit(
            comp("R1", "resistor", resistanceOhm=1000), comp("C1", "capacitor", capacitanceF=1e-6)
        ),
        5e-3,
    ),
    "rl": (
        _series_circuit(
            comp("R1", "resistor", resistanceOhm=10), comp("L1", "inductor", inductanceH=0.1)
        ),
        0.05,
    ),
    "rlc": (
        _series_circuit(
            comp("R1", "resistor", resistanceOhm=10),
            comp("L1", "inductor", inductanceH=0.01, initialCurrentA=0.1),
            comp("C1", "capacitor", capacitanceF=1e-5, initialVoltageV=2),
        ),
        0.01,
    ),
    "instrumentos": (load_fixture("medicoes-rc"), 5e-3),
    "rc-diodo": (
        circuit(
            [comp("V1", "dc_voltage_source", voltageV=10), comp("R1", "resistor")]
            + [comp("C1", "capacitor", capacitanceF=1e-5), comp("D1", "diode")]
            + [comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "C1.a"),
            ("C1.a", "D1.anode"),
            ("C1.b", "GND1.gnd"),
            ("D1.cathode", "GND1.gnd"),
            ("V1.negative", "GND1.gnd"),
        ),
        5e-3,
    ),
    "transistor-led": (load_fixture("transistor-led"), 1e-3),
}


@pytest.mark.parametrize(("data", "stop"), list(TRANSIENT.values()), ids=list(TRANSIENT))
def test_transient_matches_mna(data: dict[str, Any], stop: float) -> None:
    document = CircuitDocument.model_validate(data)
    step = stop / 200
    mna = simulate_transient(document, stop_time_s=stop, time_step_s=step)
    spice = simulate_transient_ngspice(document, stop_time_s=stop, time_step_s=step, timeout_s=10)

    assert spice.time_s == pytest.approx(mna.time_s, abs=stop * 1e-9)
    assert spice.components.keys() == mna.components.keys()
    # t = 0 fica de fora: com `uic` o ngspice pode reportar o estado antes do salto inicial.
    for cid, expected in mna.components.items():
        for field in ("voltage_v", "current_a"):
            _assert_close(spice, cid, field, getattr(expected, field))


def _assert_close(spice: TransientResult, cid: str, field: str, expected: list[float]) -> None:
    reference = np.array(expected[1:])
    actual = np.array(getattr(spice.components[cid], field)[1:])
    scale = max(float(np.max(np.abs(reference))), 1e-9)
    np.testing.assert_allclose(actual, reference, atol=5e-3 * scale, err_msg=f"{cid}.{field}")


@pytest.mark.parametrize("name", list(CIRCUITS.values()), ids=list(CIRCUITS))
def test_exported_netlist_runs_in_ngspice(name: str) -> None:
    """F2-05: a netlist exportada é aceite pelo ngspice e dá as mesmas tensões nas resistências."""
    document = CircuitDocument.model_validate(load_fixture(name))
    mna = simulate_dc(document)
    exported = export_netlist(document, load_catalog())
    elements = [line for line in exported.splitlines()[:-1] if not line.startswith(("*", "."))]
    models = [line for line in exported.splitlines() if line.startswith(".model")]
    control = [".control", "set filetype=ascii", "op", f"write {RAWFILE_NAME}", ".endc", ".end"]
    raw = run_ngspice("\n".join(["* exportada", *elements, *models, *control, ""]), 10)

    def volts(node: str) -> float:
        return 0.0 if node == "0" else raw.voltages[node.lower()]

    resistors = {c.id: c for c in document.components if c.type == "resistor"}
    checked = 0
    for line in elements:
        element, a, b, *_ = line.split()
        cid = next((r for r in resistors if element in (r.replace("-", "_"), "R" + r)), None)
        if cid is None:
            continue
        assert volts(a) - volts(b) == pytest.approx(
            mna.components[cid].voltage_v, rel=TOLERANCE, abs=1e-9
        )
        checked += 1
    assert checked == len(resistors)
