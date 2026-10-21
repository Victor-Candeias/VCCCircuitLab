"""Testes de `/api/v1/projects`: projetos na conta, partilha e colaboração (F2-09)."""

from collections.abc import Iterator
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from mongomock import MongoClient

from app.db.mongo import get_database
from app.main import app
from app.security.crypto import FieldCipher, get_cipher
from tests.factories import source_resistor

pytestmark = pytest.mark.real_auth

URL = "/api/v1/projects"
PROBLEM = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"
PASSWORD = "Abcdefg1!"

client = TestClient(app)


def _register_and_login(name: str, email: str) -> dict[str, str]:
    body = {"name": name, "email": email, "password": PASSWORD, "passwordConfirm": PASSWORD}
    assert client.post("/api/v1/users", json=body).status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    data = response.json()
    return {"Authorization": f"Bearer {data['accessToken']}", "id": data["user"]["id"]}


@pytest.fixture
def users() -> Iterator[dict[str, dict[str, str]]]:
    database = MongoClient(tz_aware=True).get_database("teste")
    cipher = FieldCipher(Fernet.generate_key().decode())
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_cipher] = lambda: cipher
    yield {
        "ana": _register_and_login("Ana Silva", "ana@exemplo.pt"),
        "rui": _register_and_login("Rui Costa", "rui@exemplo.pt"),
        "eva": _register_and_login("Eva Lopes", "eva@exemplo.pt"),
    }
    app.dependency_overrides.clear()


def headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": user["Authorization"]}


