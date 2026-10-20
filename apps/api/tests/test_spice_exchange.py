"""Testes da importação/exportação de netlists SPICE (F2-05)."""

import json
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitValidationError
from app.circuit.normalize import normalize
from app.main import app
from app.models.circuit import CircuitDocument
from app.solver.mna import simulate_dc
from app.solver.semiconductors import THERMAL_VOLTAGE_V
from app.spice.exchange import (
    EMBEDDED_PREFIX,
    InvalidNetlistError,
    NetlistIssueCode,
    export_netlist,
    import_netlist,
    parse_value,
)
from tests.factories import FIXTURES, circuit, comp, load_fixture

CATALOG = load_catalog()
FIXTURE_NAMES = sorted(p.stem for p in FIXTURES.glob("*.json"))
EXPORT = "/api/v1/circuits/export/spice"
IMPORT = "/api/v1/circuits/import/spice"
PROBLEM = "application/problem+json"

client = TestClient(app)


def document(data: dict[str, Any]) -> CircuitDocument:
    return CircuitDocument.model_validate(data)


def without_embedded(netlist: str) -> str:
    return "\n".join(line for line in netlist.splitlines() if not line.startswith("*@"))


def components(result: Any) -> dict[str, Any]:
    return {c.id: c for c in result.circuit.components}


def codes(issues: list[Any]) -> list[str]:
    return [str(i.code) for i in issues]


class TestParseValue:
    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("10", 10.0),
            ("-2.5", -2.5),
            ("1e3", 1000.0),
            ("4.7k", 4700.0),
            ("2.2u", 2.2e-6),
            ("100nF", 1e-7),
            ("1meg", 1e6),
            ("1MEG", 1e6),
            ("3m", 3e-3),
            ("10pF", 1e-11),
            ("5f", 5e-15),
            ("2g", 2e9),
            ("1t", 1e12),
            ("1mil", 25.4e-6),
            ("12V", 12.0),
            (".5", 0.5),
        ],
    )
    def test_suffixes(self, token: str, expected: float) -> None:
        assert parse_value(token) == pytest.approx(expected)

    @pytest.mark.parametrize("token", ["abc", "k10", "", "1e999", "1..2"])
    def test_invalid(self, token: str) -> None:
        assert parse_value(token) is None


