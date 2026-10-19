import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.circuit.catalog import ComponentCatalog, load_catalog_documents
from app.main import app
from app.routes import circuits
from tests.factories import AnalyticCase, comp, load_analytic_cases, load_fixture, source_resistor

VALIDATE = "/api/v1/circuits/validate"
SIMULATE = "/api/v1/circuits/simulate"
PROBLEM = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"
TOLERANCE = 1e-9

CASES = load_analytic_cases()
SUCCESS = [c for c in CASES if not c.is_error]
ERRORS = [c for c in CASES if c.is_error]

client = TestClient(app)


def by_name(cases: list[AnalyticCase]) -> dict[str, Any]:
    return {"argvalues": cases, "ids": [c.name for c in cases]}


def post_raw(path: str, body: str, content_type: str = "application/json") -> Any:
    return client.post(path, content=body, headers={"content-type": content_type})


def assert_problem(response: Any, status: int, kind: str, code: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    expected_type = kind if kind == "about:blank" else TYPE_PREFIX + kind
    assert body["type"] == expected_type
    assert body["status"] == status
    assert body["code"] == code
    assert body["title"]
    return body


class TestValidate:
    def test_valid_circuit_returns_report_with_nets(self) -> None:
        response = client.post(VALIDATE, json=load_fixture("fonte-resistencia"))

        assert response.status_code == 200
        assert response.json() == {
            "valid": True,
            "errors": [],
            "warnings": [],
            "nets": [
                {"id": "N_PLUS", "terminals": ["V1.positive", "R1.a"]},
                {"id": "N_GND", "terminals": ["V1.negative", "R1.b", "GND1.gnd"]},
            ],
        }

    @pytest.mark.parametrize("case", **by_name(SUCCESS))
    def test_simulable_cases_are_valid(self, case: AnalyticCase) -> None:
        body = client.post(VALIDATE, json=case.circuit).json()

        assert body["valid"] is True
        assert [w["code"] for w in body["warnings"]] == case.expected["warnings"]
        assert {n["id"] for n in body["nets"]} == set(case.expected["nodeVoltagesV"])

    @pytest.mark.parametrize("case", **by_name(ERRORS))
    def test_invalid_circuits_are_reported_not_rejected(self, case: AnalyticCase) -> None:
        response = client.post(VALIDATE, json=case.circuit)

        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert [e["code"] for e in body["errors"]] == case.expected["errors"]
        assert all(e["message"] and isinstance(e["refs"], list) for e in body["errors"])

    def test_nets_are_null_when_normalization_fails(self) -> None:
        body = client.post(VALIDATE, json=_case("erro-ids-duplicados").circuit).json()

        assert body["nets"] is None

    def test_schema_errors_are_problems(self) -> None:
        data = source_resistor()
        del data["units"]

        body = assert_problem(
            client.post(VALIDATE, json=data), 422, "invalid-document", "INVALID_DOCUMENT"
        )

        assert body["errors"][0]["pointer"] == "/units"


class TestSimulate:
    @pytest.mark.parametrize("case", **by_name(SUCCESS))
    def test_analytic_results(self, case: AnalyticCase) -> None:
        response = client.post(SIMULATE, json=case.circuit)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        body = response.json()
        expected = case.expected
        assert body["analysis"] == "dc_operating_point"
        assert body["status"] == "success"
        assert body["nodeVoltagesV"] == pytest.approx(expected["nodeVoltagesV"], abs=TOLERANCE)
        assert list(body["components"]) == list(expected["components"])
        for cid, values in expected["components"].items():
            assert body["components"][cid] == pytest.approx(values, abs=TOLERANCE), cid
        assert [w["code"] for w in body["warnings"]] == expected["warnings"]

    def test_acceptance_12v_100ohm(self) -> None:
        body = client.post(SIMULATE, json=load_fixture("fonte-resistencia")).json()

        assert body["components"]["R1"] == pytest.approx(
            {"voltageV": 12, "currentA": 0.12, "powerW": 1.44}
        )

    def test_branched_prototype(self) -> None:
        """E1-08: três ramos, ponte R4 e cruzamento sem junção (W8 × W11 em (540, 240))."""
        circuit = load_fixture("ramificado")
        nets = client.post(VALIDATE, json=circuit).json()["nets"]
        body = client.post(SIMULATE, json=circuit).json()

        assert sorted(sorted(n["terminals"]) for n in nets) == [
            ["GND1.gnd", "H1.b", "R1.b", "R3.b", "R4.b", "V1.negative"],
            ["H1.a", "R2.b", "R4.a"],
            ["R1.a", "R2.a", "R3.a", "S1.b"],
            ["S1.a", "V1.positive"],
        ]
        # H1 ‖ R4 (lâmpada: R = 12² / 5 = 28,8 Ω) em série com R2; R1 e R3 diretamente nos 9 V.
        lamp_r4 = 1 / (1 / 28.8 + 1 / 220)
        i_r2 = 9 / (47 + lamp_r4)
        components = body["components"]
        assert components["R2"]["currentA"] == pytest.approx(i_r2)
        assert components["H1"]["voltageV"] == pytest.approx(i_r2 * lamp_r4)
        assert components["R1"]["currentA"] == pytest.approx(9 / 150)
        assert components["R3"]["currentA"] == pytest.approx(9 / 330)
        assert components["R2"]["currentA"] == pytest.approx(
            components["H1"]["currentA"] + components["R4"]["currentA"]
        )
        assert components["S1"]["currentA"] == pytest.approx(9 / 150 + i_r2 + 9 / 330)

    @pytest.mark.parametrize("case", **by_name(ERRORS))
    def test_invalid_circuits_are_problems(self, case: AnalyticCase) -> None:
        codes = case.expected["errors"]

        response = client.post(SIMULATE, json=case.circuit)

        body = assert_problem(response, 422, "invalid-circuit", codes[0])
        assert [e["code"] for e in body["errors"]] == codes
        assert body["instance"] == SIMULATE
        assert body["detail"] == body["errors"][0]["message"]

    def test_unsupported_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        documents = [dict(item) for item in load_catalog_documents()]
        for item in documents:
            if item["type"] == "lamp":
                item["simulationModel"] = None
        monkeypatch.setattr(
            circuits,
            "load_catalog",
            lambda: ComponentCatalog.from_dict({"catalogVersion": "1.0", "components": documents}),
        )
        data = source_resistor()
        data["components"].append(comp("H1", "lamp"))
        data["wires"] += [
            {"id": "W4", "from": "H1.a", "to": "R1.a", "waypoints": []},
            {"id": "W5", "from": "H1.b", "to": "R1.b", "waypoints": []},
        ]

        body = assert_problem(
            client.post(SIMULATE, json=data), 422, "invalid-circuit", "UNSUPPORTED_MODEL"
        )

        assert body["errors"][0]["refs"] == ["H1"]

    def test_ill_conditioned_matrix_is_simulation_failure(self) -> None:
        data = source_resistor(resistanceOhm=1e-13)
        data["components"].append(comp("R2", "resistor", resistanceOhm=1e9))
        data["wires"][1]["from"] = "R2.b"
        data["wires"].append({"id": "W4", "from": "R1.b", "to": "R2.a", "waypoints": []})

        assert_problem(
            client.post(SIMULATE, json=data), 422, "simulation-failed", "ILL_CONDITIONED_MATRIX"
        )

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def slow(*args: Any, **kwargs: Any) -> None:
            time.sleep(0.5)

        monkeypatch.setattr(circuits, "simulate", slow)
        monkeypatch.setattr(circuits, "SIMULATION_TIMEOUT_S", 0.05)

        started = time.perf_counter()
        response = client.post(SIMULATE, json=source_resistor())
        elapsed = time.perf_counter() - started

        body = assert_problem(response, 503, "simulation-timeout", "SIMULATION_TIMEOUT")
        assert "0.05 s" in body["detail"]
        assert elapsed < 0.4


class TestSchemaErrors:
    def test_component_errors_have_pointer_and_refs(self) -> None:
        data = source_resistor()
        del data["components"][0]["rotation"]
        data["components"][1]["properties"]["resistanceOhm"] = "100"
        data["extraField"] = 1

        body = assert_problem(
            client.post(SIMULATE, json=data), 422, "invalid-document", "INVALID_COMPONENT"
        )

        assert [(e["code"], e["pointer"], e["refs"]) for e in body["errors"]] == [
            ("INVALID_COMPONENT", "/components/0/rotation", ["V1"]),
            ("INVALID_COMPONENT", "/components/1/properties/resistanceOhm", ["R1"]),
            ("INVALID_DOCUMENT", "/extraField", []),
        ]
        messages = [e["message"] for e in body["errors"]]
        assert messages == [
            "/components/0/rotation: campo obrigatório em falta.",
            "/components/1/properties/resistanceOhm: tipo inválido (esperado booleano ou número).",
            "/extraField: campo não permitido.",
        ]
        assert body["detail"].endswith("(+2 erro(s))")

    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_numbers_are_rejected(self, literal: str) -> None:
        body_json = json.dumps(source_resistor()).replace(
            '"resistanceOhm": 100', f'"resistanceOhm": {literal}'
        )

        body = assert_problem(
            post_raw(SIMULATE, body_json), 422, "invalid-document", "INVALID_COMPONENT"
        )

        assert body["errors"][0]["message"].endswith("tem de ser um número finito.")
        assert body["errors"][0]["refs"] == ["R1"]

    def test_wrong_literal(self) -> None:
        data = {**source_resistor(), "schemaVersion": "2.0"}

        body = assert_problem(
            client.post(SIMULATE, json=data), 422, "invalid-document", "INVALID_DOCUMENT"
        )

        assert body["errors"][0]["pointer"] == "/schemaVersion"
        assert "'1.0'" in body["errors"][0]["message"]

    def test_pointer_escapes_special_characters(self) -> None:
        data = {**source_resistor(), "a/b~c": 1}

        body = client.post(SIMULATE, json=data).json()

        assert body["errors"][0]["pointer"] == "/a~1b~0c"

    @pytest.mark.parametrize("payload", ["[]", "12", '"texto"', "null"])
    def test_root_must_be_an_object(self, payload: str) -> None:
        body = assert_problem(
            post_raw(SIMULATE, payload), 422, "invalid-document", "INVALID_DOCUMENT"
        )

        assert body["errors"][0]["pointer"] == ""

    @pytest.mark.parametrize("payload", ['{"a":', "{'a': 1}", "{,}"])
    def test_malformed_json(self, payload: str) -> None:
        assert_problem(post_raw(SIMULATE, payload), 400, "malformed-json", "MALFORMED_JSON")

    def test_non_json_content_type(self) -> None:
        response = post_raw(SIMULATE, json.dumps(source_resistor()), "text/plain")

        assert_problem(response, 415, "about:blank", "UNSUPPORTED_MEDIA_TYPE")

    def test_json_suffix_content_type_is_accepted(self) -> None:
        response = post_raw(SIMULATE, json.dumps(source_resistor()), "application/merge+json")

        assert response.status_code == 200


class TestHttpErrors:
    def test_unknown_route(self) -> None:
        body = assert_problem(client.get("/api/v1/nao-existe"), 404, "about:blank", "NOT_FOUND")

        assert body["title"] == "Not Found"
        assert body["instance"] == "/api/v1/nao-existe"

    def test_wrong_method(self) -> None:
        response = client.get(SIMULATE)

        assert_problem(response, 405, "about:blank", "METHOD_NOT_ALLOWED")
        assert response.headers["allow"] == "POST"

    def test_internal_error_hides_details(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("segredo interno")

        monkeypatch.setattr(circuits, "simulate", boom)
        unsafe_client = TestClient(app, raise_server_exceptions=False)

        response = unsafe_client.post(SIMULATE, json=source_resistor())

        assert_problem(response, 500, "internal-error", "INTERNAL_ERROR")
        assert "segredo" not in response.text


class TestOpenApi:
    def test_documents_endpoints_and_problem_responses(self) -> None:
        spec = client.get("/openapi.json").json()

        for path, statuses in (
            (VALIDATE, ["400", "415", "422"]),
            (SIMULATE, ["400", "415", "422", "503"]),
        ):
            responses = spec["paths"][path]["post"]["responses"]
            assert "application/json" in responses["200"]["content"]
            for status in statuses:
                content = responses[status]["content"]
                assert list(content) == [PROBLEM]
                assert content[PROBLEM]["schema"] == {"$ref": "#/components/schemas/Problem"}
        assert "CircuitDocument" in spec["components"]["schemas"]


def _case(name: str) -> AnalyticCase:
    return next(c for c in CASES if c.name == name)
