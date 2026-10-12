import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import UnionFind, build_nets, normalize
from app.models.circuit import CircuitDocument

FIXTURES = Path(__file__).resolve().parents[3] / "packages/circuit-schema/test/fixtures/valid"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def doc(data: dict[str, Any]) -> CircuitDocument:
    return CircuitDocument.model_validate(data)


def component(cid: str, pins: list[str], ctype: str = "resistor") -> dict[str, Any]:
    return {
        "id": cid,
        "type": ctype,
        "position": {"x": 0, "y": 0},
        "rotation": 0,
        "properties": {},
        "pins": pins,
    }


def wire(wid: str, a: str, b: str) -> dict[str, Any]:
    return {"id": wid, "from": a, "to": b, "waypoints": []}


def circuit(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schemaVersion": "1.0",
        "id": "teste",
        "name": "Teste",
        "units": "SI",
        "components": [component("R1", ["a", "b"]), component("R2", ["a", "b"])],
        "wires": [],
    }
    base.update(overrides)
    return base


def error_codes(exc: pytest.ExceptionInfo[CircuitValidationError]) -> list[CircuitErrorCode]:
    return [e.code for e in exc.value.errors]


class TestUnionFind:
    def test_union_and_find(self) -> None:
        uf = UnionFind(range(6))
        uf.union(0, 1)
        uf.union(2, 3)
        uf.union(1, 3)

        assert uf.find(0) == uf.find(3)
        assert uf.find(4) != uf.find(0)
        assert uf.find(5) == 5

    def test_long_chain(self) -> None:
        n = 10_000
        uf = UnionFind(range(n))
        for i in range(n - 1):
            uf.union(i, i + 1)

        assert len({uf.find(i) for i in range(n)}) == 1


class TestFixtures:
    def test_source_resistor_keeps_declared_net_ids(self) -> None:
        data = load_fixture("fonte-resistencia")

        result = normalize(doc(data))

        assert result.document.to_json_dict()["nets"] == [
            {"id": "N_PLUS", "terminals": ["V1.positive", "R1.a"]},
            {"id": "N_GND", "terminals": ["V1.negative", "R1.b", "GND1.gnd"]},
        ]
        assert result.terminal_to_net["GND1.gnd"] == "N_GND"

    def test_source_resistor_without_nets_generates_ids(self) -> None:
        data = load_fixture("fonte-resistencia")
        del data["nets"]

        result = normalize(doc(data))

        assert [(n.id, n.terminals) for n in result.document.nets or []] == [
            ("N1", ["V1.positive", "R1.a"]),
            ("N2", ["V1.negative", "R1.b", "GND1.gnd"]),
        ]

    def test_parallel_with_junctions(self) -> None:
        data = load_fixture("paralelo-juncao")
        data.pop("nets", None)

        partition = build_nets(doc(data))

        assert partition == [
            ["V1.positive", "S1.a"],
            ["V1.negative", "R1.b", "R2.b", "GND1.gnd"],
            ["S1.b", "R1.a", "R2.a"],
        ]

    def test_parallel_fixture_is_consistent(self) -> None:
        normalize(doc(load_fixture("paralelo-juncao")))

    def test_output_round_trips_through_model(self) -> None:
        result = normalize(doc(load_fixture("paralelo-juncao")))

        dumped = result.document.to_json_dict()

        assert doc(dumped) == result.document
        assert all("from" in w and "from_" not in w for w in dumped["wires"])


