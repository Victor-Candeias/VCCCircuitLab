import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from mongomock import MongoClient

from app.auth.dependencies import CurrentAdmin
from app.db.mongo import get_database
from app.main import app
from app.security.crypto import FieldCipher, get_cipher
from app.users.service import ensure_admin

pytestmark = pytest.mark.real_auth

PROBLEM = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"
PASSWORD = "Abcdefg1!"
EMAIL = "ana.silva@exemplo.pt"

client = TestClient(app)


@pytest.fixture
def db() -> Iterator[Any]:
    database = MongoClient(tz_aware=True).get_database("teste")
    cipher = FieldCipher(Fernet.generate_key().decode())
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_cipher] = lambda: cipher
    response = client.post(
        "/api/v1/users",
        json={
            "name": "Ana Silva",
            "email": EMAIL,
            "password": PASSWORD,
            "passwordConfirm": PASSWORD,
        },
    )
    assert response.status_code == 201
    yield database
    app.dependency_overrides.clear()


def login(email: str = EMAIL, password: str = PASSWORD) -> Any:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_unauthenticated(response: Any) -> None:
    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body["type"] == f"{TYPE_PREFIX}not-authenticated"
    assert body["errors"][0]["code"] == "NOT_AUTHENTICATED"


def test_login_returns_token_and_user(db) -> None:
    response = login(email="  Ana.Silva@Exemplo.PT ")

    assert response.status_code == 200
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert len(body["accessToken"]) >= 40
    assert body["user"]["name"] == "Ana Silva"
    assert body["user"]["email"] == EMAIL
    expires = datetime.fromisoformat(body["expiresAt"])
    assert timedelta(hours=7) < expires - datetime.now(UTC) <= timedelta(hours=8)


def test_login_returns_user_role(db) -> None:
    assert login().json()["user"]["role"] == "USER"


def test_users_without_role_are_treated_as_user(db) -> None:
    db["users"].update_one({}, {"$unset": {"role": ""}})
    token = login().json()["accessToken"]

    assert client.get("/api/v1/auth/me", headers=auth(token)).json()["role"] == "USER"


ADMIN_EMAIL = "admin@exemplo.pt"
ADMIN_PASSWORD = "bichocao"


def seed_admin(db) -> None:
    ensure_admin(db, app.dependency_overrides[get_cipher](), "Admin", ADMIN_EMAIL, ADMIN_PASSWORD)


def test_admin_seed_creates_admin_and_is_idempotent(db) -> None:
    seed_admin(db)
    seed_admin(db)

    assert db["users"].count_documents({"role": "ADMIN"}) == 1
    body = login(ADMIN_EMAIL, ADMIN_PASSWORD).json()
    assert body["user"]["role"] == "ADMIN"
    assert body["user"]["name"] == "Admin"


def test_admin_seed_promotes_existing_account_and_resets_password(db) -> None:
    ensure_admin(db, app.dependency_overrides[get_cipher](), "Ana", EMAIL, ADMIN_PASSWORD)

    assert db["users"].count_documents({}) == 1
    assert login(EMAIL, PASSWORD).status_code == 401
    assert login(EMAIL, ADMIN_PASSWORD).json()["user"]["role"] == "ADMIN"


@pytest.fixture
def admin_only_route() -> Iterator[None]:
    @app.get("/test-admin-only")
    def admin_only(_admin: CurrentAdmin) -> str:
        return "ok"

    yield
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", "") != "/test-admin-only"
    ]


def test_admin_routes_require_admin_role(db, admin_only_route) -> None:
    seed_admin(db)
    user_token = login().json()["accessToken"]
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD).json()["accessToken"]

    assert_unauthenticated(client.get("/test-admin-only"))

    forbidden = client.get("/test-admin-only", headers=auth(user_token))
    assert forbidden.status_code == 403
    assert forbidden.headers["content-type"].startswith(PROBLEM)
    assert forbidden.json()["type"] == f"{TYPE_PREFIX}forbidden"
    assert forbidden.json()["code"] == "FORBIDDEN"

    assert client.get("/test-admin-only", headers=auth(admin_token)).status_code == 200


def test_session_stores_only_token_hash(db) -> None:
    token = login().json()["accessToken"]

    stored = db["sessions"].find_one()
    assert token not in repr(stored)
    assert stored["tokenHash"] == hashlib.sha256(token.encode()).hexdigest()
    assert stored["userId"] == db["users"].find_one()["_id"]
    indexes = db["sessions"].index_information()
    assert any(i.get("expireAfterSeconds") == 0 for i in indexes.values())


@pytest.mark.parametrize(
    ("email", "password"),
    [(EMAIL, "Errada123!"), ("outro@exemplo.pt", PASSWORD)],
    ids=["wrong-password", "unknown-email"],
)
def test_login_rejects_invalid_credentials(db, email: str, password: str) -> None:
    response = login(email=email, password=password)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert body["type"] == f"{TYPE_PREFIX}invalid-credentials"
    assert body["errors"][0]["message"] == "Email ou password incorretos."
    assert db["sessions"].count_documents({}) == 0


def test_login_validates_body(db) -> None:
    response = client.post("/api/v1/auth/login", json={"email": EMAIL})

    assert response.status_code == 422
    assert response.json()["title"] == "Dados inválidos"


def test_me_returns_session_user(db) -> None:
    token = login().json()["accessToken"]

    response = client.get("/api/v1/auth/me", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


@pytest.mark.parametrize("headers", [{}, auth("token-invalido"), {"Authorization": "Basic x"}])
def test_me_requires_valid_token(db, headers: dict[str, str]) -> None:
    assert_unauthenticated(client.get("/api/v1/auth/me", headers=headers))


def test_expired_session_is_rejected(db) -> None:
    token = login().json()["accessToken"]
    db["sessions"].update_one({}, {"$set": {"expiresAt": datetime.now(UTC) - timedelta(seconds=1)}})

    assert_unauthenticated(client.get("/api/v1/auth/me", headers=auth(token)))


def test_logout_ends_session(db) -> None:
    token = login().json()["accessToken"]

    response = client.post("/api/v1/auth/logout", headers=auth(token))

    assert response.status_code == 204
    assert db["sessions"].count_documents({}) == 0
    assert_unauthenticated(client.get("/api/v1/auth/me", headers=auth(token)))


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", "/api/v1/components"),
        ("post", "/api/v1/circuits/validate"),
        ("post", "/api/v1/circuits/simulate"),
        ("post", "/api/v1/circuits/generate"),
    ],
)
def test_protected_routes_require_session(method: str, url: str) -> None:
    # Sem token a resposta é 401 sem tocar na BD (não há override de get_database).
    assert_unauthenticated(client.request(method, url, json={}))


def test_protected_route_accepts_valid_session(db) -> None:
    token = login().json()["accessToken"]

    response = client.get("/api/v1/components", headers=auth(token))

    assert response.status_code == 200


def test_public_routes_stay_open() -> None:
    assert client.get("/health").status_code == 200
