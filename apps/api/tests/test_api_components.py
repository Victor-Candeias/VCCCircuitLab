"""Testes de `GET /api/v1/components` (E2-06)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_components_returns_catalog() -> None:
    response = client.get("/api/v1/components")

    assert response.status_code == 200
    body = response.json()
    assert body["catalogVersion"] == "1.0"
    assert body["gridSize"] > 0
    assert len(body["components"]) >= 1

    types = {c["type"] for c in body["components"]}
    assert "resistor" in types
    assert "ground" in types


def test_get_components_flags_solver_support() -> None:
    response = client.get("/api/v1/components")

    body = response.json()
    resistor = next(c for c in body["components"] if c["type"] == "resistor")
    assert resistor["simulationModel"] == "resistor"
    assert resistor["supported"] is True


def test_get_components_exposes_property_schema() -> None:
    response = client.get("/api/v1/components")

    body = response.json()
    resistor = next(c for c in body["components"] if c["type"] == "resistor")
    prop = resistor["properties"]["resistanceOhm"]
    assert prop["type"] == "number"
    assert prop["unit"] == "Ω"
    assert "default" in prop
