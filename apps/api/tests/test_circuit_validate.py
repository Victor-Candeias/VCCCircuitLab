import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.circuit.catalog import CATALOG_PATH, ComponentCatalog, load_catalog
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.circuit.validate import ValidationReport, validate
from app.models.circuit import CircuitDocument, Component
from tests.factories import FIXTURES, PACKAGE, PINS, circuit, comp, source_resistor

Code = CircuitErrorCode


def run(data: dict[str, Any]) -> ValidationReport:
    return validate(CircuitDocument.model_validate(data))


def codes(issues: tuple[CircuitError, ...]) -> list[Code]:
    return [i.code for i in issues]


class TestCatalog:
    def test_bundled_copy_matches_package_catalog(self) -> None:
        original = json.loads((PACKAGE / "catalog/components.json").read_text(encoding="utf-8"))

        assert json.loads(CATALOG_PATH.read_text(encoding="utf-8")) == original

    def test_loads_pins_properties_and_models(self) -> None:
        catalog = load_catalog()

        assert set(catalog.components) == set(PINS)
        resistor = catalog.components["resistor"]
        assert resistor.pins == ("a", "b")
        assert resistor.properties["resistanceOhm"].exclusive_minimum == 0
        assert catalog.components["dc_voltage_source"].properties["voltageV"].maximum == 120
        assert catalog.components["ground"].simulation_model == "ground"