class TestExport:
    def test_transistor_led_netlist(self) -> None:
        netlist = export_netlist(document(load_fixture("transistor-led")), CATALOG)
        lines = netlist.splitlines()

        assert lines[0] == "* Transístor NPN a comandar um LED"
        assert "V1 N1 0 DC 9.0" in lines
        assert "VS1 N1 N3 DC 0" in lines  # interruptor fechado = fonte de 0 V
        assert "RB N3 N4 10000.0" in lines
        assert "Q1 N5 N4 0 QM_Q1" in lines
        assert "D1 N6 N5 LED_D1" in lines
        assert ".model QM_Q1 NPN(IS=1e-14 BF=100.0 BR=1.0)" in lines
        assert lines[-3:-1] == [".op", ".end"]
        assert lines[-1].startswith(EMBEDDED_PREFIX)
        assert netlist.endswith("\n")

    def test_diode_model_reproduces_forward_point_with_n2(self) -> None:
        data = circuit(
            [
                comp("V1", "dc_voltage_source"),
                comp("R1", "resistor"),
                comp("D1", "diode"),
                comp("GND1", "ground"),
            ],
            ("V1.positive", "R1.a"),
            ("R1.b", "D1.anode"),
            ("D1.cathode", "V1.negative"),
            ("V1.negative", "GND1.gnd"),
        )
        netlist = export_netlist(document(data), CATALOG)
        model = next(line for line in netlist.splitlines() if line.startswith(".model"))
        saturation = float(model.split("IS=")[1].split()[0])

        assert "N=2.0" in model
        assert saturation * (2.718281828459045 ** (0.7 / (2 * THERMAL_VOLTAGE_V)) - 1) == (
            pytest.approx(0.01, rel=1e-9)
        )

    def test_components_without_spice_element_are_listed_in_a_comment(self) -> None:
        netlist = export_netlist(document(load_fixture("medicoes-rc")), CATALOG)

        assert "* Sem elemento SPICE:" in netlist
        assert "VM1" in netlist.split("* Sem elemento SPICE:")[1].splitlines()[0]

    def test_open_switch_has_no_element_and_current_source_is_reversed(self) -> None:
        data = circuit(
            [
                comp("I1", "dc_current_source", currentA=0.002),
                comp("R1", "resistor"),
                comp("S1", "switch", closed=False),
                comp("R2", "resistor"),
                comp("GND1", "ground"),
            ],
            ("I1.positive", "R1.a"),
            ("R1.b", "I1.negative"),
            ("I1.negative", "GND1.gnd"),
            ("R1.a", "S1.a"),
            ("S1.b", "R2.a"),
            ("R2.b", "GND1.gnd"),
        )
        lines = export_netlist(document(data), CATALOG).splitlines()

        assert not any(line.startswith(("S1", "VS1")) for line in lines)
        current = next(line for line in lines if line.startswith("I1"))
        assert current.split()[1] == "0"  # SPICE: a corrente sai por n- = o nosso positive
        assert current.split()[4] == "0.002"

    def test_names_are_spice_safe_and_unique(self) -> None:
        data = circuit(
            [
                comp("V1", "dc_voltage_source"),
                comp("load-a", "resistor"),
                comp("Rload_a", "resistor"),
                comp("GND1", "ground"),
            ],
            ("V1.positive", "load-a.a"),
            ("load-a.b", "Rload_a.a"),
            ("Rload_a.b", "V1.negative"),
            ("V1.negative", "GND1.gnd"),
        )
        names = [line.split()[0] for line in export_netlist(document(data), CATALOG).splitlines()]

        assert "Rload_a" in names
        assert "Rload_a_2" in names

    def test_invalid_circuit_raises(self) -> None:
        data = circuit([comp("V1", "dc_voltage_source")], ("V1.positive", "V1.negative"))

        with pytest.raises(CircuitValidationError):
            export_netlist(document(data), CATALOG)


class TestRoundTrip:
    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_exported_netlist_restores_the_document(self, name: str) -> None:
        original = document(load_fixture(name))

        result = import_netlist(export_netlist(original, CATALOG), CATALOG)

        assert result.circuit == original
        assert result.warnings == []

    def test_crlf_and_whitespace_changes_keep_the_embedded_document(self) -> None:
        original = document(load_fixture("divisor-tensao"))
        lines = export_netlist(original, CATALOG).splitlines()
        spaced = [line if line.startswith("*") else line.replace(" ", " \t ") for line in lines]
        netlist = "\r\n".join(spaced)

        assert import_netlist(netlist, CATALOG).circuit == original

    def test_edited_netlist_ignores_embedded_document(self) -> None:
        netlist = export_netlist(document(load_fixture("divisor-tensao")), CATALOG)
        resistor = next(line for line in netlist.splitlines() if line.startswith("R"))
        edited = netlist.replace(resistor, resistor.rsplit(" ", 1)[0] + " 1k")

        result = import_netlist(edited, CATALOG)

        assert codes(result.warnings) == [NetlistIssueCode.EMBEDDED_CIRCUIT_IGNORED]
        imported = components(result)[resistor.split()[0]]
        assert imported.properties["resistanceOhm"] == 1000.0

    def test_corrupted_embedded_document_is_ignored(self) -> None:
        netlist = export_netlist(document(load_fixture("divisor-tensao")), CATALOG)
        corrupted = netlist.replace(EMBEDDED_PREFIX + "{", EMBEDDED_PREFIX + "{oops")

        result = import_netlist(corrupted, CATALOG)

        assert codes(result.warnings) == [NetlistIssueCode.EMBEDDED_CIRCUIT_IGNORED]
        assert len(result.circuit.components) == 4

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_inferred_circuit_simulates_like_the_original(self, name: str) -> None:
        original = document(load_fixture(name))
        netlist = without_embedded(export_netlist(original, CATALOG))

        result = import_netlist(netlist, CATALOG)

        assert [i for i in result.circuit_issues if i.code != "UNCONNECTED_PIN"] == []
        expected = simulate_dc(original, CATALOG).components
        actual = simulate_dc(result.circuit, CATALOG).components
        shared = expected.keys() & actual.keys()
        assert shared
        for cid in shared:
            assert actual[cid].current_a == pytest.approx(expected[cid].current_a, abs=1e-9)
            assert actual[cid].voltage_v == pytest.approx(expected[cid].voltage_v, abs=1e-6)