class TestNormalize:
    def test_unconnected_terminals_are_singleton_nets(self) -> None:
        result = normalize(doc(circuit(wires=[wire("W1", "R1.b", "R2.a")])))

        assert [n.terminals for n in result.document.nets or []] == [
            ["R1.a"],
            ["R1.b", "R2.a"],
            ["R2.b"],
        ]

    def test_crossing_wires_without_junction_are_not_connected(self) -> None:
        data = circuit(
            wires=[wire("W1", "R1.a", "R2.b"), wire("W2", "R1.b", "R2.a")],
        )

        partition = build_nets(doc(data))

        assert partition == [["R1.a", "R2.b"], ["R1.b", "R2.a"]]

    def test_junction_without_terminals_does_not_create_net(self) -> None:
        data = circuit(
            junctions=[{"id": "J1", "position": {"x": 0, "y": 0}}],
        )

        assert build_nets(doc(data)) == [["R1.a"], ["R1.b"], ["R2.a"], ["R2.b"]]

    def test_chained_junctions_bridge_terminals(self) -> None:
        data = circuit(
            junctions=[
                {"id": "J1", "position": {"x": 0, "y": 0}},
                {"id": "J2", "position": {"x": 20, "y": 0}},
            ],
            wires=[wire("W1", "R1.a", "J1"), wire("W2", "J1", "J2"), wire("W3", "J2", "R2.b")],
        )

        assert build_nets(doc(data))[0] == ["R1.a", "R2.b"]

    def test_self_loop_wire_is_harmless(self) -> None:
        assert build_nets(doc(circuit(wires=[wire("W1", "R1.a", "R1.a")])))[0] == ["R1.a"]

    def test_generated_ids_skip_existing_element_ids(self) -> None:
        data = circuit(components=[component("N1", ["a"]), component("N3", ["a"])])

        result = normalize(doc(data))

        assert [n.id for n in result.document.nets or []] == ["N2", "N4"]

    def test_is_deterministic_regardless_of_wire_order(self) -> None:
        wires = [wire("W1", "R1.b", "R2.a"), wire("W2", "R2.a", "R1.a")]
        a = normalize(doc(circuit(wires=wires)))
        b = normalize(doc(circuit(wires=list(reversed(wires)))))

        assert a.document.nets == b.document.nets

    def test_does_not_mutate_input(self) -> None:
        document = doc(circuit(wires=[wire("W1", "R1.b", "R2.a")]))

        normalize(document)

        assert document.nets is None


class TestNormalizeErrors:
    def test_unknown_terminal(self) -> None:
        data = circuit(wires=[wire("W1", "R1.a", "R9.a"), wire("W2", "R1.c", "R2.a")])

        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(data))

        assert error_codes(exc) == [CircuitErrorCode.UNKNOWN_TERMINAL] * 2
        assert exc.value.errors[0].refs == ("W1", "R9.a")

    def test_unknown_junction(self) -> None:
        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(circuit(wires=[wire("W1", "R1.a", "J9")])))

        assert error_codes(exc) == [CircuitErrorCode.UNKNOWN_JUNCTION]

    def test_wire_to_component_id_is_unknown_junction(self) -> None:
        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(circuit(wires=[wire("W1", "R1.a", "R2")])))

        assert error_codes(exc) == [CircuitErrorCode.UNKNOWN_JUNCTION]

    def test_declared_net_with_wrong_partition(self) -> None:
        data = load_fixture("fonte-resistencia")
        data["nets"] = [
            {"id": "N_PLUS", "terminals": ["V1.positive", "R1.a", "R1.b"]},
            {"id": "N_GND", "terminals": ["V1.negative", "GND1.gnd"]},
        ]

        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(data))

        assert set(error_codes(exc)) == {CircuitErrorCode.NET_INCONSISTENT}

    def test_declared_nets_missing_a_net(self) -> None:
        data = load_fixture("fonte-resistencia")
        data["nets"] = data["nets"][:1]

        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(data))

        assert error_codes(exc) == [CircuitErrorCode.NET_INCONSISTENT]
        assert exc.value.errors[0].refs == ("V1.negative", "R1.b", "GND1.gnd")

    def test_terminal_in_two_declared_nets(self) -> None:
        data = load_fixture("fonte-resistencia")
        data["nets"][1]["terminals"].append("R1.a")

        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(data))

        assert error_codes(exc) == [CircuitErrorCode.NET_INCONSISTENT]

    def test_declared_net_with_unknown_terminal(self) -> None:
        data = load_fixture("fonte-resistencia")
        data["nets"][0]["terminals"].append("X1.a")

        with pytest.raises(CircuitValidationError) as exc:
            normalize(doc(data))

        assert error_codes(exc) == [CircuitErrorCode.UNKNOWN_TERMINAL]

    def test_declared_net_order_is_irrelevant(self) -> None:
        data = load_fixture("fonte-resistencia")
        data["nets"] = [
            {"id": "B", "terminals": ["GND1.gnd", "R1.b", "V1.negative"]},
            {"id": "A", "terminals": ["R1.a", "V1.positive"]},
        ]

        result = normalize(doc(data))

        assert result.terminal_to_net == {
            "V1.positive": "A",
            "R1.a": "A",
            "V1.negative": "B",
            "R1.b": "B",
            "GND1.gnd": "B",
        }


