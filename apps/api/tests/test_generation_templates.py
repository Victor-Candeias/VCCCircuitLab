"""Testes dos templates de geração (E3-01): cada um tem de produzir um `CircuitDocument`
válido e simulável, com resultados consistentes com a fórmula analítica do template.
"""

import math

import pytest
from pydantic import ValidationError

from app.circuit.catalog import load_catalog
from app.circuit.validate import validate
from app.generation.params import (
    ParallelDcParams,
    SeriesDcParams,
    StaircaseLightingParams,
    SwitchCircuitParams,
    VoltageDividerParams,
)
from app.generation.registry import TEMPLATES, get_template
from app.generation.templates import (
    build_parallel_dc,
    build_series_dc,
    build_staircase_lighting,
    build_switch_circuit,
    build_voltage_divider,
)
from app.solver.mna import simulate_dc


def _assert_valid(document: object) -> None:
    report = validate(document, load_catalog())  # type: ignore[arg-type]
    assert report.ok, report.errors


class TestSeriesDc:
    def test_builds_valid_document(self) -> None:
        document = build_series_dc(SeriesDcParams(voltageV=12, resistorsOhm=[100, 220, 330]))

        _assert_valid(document)
        assert [c.id for c in document.components] == ["V1", "R1", "R2", "R3", "GND1"]

    def test_current_matches_analytic_formula(self) -> None:
        document = build_series_dc(SeriesDcParams(voltageV=12, resistorsOhm=[100, 220, 330]))

        result = simulate_dc(document, load_catalog())

        expected_current = 12 / (100 + 220 + 330)
        for cid, resistance in (("R1", 100), ("R2", 220), ("R3", 330)):
            assert result.components[cid].current_a == pytest.approx(expected_current)
            assert result.components[cid].voltage_v == pytest.approx(expected_current * resistance)

    def test_single_resistor(self) -> None:
        document = build_series_dc(SeriesDcParams(voltageV=9, resistorsOhm=[100]))

        result = simulate_dc(document, load_catalog())

        assert result.components["R1"].current_a == pytest.approx(0.09)

    def test_rejects_non_positive_resistance(self) -> None:
        with pytest.raises(ValidationError):
            SeriesDcParams(voltageV=12, resistorsOhm=[100, 0])

    def test_rejects_empty_resistor_list(self) -> None:
        with pytest.raises(ValidationError):
            SeriesDcParams(voltageV=12, resistorsOhm=[])

    def test_rejects_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            SeriesDcParams(voltageV=12, resistorsOhm=[100], extra=True)


class TestParallelDc:
    def test_builds_valid_document(self) -> None:
        document = build_parallel_dc(ParallelDcParams(voltageV=12, resistorsOhm=[100, 200]))

        _assert_valid(document)

    def test_each_branch_sees_full_voltage(self) -> None:
        document = build_parallel_dc(ParallelDcParams(voltageV=12, resistorsOhm=[100, 200, 300]))

        result = simulate_dc(document, load_catalog())

        for cid, resistance in (("R1", 100), ("R2", 200), ("R3", 300)):
            assert result.components[cid].voltage_v == pytest.approx(12)
            assert result.components[cid].current_a == pytest.approx(12 / resistance)
        assert result.components["V1"].current_a == pytest.approx(-(12 / 100 + 12 / 200 + 12 / 300))


class TestVoltageDivider:
    def test_builds_valid_document(self) -> None:
        document = build_voltage_divider(VoltageDividerParams(voltageV=12, resistorsOhm=[100, 220]))

        _assert_valid(document)

    def test_tap_voltage_matches_divider_formula(self) -> None:
        document = build_voltage_divider(VoltageDividerParams(voltageV=12, resistorsOhm=[100, 220]))

        normalized = validate(document, load_catalog()).normalized
        assert normalized is not None
        result = simulate_dc(document, load_catalog())

        expected_tap = 12 * 220 / (100 + 220)
        tap_net = next(
            n.id
            for n in normalized.document.nets or []
            if "R1.b" in n.terminals or "R2.a" in n.terminals
        )
        assert result.node_voltages_v[tap_net] == pytest.approx(expected_tap)

    def test_rejects_single_resistor(self) -> None:
        with pytest.raises(ValidationError):
            VoltageDividerParams(voltageV=12, resistorsOhm=[100])


