"""Testes do gerador por linguagem natural (`app.generation.natural`) e do endpoint
`POST /api/v1/circuits/generate/text` (F2-06)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.generation.errors import InvalidParametersError, UninterpretableTextError
from app.generation.natural import MAX_TEXT_CHARS, interpret
from app.main import app

GENERATE_TEXT = "/api/v1/circuits/generate/text"
PROBLEM = "application/problem+json"

client = TestClient(app)


class TestTemplates:
    @pytest.mark.parametrize(
        ("text", "template", "parameters"),
        [
            (
                "circuito em série com fonte de 12 V e resistências de 100, 220 e 330 Ω",
                "series_dc",
                {"voltageV": 12.0, "resistorsOhm": [100.0, 220.0, 330.0]},
            ),
            (
                "Três resistências de 1 kΩ em PARALELO com uma bateria de 5 V",
                "parallel_dc",
                {"voltageV": 5.0, "resistorsOhm": [1000.0, 1000.0, 1000.0]},
            ),
            (
                "divisor de tensão de 9V com 10k e 4,7k",
                "voltage_divider",
                {"voltageV": 9.0, "resistorsOhm": [10000.0, 4700.0]},
            ),
            (
                "interruptor aberto com uma lâmpada de 50 ohm a 24 V",
                "switch_circuit",
                {"voltageV": 24.0, "loadOhm": 50.0, "closed": False},
            ),
            (
                "pilha de 1,5 volts e resistor de 1MΩ em serie",
                "series_dc",
                {"voltageV": 1.5, "resistorsOhm": [1e6]},
            ),
        ],
    )
    def test_recognises_topology_and_values(
        self, text: str, template: str, parameters: dict[str, Any]
    ) -> None:
        result = interpret(text)

        assert result.template == template
        assert result.parameters == parameters

    def test_divider_wins_over_series_keyword(self) -> None:
        assert interpret("divisor com 1k e 2k em série a 5 V").template == "voltage_divider"

    def test_summary_describes_the_circuit(self) -> None:
        result = interpret("divisor de tensão de 9 V com 10 kΩ e 4,7 kΩ")

        assert result.summary == "Divisor de tensão: fonte de 9 V e resistências de 10 kΩ e 4.7 kΩ."
        assert result.assumptions == []


class TestStaircase:
    def test_defaults_are_assumed(self) -> None:
        result = interpret("iluminação de escada")

        assert result.template == "staircase_lighting"
        assert result.parameters == {
            "voltageV": 230.0,
            "frequencyHz": 50.0,
            "lampPowerW": 60.0,
            "breakerRatedA": 10.0,
            "switch1ToL2": False,
            "switch2ToL2": False,
        }
        assert len(result.assumptions) == 5
        assert result.summary.endswith("lâmpada de 60 W (apagada).")

    def test_reads_power_breaker_and_state(self) -> None:
        result = interpret("Comutadores de escada com lâmpada de 100 W acesa e disjuntor de 16 A")

        assert result.parameters["lampPowerW"] == 100.0
        assert result.parameters["breakerRatedA"] == 16.0
        assert result.parameters["switch1ToL2"] is True

    def test_rejects_resistances(self) -> None:
        with pytest.raises(UninterpretableTextError) as exc:
            interpret("escada com uma lâmpada de 10 ohm")

        assert "«10 ohm»" in exc.value.reasons[0]

    def test_values_outside_the_limits_are_invalid_parameters(self) -> None:
        with pytest.raises(InvalidParametersError):
            interpret("escada a 500 V")

    def test_endpoint_returns_a_simulable_circuit(self) -> None:
        response = client.post(GENERATE_TEXT, json={"text": "luz de escada acesa"})

        assert response.status_code == 200
        body = response.json()
        assert body["template"] == "staircase_lighting"
        assert [w["code"] for w in body["warnings"]] == ["MAINS_VOLTAGE"]
        simulated = client.post("/api/v1/circuits/simulate", json=body["circuit"])
        assert simulated.status_code == 200, simulated.json()
        assert simulated.json()["components"]["HR1"]["powerW"] == pytest.approx(60)


class TestValues:
    def test_unitless_list_takes_the_unit_of_its_neighbour(self) -> None:
        result = interpret("série a 5 V com 100, 220, e 330 ohms")

        assert result.parameters["resistorsOhm"] == [100.0, 220.0, 330.0]

    def test_unitless_values_classified_by_context(self) -> None:
        result = interpret("em série: fonte de 5 e resistência de 220")

        assert result.parameters == {"voltageV": 5.0, "resistorsOhm": [220.0]}

    def test_count_with_explicit_values(self) -> None:
        result = interpret("duas resistências de 10k e 4,7k em paralelo com 9 V")

        assert result.parameters["resistorsOhm"] == [10000.0, 4700.0]

    def test_millivolt_prefix(self) -> None:
        assert interpret("série com 500 mV e 1k").parameters["voltageV"] == pytest.approx(0.5)


class TestAssumptions:
    def test_missing_values_get_defaults_and_are_reported(self) -> None:
        result = interpret("divisor de tensão")

        assert result.parameters == {"voltageV": 12.0, "resistorsOhm": [100.0, 100.0]}
        assert result.assumptions == [
            "Tensão da fonte não indicada: assumidos 12 V.",
            "Valores das resistências não indicados: assumidos 100 Ω e 100 Ω.",
        ]

    def test_missing_topology_defaults_to_series(self) -> None:
        result = interpret("12 V e 1k")

        assert result.template == "series_dc"
        assert "Topologia não indicada: assumido um circuito em série." in result.assumptions

    def test_switch_state_defaults_to_closed(self) -> None:
        result = interpret("interruptor com carga de 100 Ω a 12 V")

        assert result.parameters["closed"] is True
        assert "Estado do interruptor não indicado: assumido fechado." in result.assumptions

    def test_alternating_current_is_flagged(self) -> None:
        result = interpret("série com 230 V AC e 1k")

        assert "Os circuitos gerados são de corrente contínua: a fonte é DC." in result.assumptions


class TestRejections:
    @pytest.mark.parametrize(
        ("text", "fragment"),
        [
            ("olá, tudo bem?", "Não foi possível reconhecer um circuito"),
            ("série e paralelo com 12 V e 1k", "série e paralelo ao mesmo tempo"),
            ("série com fonte de 2 A", "corrente (A) não é suportada"),
            ("série com 5 V e 9 V e 1k", "uma fonte de tensão"),
            ("duas resistências de 1k, 2k e 3k", "2 resistência(s) mas 3 valor(es)"),
            ("20 resistências de 1k em série", "entre 1 e 12"),
            ("série com fonte 12 e 100", "«100»"),
            ("interruptor com 100 Ω e 200 Ω", "uma só carga"),
            ("divisor de 9 V com 1k", "pelo menos duas resistências"),
            ("import os; os.system('rm -rf /')", "Não foi possível reconhecer um circuito"),
        ],
    )
    def test_unsupported_text_is_explained(self, text: str, fragment: str) -> None:
        with pytest.raises(UninterpretableTextError) as info:
            interpret(text)

        assert any(fragment in reason for reason in info.value.reasons)

    def test_values_still_go_through_the_template_schema(self) -> None:
        with pytest.raises(InvalidParametersError):
            interpret("série com 0 V e 1k")


class TestEndpoint:
    def test_returns_interpretation_and_validated_circuit(self) -> None:
        response = client.post(GENERATE_TEXT, json={"text": "paralelo de 100 e 200 Ω a 10 V"})

        assert response.status_code == 200
        body = response.json()
        assert body["template"] == "parallel_dc"
        assert body["title"] == "Circuito em paralelo"
        assert body["parameters"] == {"voltageV": 10.0, "resistorsOhm": [100.0, 200.0]}
        assert body["summary"].startswith("Circuito em paralelo:")
        assert body["assumptions"] == []
        assert body["warnings"] == []
        assert body["circuit"]["nets"]

    def test_generated_circuit_is_simulable(self) -> None:
        circuit = client.post(GENERATE_TEXT, json={"text": "série com 12 V, 100 e 220 Ω"}).json()[
            "circuit"
        ]

        result = client.post("/api/v1/circuits/simulate", json=circuit).json()

        assert result["components"]["R1"]["currentA"] == pytest.approx(12 / 320)

    def test_uninterpretable_text_is_a_problem(self) -> None:
        response = client.post(GENERATE_TEXT, json={"text": "uma torradeira"})

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM
        body = response.json()
        assert body["type"] == "urn:vcccircuitlab:problem:uninterpretable-text"
        assert body["code"] == "UNINTERPRETABLE_TEXT"
        assert body["errors"][0]["code"] == "UNINTERPRETABLE_TEXT"

    def test_invalid_values_are_parameter_problems(self) -> None:
        response = client.post(GENERATE_TEXT, json={"text": "série com 0 V e 1k"})

        assert response.status_code == 422
        assert response.json()["type"] == "urn:vcccircuitlab:problem:invalid-parameters"

    @pytest.mark.parametrize(
        "body",
        [{"text": ""}, {"text": "x" * (MAX_TEXT_CHARS + 1)}, {"text": "série", "extra": 1}, {}],
    )
    def test_rejects_malformed_requests(self, body: dict[str, Any]) -> None:
        response = client.post(GENERATE_TEXT, json=body)

        assert response.status_code == 422
        assert response.json()["type"] == "urn:vcccircuitlab:problem:invalid-document"