class TestValidCircuits:
    @pytest.mark.parametrize("name", ["fonte-resistencia", "paralelo-juncao", "ramificado"])
    def test_fixtures_are_valid(self, name: str) -> None:
        report = validate(
            CircuitDocument.model_validate_json((FIXTURES / f"{name}.json").read_text("utf-8"))
        )

        assert report.ok, report.errors
        assert report.warnings == ()
        assert report.raise_for_errors() is report.normalized

    def test_series(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor"), comp("R2", "resistor")]
            + [comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "R2.a"),
            ("R2.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        report = run(data)

        assert report.ok
        assert report.normalized is not None
        assert len(report.normalized.document.nets or []) == 3

    @pytest.mark.parametrize("closed", [True, False])
    def test_switch_open_or_closed_is_valid(self, closed: bool) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("S1", "switch", closed=closed)]
            + [comp("H1", "lamp"), comp("GND1", "ground")],
            ("V1.positive", "S1.a"),
            ("S1.b", "H1.a"),
            ("H1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        report = run(data)

        assert report.ok, report.errors

    def test_current_source_with_load(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source"), comp("R1", "resistor"), comp("GND1", "ground")],
            ("I1.positive", "R1.a"),
            ("R1.b", "I1.negative"),
            ("GND1.gnd", "I1.negative"),
        )

        assert run(data).ok

    def test_closed_switches_in_parallel_are_not_a_conflict(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor"), comp("R2", "resistor")]
            + [comp("S1", "switch"), comp("S2", "switch"), comp("GND1", "ground")],
            ("V1.positive", "R1.a"),
            ("R1.b", "S1.a"),
            ("R1.b", "S2.a"),
            ("S1.b", "R2.a"),
            ("S2.b", "R2.a"),
            ("R2.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        assert run(data).ok

    def test_closed_switches_shorting_the_source(self) -> None:
        data = source_resistor()
        data["components"] += [comp("S1", "switch"), comp("S2", "switch")]
        data["wires"] += [
            {"id": "W4", "from": "S1.a", "to": "R1.a", "waypoints": []},
            {"id": "W5", "from": "S1.b", "to": "R1.b", "waypoints": []},
            {"id": "W6", "from": "S2.a", "to": "R1.a", "waypoints": []},
            {"id": "W7", "from": "S2.b", "to": "R1.b", "waypoints": []},
        ]

        report = run(data)

        assert codes(report.errors) == [Code.VOLTAGE_SOURCE_LOOP]
        assert report.errors[0].refs == ("S1", "V1")

    def test_two_grounds_in_separate_subcircuits(self) -> None:
        data = source_resistor()
        data["components"] += [comp("V2", "dc_voltage_source"), comp("R2", "resistor")]
        data["components"] += [comp("GND2", "ground")]
        data["wires"] += [
            {"id": "W4", "from": "V2.positive", "to": "R2.a", "waypoints": []},
            {"id": "W5", "from": "R2.b", "to": "V2.negative", "waypoints": []},
            {"id": "W6", "from": "GND2.gnd", "to": "V2.negative", "waypoints": []},
        ]

        assert run(data).ok


class TestGroundAndFloating:
    def test_missing_ground(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("R1", "resistor")],
            ("V1.positive", "R1.a"),
            ("R1.b", "V1.negative"),
        )

        report = run(data)

        assert codes(report.errors) == [Code.MISSING_GROUND]
        with pytest.raises(CircuitValidationError):
            report.raise_for_errors()

    def test_empty_circuit_has_no_ground(self) -> None:
        assert codes(run(circuit([])).errors) == [Code.MISSING_GROUND]

    def test_isolated_subcircuit_is_floating(self) -> None:
        data = source_resistor()
        data["components"] += [comp("R2", "resistor"), comp("R3", "resistor")]
        data["wires"] += [{"id": "W4", "from": "R2.b", "to": "R3.a", "waypoints": []}]

        report = run(data)

        assert codes(report.errors) == [Code.FLOATING_NET]
        error = report.errors[0]
        assert error.refs[-4:] == ("R2.a", "R2.b", "R3.a", "R3.b")
        assert codes(report.warnings) == [Code.UNCONNECTED_PIN] * 2
        assert [w.refs for w in report.warnings] == [("R2.a",), ("R3.b",)]

    def test_unconnected_ground_pin_leaves_circuit_floating(self) -> None:
        data = source_resistor()
        data["wires"].pop()

        report = run(data)

        assert codes(report.errors) == [Code.FLOATING_NET]
        assert [w.refs for w in report.warnings] == [("GND1.gnd",)]

    def test_open_switch_leaving_dangling_branch_is_floating(self) -> None:
        data = source_resistor()
        data["components"] += [comp("S1", "switch", closed=False), comp("H1", "lamp")]
        data["wires"] += [
            {"id": "W4", "from": "R1.a", "to": "S1.a", "waypoints": []},
            {"id": "W5", "from": "S1.b", "to": "H1.a", "waypoints": []},
        ]

        report = run(data)

        assert codes(report.errors) == [Code.FLOATING_NET]
        assert codes(report.warnings) == [Code.UNCONNECTED_PIN]
        assert "S1.b" in report.errors[0].refs

    def test_dangling_resistor_pin_is_only_a_warning(self) -> None:
        data = source_resistor()
        data["components"].append(comp("R2", "resistor"))
        data["wires"].append({"id": "W4", "from": "R2.a", "to": "R1.a", "waypoints": []})

        report = run(data)

        assert report.ok
        assert [w.refs for w in report.warnings] == [("R2.b",)]


class TestIdealSourceConflicts:
    def test_voltage_sources_in_parallel(self) -> None:
        data = source_resistor()
        data["components"].append(comp("V2", "dc_voltage_source", voltageV=5))
        data["wires"] += [
            {"id": "W4", "from": "V2.positive", "to": "V1.positive", "waypoints": []},
            {"id": "W5", "from": "V2.negative", "to": "V1.negative", "waypoints": []},
        ]

        report = run(data)

        assert codes(report.errors) == [Code.VOLTAGE_SOURCE_LOOP]
        assert report.errors[0].refs == ("V1", "V2")

    def test_voltage_source_shorted_by_wire(self) -> None:
        data = source_resistor()
        data["wires"].append({"id": "W4", "from": "V1.positive", "to": "R1.b", "waypoints": []})

        report = run(data)

        assert codes(report.errors) == [Code.VOLTAGE_SOURCE_LOOP]
        assert report.errors[0].refs == ("V1",)
        assert "curto-circuito" in report.errors[0].message

    def test_voltage_source_shorted_by_closed_switch(self) -> None:
        data = source_resistor()
        data["components"].append(comp("S1", "switch", closed=True))
        data["wires"] += [
            {"id": "W4", "from": "S1.a", "to": "V1.positive", "waypoints": []},
            {"id": "W5", "from": "S1.b", "to": "V1.negative", "waypoints": []},
        ]

        report = run(data)

        assert codes(report.errors) == [Code.VOLTAGE_SOURCE_LOOP]
        assert report.errors[0].refs == ("S1", "V1")

    def test_open_switch_does_not_short_voltage_source(self) -> None:
        data = source_resistor()
        data["components"].append(comp("S1", "switch", closed=False))
        data["wires"] += [
            {"id": "W4", "from": "S1.a", "to": "V1.positive", "waypoints": []},
            {"id": "W5", "from": "S1.b", "to": "V1.negative", "waypoints": []},
        ]

        assert run(data).ok

    def test_voltage_source_between_two_grounds(self) -> None:
        data = source_resistor()
        data["components"].append(comp("GND2", "ground"))
        data["wires"].append({"id": "W4", "from": "GND2.gnd", "to": "V1.positive", "waypoints": []})

        report = run(data)

        assert codes(report.errors) == [Code.VOLTAGE_SOURCE_LOOP]
        assert set(report.errors[0].refs) == {"GND1", "GND2", "V1"}
        assert report.errors[0].refs[-1] == "V1"

    def test_voltage_sources_in_series_are_valid(self) -> None:
        data = circuit(
            [comp("V1", "dc_voltage_source"), comp("V2", "dc_voltage_source")]
            + [comp("R1", "resistor"), comp("GND1", "ground")],
            ("V1.positive", "V2.negative"),
            ("V2.positive", "R1.a"),
            ("R1.b", "V1.negative"),
            ("GND1.gnd", "V1.negative"),
        )

        assert run(data).ok

    def test_current_sources_in_series(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source"), comp("I2", "dc_current_source", currentA=0.2)]
            + [comp("R1", "resistor"), comp("GND1", "ground")],
            ("I1.positive", "I2.negative"),
            ("I2.positive", "R1.a"),
            ("R1.b", "I1.negative"),
            ("GND1.gnd", "I1.negative"),
        )

        report = run(data)

        assert codes(report.errors) == [Code.CURRENT_SOURCE_CUTSET]
        assert report.errors[0].refs[:2] == ("I1", "I2")

    def test_open_circuited_current_source(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source"), comp("GND1", "ground")],
            ("GND1.gnd", "I1.negative"),
        )

        report = run(data)

        assert codes(report.errors) == [Code.CURRENT_SOURCE_CUTSET]
        assert codes(report.warnings) == [Code.UNCONNECTED_PIN]

    def test_current_source_behind_open_switch(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source"), comp("S1", "switch", closed=False)]
            + [comp("R1", "resistor"), comp("GND1", "ground")],
            ("I1.positive", "S1.a"),
            ("S1.b", "R1.a"),
            ("R1.b", "I1.negative"),
            ("GND1.gnd", "I1.negative"),
        )

        report = run(data)

        assert codes(report.errors) == [Code.CURRENT_SOURCE_CUTSET]


class TestValues:
    @pytest.mark.parametrize(
        ("ctype", "prop", "value"),
        [
            ("resistor", "resistanceOhm", 0),
            ("resistor", "resistanceOhm", -10),
            ("dc_voltage_source", "voltageV", 0),
            ("dc_voltage_source", "voltageV", -12),
            ("dc_voltage_source", "voltageV", 120.5),
            ("dc_current_source", "currentA", 11),
            ("lamp", "ratedPowerW", 0),
        ],
    )
    def test_out_of_range_values(self, ctype: str, prop: str, value: float) -> None:
        data = circuit([comp("X1", ctype, **{prop: value}), comp("GND1", "ground")])

        report = run(data)

        assert codes(report.errors)[0] == Code.INVALID_VALUE
        assert report.errors[0].refs == ("X1",)
        assert prop in report.errors[0].message

    def test_value_message_includes_unit_and_limit(self) -> None:
        report = run(source_resistor(resistanceOhm=0))

        assert codes(report.errors) == [Code.INVALID_VALUE]
        assert (
            report.errors[0].message == "A propriedade resistanceOhm de R1 (0 Ω) tem de ser > 0 Ω."
        )

    def test_limits_are_inclusive_where_defined(self) -> None:
        data = source_resistor()
        data["components"][0]["properties"]["voltageV"] = 120

        assert run(data).ok

    def test_nan_is_rejected_by_the_model(self) -> None:
        with pytest.raises(ValidationError):
            CircuitDocument.model_validate(source_resistor(resistanceOhm=float("nan")))

    @pytest.mark.parametrize("value", [float("nan"), float("inf")])
    def test_non_finite_values_are_rejected_by_the_validator(self, value: float) -> None:
        document = CircuitDocument.model_validate(source_resistor())
        bad = Component.model_construct(
            **{**dict(document.components[1]), "properties": {"resistanceOhm": value}}
        )
        document = document.model_copy(
            update={"components": [document.components[0], bad, document.components[2]]}
        )

        report = validate(document)

        assert codes(report.errors) == [Code.INVALID_VALUE]
        assert "finito" in report.errors[0].message

    def test_wrong_property_types(self) -> None:
        data = source_resistor(resistanceOhm=True)
        data["components"].append(comp("S1", "switch", closed=1))

        report = run(data)

        assert codes(report.errors)[:2] == [Code.INVALID_PROPERTY_TYPE] * 2

    def test_unknown_and_missing_properties(self) -> None:
        data = source_resistor(powerW=1)
        del data["components"][1]["properties"]["resistanceOhm"]

        report = run(data)

        assert codes(report.errors) == [Code.UNKNOWN_PROPERTY, Code.MISSING_PROPERTY]

    def test_value_errors_do_not_hide_topology_errors(self) -> None:
        data = source_resistor(resistanceOhm=-1)
        data["wires"].pop()

        assert codes(run(data).errors) == [Code.INVALID_VALUE, Code.FLOATING_NET]


class TestDocumentRules:
    def test_duplicate_ids_across_element_kinds(self) -> None:
        data = source_resistor()
        data["components"].append(comp("R1", "resistor"))
        data["wires"][0]["id"] = "V1"
        data["junctions"] = [{"id": "W2", "position": {"x": 0, "y": 0}}]

        report = run(data)

        assert codes(report.errors) == [Code.DUPLICATE_ID] * 3
        assert [e.refs for e in report.errors] == [("V1",), ("R1",), ("W2",)]
        assert report.normalized is None

    def test_duplicate_declared_net_id(self) -> None:
        data = source_resistor()
        data["nets"] = [
            {"id": "R1", "terminals": ["V1.positive", "R1.a"]},
            {"id": "N2", "terminals": ["V1.negative", "R1.b", "GND1.gnd"]},
        ]

        report = run(data)

        assert codes(report.errors) == [Code.DUPLICATE_ID]
        assert "rede" in report.errors[0].message

    def test_self_loop_wire(self) -> None:
        data = source_resistor()
        data["wires"].append({"id": "W4", "from": "R1.a", "to": "R1.a", "waypoints": []})

        report = run(data)

        assert codes(report.errors) == [Code.SELF_LOOP_WIRE]
        assert report.errors[0].refs == ("W4", "R1.a")

    def test_unknown_component_type(self) -> None:
        data = source_resistor()
        data["components"].append({**comp("R2", "resistor"), "type": "capacitor"})

        report = run(data)

        assert codes(report.errors) == [Code.UNKNOWN_COMPONENT_TYPE]
        assert report.normalized is not None

    def test_unknown_and_missing_pins(self) -> None:
        data = source_resistor()
        data["components"][1]["pins"] = ["a", "c"]

        report = run(data)

        assert codes(report.errors) == [Code.UNKNOWN_PIN, Code.MISSING_PIN, Code.UNKNOWN_TERMINAL]
        assert report.errors[0].refs == ("R1", "R1.c")
        assert report.errors[1].refs == ("R1", "R1.b")

    def test_wire_to_unknown_pin_comes_from_normalizer(self) -> None:
        data = source_resistor()
        data["wires"][0]["to"] = "R1.x"

        report = run(data)

        assert codes(report.errors) == [Code.UNKNOWN_TERMINAL]

    def test_unsupported_model(self) -> None:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        for item in raw["components"]:
            if item["type"] == "lamp":
                item["simulationModel"] = None
        catalog = ComponentCatalog.from_dict(raw)
        data = source_resistor()
        data["components"].append(comp("H1", "lamp"))
        data["wires"] += [
            {"id": "W4", "from": "H1.a", "to": "R1.a", "waypoints": []},
            {"id": "W5", "from": "H1.b", "to": "R1.b", "waypoints": []},
        ]

        report = validate(CircuitDocument.model_validate(data), catalog)

        assert codes(report.errors) == [Code.UNSUPPORTED_MODEL]
        assert report.errors[0].refs == ("H1",)

    def test_does_not_mutate_input(self) -> None:
        document = CircuitDocument.model_validate(source_resistor())

        validate(document)

        assert document.nets is None
