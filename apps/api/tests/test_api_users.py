from collections.abc import Iterator
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from mongomock import MongoClient

from app.db.mongo import get_database
from app.main import app
from app.security.crypto import FieldCipher, get_cipher
from app.security.passwords import verify_password

URL = "/api/v1/users"
PROBLEM = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"
PASSWORD = "Abcdefg1!"

VALID: dict[str, Any] = {
    "name": "Ana Silva",
    "email": "Ana.Silva@Exemplo.pt",
    "password": PASSWORD,
    "passwordConfirm": PASSWORD,
}


@pytest.fixture
def db() -> Iterator[Any]:
    database = MongoClient().get_database("teste")
    cipher = FieldCipher(Fernet.generate_key().decode())
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_cipher] = lambda: cipher
    database.cipher = cipher
    yield database
    app.dependency_overrides.clear()


client = TestClient(app)


def post(**changes: Any) -> Any:
    return client.post(URL, json={**VALID, **changes})


def test_create_user_stores_encrypted_data(db) -> None:
    response = post()

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ana Silva"
    assert body["email"] == "ana.silva@exemplo.pt"
    assert "password" not in body
    assert "passwordHash" not in body
    assert body["createdAt"]

    stored = db["users"].find_one()
    assert str(stored["_id"]) == body["id"]
    raw = repr(stored)
    for secret in ("Ana Silva", "exemplo.pt", PASSWORD):
        assert secret not in raw
    assert db.cipher.decrypt(stored["name"]) == "Ana Silva"
    assert db.cipher.decrypt(stored["email"]) == "ana.silva@exemplo.pt"
    assert verify_password(PASSWORD, stored["passwordHash"])


def test_duplicate_email_is_rejected_case_insensitively(db) -> None:
    assert post().status_code == 201

    response = post(email="ANA.SILVA@exemplo.PT", name="Outra")

    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["type"] == TYPE_PREFIX + "email-already-registered"
    assert body["code"] == "EMAIL_ALREADY_REGISTERED"
    assert db["users"].count_documents({}) == 1


@pytest.mark.parametrize(
    ("changes", "pointer"),
    [
        ({"name": "   "}, "/name"),
        ({"email": "sem-arroba"}, "/email"),
        ({"email": "a@b"}, "/email"),
        ({"password": "abc", "passwordConfirm": "abc"}, "/password"),
        ({"password": "abcdefgh", "passwordConfirm": "abcdefgh"}, "/password"),
        ({"passwordConfirm": "Abcdefg1?"}, "/passwordConfirm"),
    ],
)
def test_invalid_data_returns_422_with_pointer(db, changes: dict[str, Any], pointer: str) -> None:
    response = post(**changes)

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["title"] == "Dados inválidos"
    assert pointer in [e["pointer"] for e in body["errors"]]
    assert PASSWORD not in response.text
    assert db["users"].count_documents({}) == 0


def test_missing_and_extra_fields_are_rejected(db) -> None:
    response = client.post(URL, json={"name": "Ana", "role": "admin"})

    assert response.status_code == 422
    pointers = {e["pointer"] for e in response.json()["errors"]}
    assert {"/email", "/password", "/passwordConfirm", "/role"} <= pointers


def test_unavailable_database_returns_503_without_details(monkeypatch) -> None:
    for name in ("MONGODB_USERNAME", "MONGODB_PASSWORD", "DATA_ENCRYPTION_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("app.db.mongo.load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr("app.security.crypto.load_dotenv", lambda *a, **k: False)
    from app.db.mongo import get_client

    get_client.cache_clear()

    response = post()

    assert response.status_code == 503
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "MONGODB" not in response.text
    assert "DATA_ENCRYPTION_KEY" not in response.text
