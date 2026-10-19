"""Segurança operacional (E5-04): CORS, limite do corpo, rate limiting e dados como dados."""

import json
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.http_security import RateLimiter, SecuritySettings, install_security
from app.main import app
from app.problems import install_problem_handlers

FRONTEND = "https://frontend.example.pt"


def make_client(**settings: object) -> TestClient:
    """App mínima com os middlewares e um endpoint que lê o corpo."""
    test_app = FastAPI()
    install_problem_handlers(test_app)
    install_security(test_app, SecuritySettings(**settings))  # type: ignore[arg-type]

    @test_app.post("/api/v1/auth/login")
    @test_app.post("/api/v1/echo")
    def echo(body: dict) -> dict:
        return {"size": len(json.dumps(body))}

    @test_app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return TestClient(test_app)


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", f" {FRONTEND}/ , http://localhost:5173 ")
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "2048")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.delenv("AUTH_RATE_LIMIT_PER_MINUTE", raising=False)
    settings = SecuritySettings.from_env()
    assert settings.cors_origins == (FRONTEND, "http://localhost:5173")
    assert settings.max_body_bytes == 2048
    assert settings.rate_limit_per_minute == 0
    assert settings.auth_rate_limit_per_minute == 20

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "muitos")
    with pytest.raises(ValueError, match="RATE_LIMIT_PER_MINUTE"):
        SecuritySettings.from_env()


class TestCors:
    def test_allowed_origin_gets_cors_headers_and_preflight(self) -> None:
        client = make_client(cors_origins=(FRONTEND,))
        response = client.post("/api/v1/echo", json={}, headers={"Origin": FRONTEND})
        assert response.headers["access-control-allow-origin"] == FRONTEND

        preflight = client.options(
            "/api/v1/echo",
            headers={
                "Origin": FRONTEND,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == FRONTEND

    def test_other_origins_are_not_allowed(self) -> None:
        client = make_client(cors_origins=(FRONTEND,))
        response = client.post("/api/v1/echo", json={}, headers={"Origin": "https://mal.example"})
        assert "access-control-allow-origin" not in response.headers
        preflight = client.options(
            "/api/v1/echo",
            headers={"Origin": "https://mal.example", "Access-Control-Request-Method": "POST"},
        )
        assert preflight.status_code == 400

    def test_without_configuration_no_origin_is_allowed(self) -> None:
        response = make_client().get("/health", headers={"Origin": FRONTEND})
        assert "access-control-allow-origin" not in response.headers


class TestBodyLimit:
    def test_declared_content_length_above_limit_is_413(self) -> None:
        client = make_client(max_body_bytes=100, cors_origins=(FRONTEND,))
        response = client.post("/api/v1/echo", json={"x": "a" * 200}, headers={"Origin": FRONTEND})
        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "PAYLOAD_TOO_LARGE"
        # O erro também traz CORS, para o frontend o conseguir ler.
        assert response.headers["access-control-allow-origin"] == FRONTEND

    def test_streamed_body_above_limit_is_413(self) -> None:
        client = make_client(max_body_bytes=100)

        def chunks() -> Iterator[bytes]:
            yield b'{"x": "'
            yield b"a" * 200
            yield b'"}'

        response = client.post(
            "/api/v1/echo", content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413
        assert response.json()["code"] == "PAYLOAD_TOO_LARGE"

    def test_body_within_limit_passes(self) -> None:
        response = make_client(max_body_bytes=100).post("/api/v1/echo", json={"x": "a"})
        assert response.status_code == 200


class TestRateLimit:
    def test_over_limit_is_429_with_retry_after(self) -> None:
        client = make_client(rate_limit_per_minute=3)
        assert [client.post("/api/v1/echo", json={}).status_code for _ in range(3)] == [200] * 3
        response = client.post("/api/v1/echo", json={})
        assert response.status_code == 429
        assert response.json()["code"] == "RATE_LIMITED"
        assert 1 <= int(response.headers["retry-after"]) <= 60

    def test_health_and_preflight_are_exempt(self) -> None:
        client = make_client(rate_limit_per_minute=1, cors_origins=(FRONTEND,))
        for _ in range(5):
            assert client.get("/health").status_code == 200
            preflight = client.options(
                "/api/v1/echo",
                headers={"Origin": FRONTEND, "Access-Control-Request-Method": "POST"},
            )
            assert preflight.status_code == 200

    def test_auth_has_its_own_stricter_bucket(self) -> None:
        client = make_client(rate_limit_per_minute=100, auth_rate_limit_per_minute=2)
        codes = [client.post("/api/v1/auth/login", json={}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        assert client.post("/api/v1/echo", json={}).status_code == 200

    def test_zero_disables(self) -> None:
        client = make_client(rate_limit_per_minute=0)
        assert all(client.post("/api/v1/echo", json={}).status_code == 200 for _ in range(10))

    def test_window_slides_and_clients_are_independent(self) -> None:
        now = [0.0]
        limiter = RateLimiter(clock=lambda: now[0])
        assert limiter.hit(("api", "1.1.1.1"), 1) is None
        assert limiter.hit(("api", "1.1.1.1"), 1) == pytest.approx(60)
        assert limiter.hit(("api", "2.2.2.2"), 1) is None
        now[0] = 60.5
        assert limiter.hit(("api", "1.1.1.1"), 1) is None


def test_code_like_input_is_treated_as_data() -> None:
    """Nunca se executa código do cliente: o template é procurado num registo fixo e os textos
    são devolvidos tal como vieram."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/circuits/generate",
        json={"template": "__import__('os').system('id')", "parameters": {}},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNKNOWN_TEMPLATE"