HAND_WRITTEN = """Divisor com LED e transístor
* comentário
V1 in 0 DC 12 ; fonte principal
Vneg 0 neg -5
R1 in mid 4.7k
R2 mid 0 10K $ resistência de baixo
C1 mid 0 100n IC=1.5
L1 in
+ coil 1mH
Rcoil coil 0 1meg
Ib 0 base 10u
Rb base 0 100k
D1 neg out redled
Rout out 0 220
Q1 col base 0 0 qmod
Rc in col 1k
Vam col col2 0
Rc2 col2 0 1meg
.model redled D(IS=1e-20 N=2 RS=5)
.model qmod NPN(BF=150 IS=2e-15 VAF=100)
.tran 1u 1m
.control
run
.endc
.op
.end
"""


class TestInference:
    def test_hand_written_netlist(self) -> None:
        result = import_netlist(HAND_WRITTEN, CATALOG)
        parts = components(result)

        assert result.circuit.name == "Divisor com LED e transístor"
        assert parts["V1"].type == "dc_voltage_source"
        assert parts["V1"].properties == {"voltageV": 12.0}
        assert parts["Vneg"].properties == {"voltageV": 5.0}
        assert parts["R1"].properties == {"resistanceOhm": 4700.0}
        assert parts["R2"].properties == {"resistanceOhm": 10000.0}
        assert parts["C1"].properties == {"capacitanceF": 1e-7, "initialVoltageV": 1.5}
        assert parts["L1"].properties == {"inductanceH": 1e-3, "initialCurrentA": 0.0}
        assert parts["Vam"].type == "ammeter"
        assert parts["Ib"].type == "dc_current_source"
        assert parts["Ib"].properties == {"currentA": 1e-5}
        assert parts["D1"].type == "led"
        assert parts["D1"].properties["forwardCurrentA"] == 0.02
        expected_vf = 2 * THERMAL_VOLTAGE_V * math.log1p(0.02 / 1e-20)
        assert parts["D1"].properties["forwardVoltageV"] == pytest.approx(expected_vf, abs=1e-6)
        assert parts["Q1"].type == "npn_transistor"
        assert parts["Q1"].properties == {"currentGain": 150.0, "saturationCurrentA": 2e-15}
        assert "GND1" in parts
        assert [c for c in result.circuit_issues if c.code != "UNCONNECTED_PIN"] == []
        warnings = codes(result.warnings)
        assert NetlistIssueCode.IGNORED_DIRECTIVE in warnings  # .tran e .control
        assert warnings.count(NetlistIssueCode.IGNORED_PARAMETER) == 2  # RS e VAF

    def test_pins_follow_spice_conventions(self) -> None:
        result = import_netlist(HAND_WRITTEN, CATALOG)
        normalized = normalize(result.circuit).document
        nets = {t: net.id for net in normalized.nets or [] for t in net.terminals}
        ground = nets["GND1.gnd"]

        assert nets["Vneg.positive"] != ground  # -5 V: os pinos trocam
        assert nets["Vneg.negative"] == ground
        assert nets["Ib.positive"] != ground  # I 0 base: a corrente entra em base
        assert nets["Ib.negative"] == ground
        assert nets["Q1.emitter"] == ground  # o 4.º nó (substrato) é ignorado
        assert nets["D1.anode"] == nets["Vneg.positive"]

    def test_imported_circuit_simulates(self) -> None:
        text = "Divisor\nV1 1 0 10\nR1 1 2 1k\nR2 2 0 1k\n.end\n"

        result = simulate_dc(import_netlist(text, CATALOG).circuit, CATALOG)

        assert result.components["R2"].voltage_v == pytest.approx(5.0)
        assert result.components["R1"].current_a == pytest.approx(5e-3)

    def test_layout_has_grid_positions_and_one_wire_chain_per_node(self) -> None:
        text = "T\nV1 a 0 1\nR1 a b 1\nR2 b 0 1\nR3 b 0 1\nR4 b 0 1\n"

        result = import_netlist(text, CATALOG)
        positions = {(c.position.x, c.position.y) for c in result.circuit.components}

        assert len(positions) == len(result.circuit.components)  # sem sobreposições
        # nós a (2 terminais), b (4), 0 (4 + terra): 1 + 3 + 4 fios
        assert len(result.circuit.wires) == 8
        assert result.circuit.nets is None
        assert result.circuit.id == "netlist-spice"

    def test_ids_are_sanitized_and_unique(self) -> None:
        text = "T\nV1 a 0 1\nR.x a 0 1\nr.x a 0 1\nR.x a 0 2\n"

        ids = [c.id for c in import_netlist(text, CATALOG).circuit.components]

        assert ids == ["V1", "R_x", "r_x", "R_x_2", "GND1"]

    def test_zero_current_source_is_skipped(self) -> None:
        result = import_netlist("T\nV1 a 0 1\nR1 a 0 1\nI1 a 0 0\n", CATALOG)

        assert "I1" not in components(result)
        assert NetlistIssueCode.IGNORED_PARAMETER in codes(result.warnings)

    def test_diode_with_default_model_and_approximation_warning(self) -> None:
        result = import_netlist("T\nV1 a 0 1\nR1 a b 1k\nD1 b 0 dmod\n.model dmod D\n", CATALOG)
        diode = components(result)["D1"]

        assert diode.type == "diode"
        assert diode.properties["forwardCurrentA"] == 0.01
        assert diode.properties["forwardVoltageV"] == pytest.approx(
            THERMAL_VOLTAGE_V * math.log1p(0.01 / 1e-14), abs=1e-6
        )
        assert codes(result.warnings) == [NetlistIssueCode.APPROXIMATE_MODEL]

    def test_empty_title_gets_a_default_name(self) -> None:
        result = import_netlist("\nV1 a 0 1\nR1 a 0 1\n", CATALOG)

        assert result.circuit.name == "Netlist SPICE importada"