class TestSwitchCircuit:
    def test_builds_valid_document(self) -> None:
        document = build_switch_circuit(SwitchCircuitParams(voltageV=12, loadOhm=100, closed=True))

        _assert_valid(document)

    def test_closed_switch_allows_current(self) -> None:
        document = build_switch_circuit(SwitchCircuitParams(voltageV=12, loadOhm=100, closed=True))

        result = simulate_dc(document, load_catalog())

        assert result.components["R1"].current_a == pytest.approx(0.12)
        assert result.components["S1"].current_a == pytest.approx(0.12)

    def test_open_switch_blocks_current(self) -> None:
        document = build_switch_circuit(SwitchCircuitParams(voltageV=12, loadOhm=100, closed=False))

        result = simulate_dc(document, load_catalog())

        assert result.components["R1"].current_a == pytest.approx(0, abs=1e-12)
        assert result.components["S1"].current_a == pytest.approx(0, abs=1e-12)
        assert result.components["V1"].current_a == pytest.approx(0, abs=1e-12)

    def test_closed_defaults_to_true(self) -> None:
        params = SwitchCircuitParams(voltageV=12, loadOhm=100)

        assert params.closed is True


class TestStaircaseLighting:
    def test_builds_valid_document_with_defaults(self) -> None:
        document = build_staircase_lighting(StaircaseLightingParams())

        report = validate(document, load_catalog())
        assert report.ok, report.errors
        assert [c.id for c in document.components] == ["AC1", "QF1", "SC1", "SC2", "HR1", "GND1"]
        # Rede com disjuntor: só o aviso de segurança; nenhum pino por ligar.
        assert [w.code for w in report.warnings] == ["MAINS_VOLTAGE"]

    @pytest.mark.parametrize(
        ("first", "second", "lit"),
        [(False, False, False), (True, False, True), (False, True, True), (True, True, False)],
    )
    def test_either_switch_toggles_the_lamp(self, first: bool, second: bool, lit: bool) -> None:
        params = StaircaseLightingParams(switch1ToL2=first, switch2ToL2=second)

        result = simulate_dc(build_staircase_lighting(params), load_catalog())

        lamp = result.components["HR1"]
        assert lamp.voltage_v == pytest.approx(230 if lit else 0)
        assert lamp.power_w == pytest.approx(60 if lit else 0)

    def test_parameters_reach_the_components(self) -> None:
        params = StaircaseLightingParams(
            voltageV=400, frequencyHz=60, lampPowerW=100, breakerRatedA=16, switch2ToL2=True
        )

        document = build_staircase_lighting(params)

        props = {c.id: c.properties for c in document.components}
        assert props["AC1"] == {"voltageV": 400, "frequencyHz": 60}
        assert props["QF1"] == {"closed": True, "ratedCurrentA": 16}
        assert props["HR1"] == {"ratedVoltageV": 400, "ratedPowerW": 100}
        assert props["SC2"] == {"toL2": True}

    @pytest.mark.parametrize(
        "parameters",
        [{"voltageV": 401}, {"frequencyHz": 45}, {"lampPowerW": 0}, {"breakerRatedA": 200}],
    )
    def test_rejects_values_outside_the_catalog_limits(self, parameters: dict[str, float]) -> None:
        with pytest.raises(ValidationError):
            StaircaseLightingParams(**parameters)


class TestRegistry:
    @pytest.mark.parametrize("name", list(TEMPLATES))
    def test_registered_templates_are_discoverable(self, name: str) -> None:
        spec = get_template(name)

        assert spec.name == name
        assert spec.title
        assert spec.params_model is not None
        assert callable(spec.build)

    def test_unknown_template_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_template("nao_existe")

    @pytest.mark.parametrize("name", list(TEMPLATES))
    def test_registry_builds_valid_documents_with_minimal_params(self, name: str) -> None:
        spec = get_template(name)
        minimal: dict[str, object] = {"voltageV": 12}
        if name == "staircase_lighting":
            pass
        elif name == "switch_circuit":
            minimal["loadOhm"] = 100
        else:
            needs_two = name == "voltage_divider"
            minimal["resistorsOhm"] = [100, 200] if needs_two else [100]

        params = spec.params_model(**minimal)
        document = spec.build(params)

        _assert_valid(document)
        result = simulate_dc(document, load_catalog())
        assert all(math.isfinite(v) for v in result.node_voltages_v.values())
