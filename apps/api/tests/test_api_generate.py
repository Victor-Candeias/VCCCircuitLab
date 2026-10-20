"""Testes do endpoint `POST /api/v1/circuits/generate` (E3-02)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

GENERATE = "/api/v1/circuits/generate"
PROBLEM = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"

client = TestClient(app)

SERIES_PARAMS = {"voltageV": 12, "resistorsOhm": [100, 220]}


def assert_problem(response: Any, status: int, kind: str, code: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    expected_type = kind if kind == "about:blank" else TYPE_PREFIX + kind
    assert body["type"] == expected_type
    assert body["status"] == status
    assert body["code"] == code
    assert body["instance"] == GENERATE
    return body


class TestSeriesDc:
    def test_generates_valid_canonical_document_with_nets(self) -> None:
        response = client.post(
            GENERATE, json={"template": "series_dc", "parameters": SERIES_PARAMS}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        body = response.json()
        assert body["schemaVersion"] == "1.0"
        assert [c["id"] for c in body["components"]] == ["V1", "R1", "R2", "GND1"]
        assert len(body["wires"]) == 4
        assert body["nets"] is not None
        assert len(body["nets"]) == 3

    def test_generated_document_is_simulable(self) -> None:
        document = client.post(
            GENERATE, json={"template": "series_dc", "parameters": SERIES_PARAMS}
        ).json()

        result = client.post("/api/v1/circuits/simulate", json=document).json()

        expected_current = 12 / (100 + 220)
        assert result["components"]["R1"]["currentA"] == pytest.approx(expected_current)
        assert result["components"]["R2"]["currentA"] == pytest.approx(expected_current)


class TestOtherTemplates:
    @pytest.mark.parametrize(
        ("template", "parameters"),
        [
            ("parallel_dc", {"voltageV": 12, "resistorsOhm": [100, 200]}),
            ("voltage_divider", {"voltageV": 12, "resistorsOhm": [100, 220]}),
            ("switch_circuit", {"voltageV": 12, "loadOhm": 100, "closed": True}),
            ("staircase_lighting", {"lampPowerW": 100, "switch1ToL2": True}),
        ],
        ids=["parallel_dc", "voltage_divider", "switch_circuit", "staircase_lighting"],
    )
    def test_generates_valid_document(self, template: str, parameters: dict[str, Any]) -> None:
        response = client.post(GENERATE, json={"template": template, "parameters": parameters})

        assert response.status_code == 200
        body = response.json()
        assert body["nets"] is not None

    def test_switch_circuit_defaults_to_closed(self) -> None:
        response = client.post(
            GENERATE,
            json={"template": "switch_circuit", "parameters": {"voltageV": 12, "loadOhm": 100}},
        )

        components = response.json()["components"]
        assert next(c for c in components if c["id"] == "S1")["properties"]["closed"] is True


class TestErrors:
    def test_unknown_template_is_a_problem(self) -> None:
        response = client.post(GENERATE, json={"template": "nao_existe", "parameters": {}})

        body = assert_problem(response, 422, "unknown-template", "UNKNOWN_TEMPLATE")
        assert "nao_existe" in body["detail"]

    def test_invalid_parameters_are_problems(self) -> None:
        response = client.post(
            GENERATE,
            json={
                "template": "series_dc",
                "parameters": {"voltageV": -1, "resistorsOhm": [100, 0]},
            },
        )

        body = assert_problem(response, 422, "invalid-parameters", "INVALID_PARAMETERS")
        assert [e["pointer"] for e in body["errors"]] == [
            "/parameters/voltageV",
            "/parameters/resistorsOhm/1",
        ]
        assert all(e["message"].endswith("tem de ser > 0.") for e in body["errors"])

    def test_missing_required_parameter_is_a_problem(self) -> None:
        response = client.post(GENERATE, json={"template": "series_dc", "parameters": {}})

        body = assert_problem(response, 422, "invalid-parameters", "INVALID_PARAMETERS")
        assert {e["pointer"] for e in body["errors"]} == {
            "/parameters/voltageV",
            "/parameters/resistorsOhm",
        }

    def test_unknown_parameter_is_a_problem(self) -> None:
        response = client.post(
            GENERATE,
            json={
                "template": "series_dc",
                "parameters": {"voltageV": 12, "resistorsOhm": [100], "extra": 1},
            },
        )

        assert_problem(response, 422, "invalid-parameters", "INVALID_PARAMETERS")

    def test_missing_template_field_is_a_schema_error(self) -> None:
        response = client.post(GENERATE, json={"parameters": {}})

        assert_problem(response, 422, "invalid-document", "INVALID_DOCUMENT")

    def test_unknown_top_level_field_is_a_schema_error(self) -> None:
        response = client.post(
            GENERATE, json={"template": "series_dc", "parameters": {}, "extra": 1}
        )

        assert_problem(response, 422, "invalid-document", "INVALID_DOCUMENT")

    def test_non_json_content_type(self) -> None:
        response = client.post(
            GENERATE,
            content='{"template": "series_dc", "parameters": {}}',
            headers={"content-type": "text/plain"},
        )

        assert_problem(response, 415, "about:blank", "UNSUPPORTED_MEDIA_TYPE")


class TestOpenApi:
    def test_documents_endpoint_and_problem_responses(self) -> None:
        spec = client.get("/openapi.json").json()

        responses = spec["paths"][GENERATE]["post"]["responses"]
        assert "application/json" in responses["200"]["content"]
        for status in ("400", "415", "422"):
            assert list(responses[status]["content"]) == [PROBLEM]