class TestErrors:
    @pytest.mark.parametrize(
        ("body", "code", "line"),
        [
            ("X1 a b sub", NetlistIssueCode.UNSUPPORTED_ELEMENT, 3),
            ("E1 a 0 b 0 2", NetlistIssueCode.UNSUPPORTED_ELEMENT, 3),
            (".include modelos.lib", NetlistIssueCode.UNSUPPORTED_DIRECTIVE, 3),
            (".subckt amp a b", NetlistIssueCode.UNSUPPORTED_DIRECTIVE, 3),
            (".param r=1k", NetlistIssueCode.UNSUPPORTED_DIRECTIVE, 3),
            ("V2 a 0 PULSE(0 5 0 1n 1n 1u 2u)", NetlistIssueCode.UNSUPPORTED_SOURCE, 3),
            ("V2 a 0 SIN(0 1 50)", NetlistIssueCode.UNSUPPORTED_SOURCE, 3),
            ("D1 a 0 nomodel", NetlistIssueCode.UNKNOWN_MODEL, 3),
            ("R2 a 0 abc", NetlistIssueCode.INVALID_VALUE, 3),
            ("R2 a 0", NetlistIssueCode.INVALID_NETLIST, 3),
        ],
    )
    def test_unsupported_input_reports_line(
        self, body: str, code: NetlistIssueCode, line: int
    ) -> None:
        with pytest.raises(InvalidNetlistError) as info:
            import_netlist(f"Título\nV1 a 0 5\n{body}\nR1 a 0 1k\n", CATALOG)

        issue = info.value.issues[0]
        assert issue.code == code
        assert issue.line == line
        assert issue.text().startswith(f"Linha {line}: ")

    def test_all_errors_are_reported(self) -> None:
        with pytest.raises(InvalidNetlistError) as info:
            import_netlist("T\nX1 a b s\nM1 d g s b nmos\n.lib x\n", CATALOG)

        assert [i.line for i in info.value.issues] == [2, 3, 4]

    def test_empty_netlist(self) -> None:
        with pytest.raises(InvalidNetlistError) as info:
            import_netlist("Só título\n* nada\n.op\n.end\n", CATALOG)

        assert info.value.issues[0].code == NetlistIssueCode.INVALID_NETLIST

    def test_lines_after_end_are_ignored(self) -> None:
        result = import_netlist("T\nV1 a 0 1\nR1 a 0 1\n.end\nX1 a b c\n", CATALOG)

        assert set(components(result)) == {"V1", "R1", "GND1"}