def assert_problem(response: Any, status: int, kind: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert body["type"] == f"{TYPE_PREFIX}{kind}"
    return body


def create(user: dict[str, str], **circuit_changes: Any) -> dict[str, Any]:
    circuit = source_resistor() | circuit_changes
    response = client.post(URL, json={"circuit": circuit}, headers=headers(user))
    assert response.status_code == 201
    return response.json()


def share(owner: dict[str, str], project_id: str, email: str, role: str) -> Any:
    return client.put(
        f"{URL}/{project_id}/shares", json={"email": email, "role": role}, headers=headers(owner)
    )


def test_requires_session(users) -> None:
    assert_problem(client.get(URL), 401, "not-authenticated")


def test_create_and_open_project(users) -> None:
    created = create(users["ana"], name="Divisor")

    assert created["name"] == "Divisor"
    assert created["access"] == "owner"
    assert created["version"] == 1
    assert created["owner"] == {
        "id": users["ana"]["id"],
        "name": "Ana Silva",
        "email": "ana@exemplo.pt",
    }
    assert created["updatedBy"]["id"] == users["ana"]["id"]
    assert created["shares"] == []
    assert created["circuit"]["components"][1]["id"] == "R1"

    opened = client.get(f"{URL}/{created['id']}", headers=headers(users["ana"]))
    assert opened.status_code == 200
    assert opened.json() == created


def test_invalid_circuit_is_rejected(users) -> None:
    circuit = source_resistor() | {"units": "imperial"}

    response = client.post(URL, json={"circuit": circuit}, headers=headers(users["ana"]))

    assert response.status_code == 422


def test_list_includes_own_and_shared_projects_only(users) -> None:
    own = create(users["ana"], name="Meu")
    shared = create(users["rui"], name="Do Rui")
    create(users["eva"], name="Da Eva")
    assert share(users["rui"], shared["id"], "ANA@exemplo.pt ", "viewer").status_code == 200

    response = client.get(URL, headers=headers(users["ana"]))

    assert response.status_code == 200
    listed = {p["id"]: p for p in response.json()}
    assert set(listed) == {own["id"], shared["id"]}
    assert listed[own["id"]]["access"] == "owner"
    assert listed[shared["id"]]["access"] == "viewer"
    assert listed[shared["id"]]["owner"]["name"] == "Rui Costa"
    assert "circuit" not in listed[shared["id"]]


def test_project_of_another_user_is_not_found(users) -> None:
    project = create(users["rui"])
    url = f"{URL}/{project['id']}"

    assert_problem(client.get(url, headers=headers(users["ana"])), 404, "project-not-found")
    assert_problem(client.delete(url, headers=headers(users["ana"])), 404, "project-not-found")
    assert_problem(
        client.get(f"{URL}/nao-e-um-id", headers=headers(users["ana"])), 404, "project-not-found"
    )


def test_editor_saves_and_version_increments(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "editor")
    circuit = source_resistor() | {"name": "Alterado pelo Rui"}

    response = client.put(
        f"{URL}/{project['id']}",
        json={"circuit": circuit, "version": 1},
        headers=headers(users["rui"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert body["name"] == "Alterado pelo Rui"
    assert body["access"] == "editor"
    assert body["updatedBy"]["name"] == "Rui Costa"


def test_stale_version_is_a_conflict(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "editor")
    url = f"{URL}/{project['id']}"
    first = {"circuit": source_resistor() | {"name": "Primeiro"}, "version": 1}
    second = {"circuit": source_resistor() | {"name": "Segundo"}, "version": 1}

    assert client.put(url, json=first, headers=headers(users["rui"])).status_code == 200
    body = assert_problem(
        client.put(url, json=second, headers=headers(users["ana"])), 409, "project-version-conflict"
    )

    assert body["code"] == "PROJECT_VERSION_CONFLICT"
    assert "versão atual: 2" in body["detail"]
    assert client.get(url, headers=headers(users["ana"])).json()["name"] == "Primeiro"


def test_viewer_cannot_save_delete_or_share(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "viewer")
    url = f"{URL}/{project['id']}"
    rui = headers(users["rui"])

    saved = client.put(url, json={"circuit": source_resistor(), "version": 1}, headers=rui)
    assert_problem(saved, 403, "forbidden")
    assert_problem(client.delete(url, headers=rui), 403, "forbidden")
    assert_problem(share(users["rui"], project["id"], "eva@exemplo.pt", "viewer"), 403, "forbidden")


def test_editor_cannot_delete_or_share(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "editor")

    deleted = client.delete(f"{URL}/{project['id']}", headers=headers(users["rui"]))

    assert_problem(deleted, 403, "forbidden")
    assert_problem(share(users["rui"], project["id"], "eva@exemplo.pt", "editor"), 403, "forbidden")


def test_share_updates_role_without_duplicating(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "viewer")

    response = share(users["ana"], project["id"], "rui@exemplo.pt", "editor")

    assert response.status_code == 200
    assert response.json()["shares"] == [
        {
            "user": {"id": users["rui"]["id"], "name": "Rui Costa", "email": "rui@exemplo.pt"},
            "role": "editor",
        }
    ]


def test_share_with_unknown_email_or_owner_is_rejected(users) -> None:
    project = create(users["ana"])

    unknown = share(users["ana"], project["id"], "ninguem@exemplo.pt", "viewer")
    owner = share(users["ana"], project["id"], "ana@exemplo.pt", "editor")
    bad_role = share(users["ana"], project["id"], "rui@exemplo.pt", "owner")

    assert assert_problem(unknown, 404, "share-user-not-found")["code"] == "SHARE_USER_NOT_FOUND"
    assert assert_problem(owner, 422, "invalid-share")["code"] == "INVALID_SHARE"
    assert bad_role.status_code == 422


def test_owner_removes_share_and_guest_leaves(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "editor")
    share(users["ana"], project["id"], "eva@exemplo.pt", "viewer")
    url = f"{URL}/{project['id']}"

    removed = client.delete(f"{url}/shares/{users['rui']['id']}", headers=headers(users["ana"]))
    left = client.delete(f"{url}/shares/{users['eva']['id']}", headers=headers(users["eva"]))

    assert removed.status_code == 204
    assert left.status_code == 204
    assert client.get(url, headers=headers(users["ana"])).json()["shares"] == []
    assert_problem(client.get(url, headers=headers(users["rui"])), 404, "project-not-found")


def test_guest_cannot_remove_other_guests(users) -> None:
    project = create(users["ana"])
    share(users["ana"], project["id"], "rui@exemplo.pt", "editor")
    share(users["ana"], project["id"], "eva@exemplo.pt", "viewer")

    response = client.delete(
        f"{URL}/{project['id']}/shares/{users['eva']['id']}", headers=headers(users["rui"])
    )

    assert_problem(response, 403, "forbidden")


def test_owner_deletes_project(users) -> None:
    project = create(users["ana"])
    url = f"{URL}/{project['id']}"

    assert client.delete(url, headers=headers(users["ana"])).status_code == 204
    assert_problem(client.get(url, headers=headers(users["ana"])), 404, "project-not-found")
