"""Testes de `GET/POST/PUT/DELETE /api/v1/templates` (F2-10)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mongomock import MongoClient

from app.auth.dependencies import require_user
from app.db.mongo import get_database
from app.main import app
from app.models.user import UserOut

URL = "/api/v1/templates"
PROBLEM = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"

FAKE_USER = UserOut(
    id="000000000000000000000001",
    name="Utilizador de teste",
    email="teste@vcccircuitlab.test",
    created_at=datetime(2025, 1, 1, tzinfo=UTC),
)
FAKE_ADMIN = UserOut(
    id="000000000000000000000002",
    name="Admin de teste",
    email="admin@vcccircuitlab.test",
    role="ADMIN",
    created_at=datetime(2025, 1, 1, tzinfo=UTC),
)

TEMPLATE: dict[str, Any] = {
    "type": "lamp2",
    "label": "Lâmpada 2",
    "category": "load",
    "idPrefix": "L2",
    "symbol": "lamp2_iec",
    "size": {"width": 40, "height": 40},
    "pins": [
        {"id": "a", "kind": "passive", "position": {"x": -20, "y": 0}},
        {"id": "b", "kind": "passive", "position": {"x": 20, "y": 0}},
    ],
    "properties": {
        "ratedVoltageV": {"type": "number", "title": "Tensão", "unit": "V", "default": 12}
    },
    "simulationModel": None,
}


@pytest.fixture
def db() -> Iterator[Any]:
    database = MongoClient().get_database("teste")
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)


def as_admin() -> None:
    app.dependency_overrides[require_user] = lambda: FAKE_ADMIN


client = TestClient(app)


def test_list_templates_starts_empty(db) -> None:
    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


def test_user_cannot_create_template(db) -> None:
    response = client.post(URL, json=TEMPLATE)

    assert response.status_code == 403
    assert response.headers["content-type"] == PROBLEM
    assert response.json()["code"] == "FORBIDDEN"
    assert db["templates"].count_documents({}) == 0


def test_admin_can_create_and_list_template(db) -> None:
    as_admin()

    response = client.post(URL, json=TEMPLATE)

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "lamp2"
    assert body["idPrefix"] == "L2"
    assert body["createdBy"] == FAKE_ADMIN.email
    assert body["createdAt"]
    assert body["updatedAt"]

    listed = client.get(URL).json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]

    fetched = client.get(f"{URL}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["type"] == "lamp2"


def test_get_unknown_template_returns_404(db) -> None:
    response = client.get(f"{URL}/000000000000000000000099")

    assert response.status_code == 404
    assert response.json()["code"] == "TEMPLATE_NOT_FOUND"


def test_duplicate_type_is_rejected(db) -> None:
    as_admin()
    assert client.post(URL, json=TEMPLATE).status_code == 201

    response = client.post(URL, json=TEMPLATE)

    assert response.status_code == 409
    assert response.json()["code"] == "TEMPLATE_TYPE_ALREADY_EXISTS"
    assert db["templates"].count_documents({}) == 1


def test_admin_can_update_template(db) -> None:
    as_admin()
    created = client.post(URL, json=TEMPLATE).json()

    response = client.put(f"{URL}/{created['id']}", json={**TEMPLATE, "label": "Lâmpada nova"})

    assert response.status_code == 200
    assert response.json()["label"] == "Lâmpada nova"


def test_update_unknown_template_returns_404(db) -> None:
    as_admin()

    response = client.put(f"{URL}/000000000000000000000099", json=TEMPLATE)

    assert response.status_code == 404
    assert response.json()["code"] == "TEMPLATE_NOT_FOUND"


def test_user_cannot_update_or_delete_template(db) -> None:
    as_admin()
    created = client.post(URL, json=TEMPLATE).json()
    app.dependency_overrides[require_user] = lambda: FAKE_USER  # volta ao utilizador normal

    update_response = client.put(f"{URL}/{created['id']}", json=TEMPLATE)
    delete_response = client.delete(f"{URL}/{created['id']}")

    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_admin_can_delete_template(db) -> None:
    as_admin()
    created = client.post(URL, json=TEMPLATE).json()

    response = client.delete(f"{URL}/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"{URL}/{created['id']}").status_code == 404


def test_delete_unknown_template_returns_404(db) -> None:
    as_admin()

    response = client.delete(f"{URL}/000000000000000000000099")

    assert response.status_code == 404


def test_invalid_body_returns_422(db) -> None:
    as_admin()

    response = client.post(URL, json={"type": "x"})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM


def test_extra_fields_are_rejected(db) -> None:
    as_admin()

    response = client.post(URL, json={**TEMPLATE, "unexpected": True})

    assert response.status_code == 422
