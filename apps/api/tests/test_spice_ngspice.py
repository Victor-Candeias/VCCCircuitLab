"""ngspice real vs. solver MNA (F2-01). Só corre se o `ngspice` estiver instalado (CI)."""

import shutil
from typing import Any

import pytest

from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, simulate_dc
from app.spice.engine import simulate_dc_ngspice
from tests.factories import FIXTURES, load_analytic_cases, load_fixture

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