class TestEndpoints:
    def test_export(self) -> None:
        response = client.post(EXPORT, json=load_fixture("divisor-tensao"))

        assert response.status_code == 200
        netlist = response.json()["netlist"]
        assert ".op\n.end\n" in netlist

    def test_export_invalid_circuit(self) -> None:
        data = circuit([comp("V1", "dc_voltage_source")], ("V1.positive", "V1.negative"))

        response = client.post(EXPORT, json=data)

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM

    def test_import_round_trip(self) -> None:
        data = load_fixture("transistor-led")
        netlist = client.post(EXPORT, json=data).json()["netlist"]

        response = client.post(IMPORT, json={"netlist": netlist})

        assert response.status_code == 200
        body = response.json()
        assert body["circuit"] == json.loads(
            document(data).model_dump_json(by_alias=True, exclude_none=True)
        )
        assert body["warnings"] == []
        assert body["issues"] == []

    def test_import_returns_warnings_and_issues(self) -> None:
        response = client.post(IMPORT, json={"netlist": "T\nV1 a 0 1\nR1 a b 1\n.tran 1u 1m\n"})

        assert response.status_code == 200
        body = response.json()
        assert [w["code"] for w in body["warnings"]] == ["IGNORED_DIRECTIVE"]
        assert body["warnings"][0]["message"].startswith("Linha 4: ")
        assert [i["code"] for i in body["issues"]] == ["UNCONNECTED_PIN"]

    def test_import_invalid_netlist_problem(self) -> None:
        response = client.post(IMPORT, json={"netlist": "T\nX1 a b sub\n"})

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM
        body = response.json()
        assert body["type"] == "urn:vcccircuitlab:problem:invalid-netlist"
        assert body["title"] == "Netlist SPICE inválida"
        assert body["code"] == "INVALID_NETLIST"
        assert body["errors"][0]["code"] == "UNSUPPORTED_ELEMENT"
        assert body["errors"][0]["message"].startswith("Linha 2: ")

    @pytest.mark.parametrize(
        "payload",
        [{"netlist": ""}, {"netlist": "T\nV1 a 0 1\n", "extra": 1}, {}, {"netlist": 3}],
    )
    def test_import_rejects_bad_body(self, payload: dict[str, Any]) -> None:
        response = client.post(IMPORT, json=payload)

        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_DOCUMENT"