class TestModels:
    def test_valid_fixtures_parse_from_json(self) -> None:
        for path in FIXTURES.glob("*.json"):
            CircuitDocument.model_validate_json(path.read_text(encoding="utf-8"))

    @pytest.mark.parametrize(
        ("path", "value"),
        [
            (("schemaVersion",), "2.0"),
            (("units",), "imperial"),
            (("id",), "-mau"),
            (("name",), ""),
            (("components", 0, "id"), "R.1"),
            (("components", 0, "id"), "1R"),
            (("components", 0, "type"), "Resistor"),
            (("components", 0, "rotation"), 45),
            (("components", 0, "rotation"), "90"),
            (("components", 0, "pins"), []),
            (("components", 0, "pins"), ["a", "a"]),
            (("components", 0, "properties"), {"ResistanceOhm": 1}),
            (("components", 0, "properties"), {"resistanceOhm": "100"}),
            (("components", 0, "properties"), {"resistanceOhm": None}),
            (("components", 0, "position", "x"), True),
            (("components", 0, "position", "x"), float("inf")),
            (("components", 0, "position", "x"), float("nan")),
            (("components", 0, "label"), "x" * 65),
            (("wires",), [{"id": "W1", "from": "R1.a", "to": "R1.b"}]),
            (("wires",), [{"id": "W1", "from": "R1.a.b", "to": "R1.b", "waypoints": []}]),
            (("nets",), [{"id": "N1", "terminals": []}]),
            (("nets",), [{"id": "N1", "terminals": ["R1"]}]),
        ],
    )
    def test_rejects_invalid_values(self, path: tuple[Any, ...], value: Any) -> None:
        data = circuit()
        target = data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

        with pytest.raises(ValidationError):
            doc(data)

    @pytest.mark.parametrize("where", ["root", "component", "position", "wire"])
    def test_rejects_extra_fields(self, where: str) -> None:
        data = circuit(wires=[wire("W1", "R1.a", "R2.a")])
        target = {
            "root": data,
            "component": data["components"][0],
            "position": data["components"][0]["position"],
            "wire": data["wires"][0],
        }[where]
        target["extra"] = 1

        with pytest.raises(ValidationError):
            doc(data)

    def test_accepts_integer_and_boolean_properties(self) -> None:
        data = circuit()
        data["components"][0]["properties"] = {"resistanceOhm": 100, "closed": True}

        props = doc(data).components[0].properties

        assert props == {"resistanceOhm": 100.0, "closed": True}
        assert props["closed"] is True

    def test_wire_accepts_python_name_and_alias(self) -> None:
        data = circuit(wires=[{"id": "W1", "from_": "R1.a", "to": "R2.a", "waypoints": []}])

        assert doc(data).wires[0].from_ == "R1.a"

    def test_models_are_immutable(self) -> None:
        document = doc(copy.deepcopy(circuit()))

        with pytest.raises(ValidationError):
            document.name = "outro"  # type: ignore[misc]
