"""Observabilidade (E5-05): request ID, log de pedidos sem dados sensíveis, métricas e readiness."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import health as health_module

METRICS_TOKEN = "token-de-metricas-de-teste"


@pytest.fixture
def client() -> TestClient:
    app.state.metrics.reset()
    return TestClient(app)


def access_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "app.access"]


def test_generates_request_id(client: TestClient) -> None:
    first = client.get("/api/v1/components").headers["x-request-id"]
    second = client.get("/api/v1/components").headers["x-request-id"]
    assert len(first) == 32
    assert first != second


def test_propagates_safe_request_id_and_replaces_unsafe(client: TestClient) -> None:
    ok = client.get("/health", headers={"X-Request-ID": "proxy-abc.123"})
    assert ok.headers["x-request-id"] == "proxy-abc.123"
    bad = client.get("/health", headers={"X-Request-ID": 'a b"<script>'})
    assert bad.headers["x-request-id"] != 'a b"<script>'
    assert len(bad.headers["x-request-id"]) == 32


def test_access_log_has_route_template_and_no_sensitive_data(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.access")
    response = client.get(
        "/api/v1/templates/segredo-no-caminho?token=segredo-na-query",
        headers={"Authorization": "Bearer segredo-no-header", "X-Request-ID": "req-1"},
    )
    client.post("/api/v1/users", json={"email": "pessoa@exemplo.pt", "password": "x"})

    lines = access_lines(caplog)
    assert len(lines) == 2
    assert lines[0] == (
        f"request_id=req-1 method=GET route=/api/v1/templates/{{template_id}} "
        f"status={response.status_code} duration_ms=" + lines[0].rsplit("=", 1)[1]
    )
    assert "route=/api/v1/users status=422" in lines[1]
    joined = "\n".join(r.getMessage() for r in caplog.records)
    for secret in ("segredo", "pessoa@exemplo.pt", "testclient"):
        assert secret not in joined


def test_unmatched_routes_do_not_create_unbounded_labels(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.access")
    client.get("/nao/existe/123")
    assert "route=unmatched status=404" in access_lines(caplog)[0]
    assert "/nao/existe" not in app.state.metrics.render()


def test_health_endpoints_are_not_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.access")
    client.get("/health")
    assert access_lines(caplog) == []


def test_metrics_disabled_without_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    assert client.get("/metrics").status_code == 404


def test_metrics_require_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_TOKEN", METRICS_TOKEN)
    assert client.get("/metrics").status_code == 401
    wrong = client.get("/metrics", headers={"Authorization": "Bearer outro"})
    assert wrong.status_code == 401
    assert wrong.headers["www-authenticate"] == "Bearer"


def test_metrics_prometheus_output(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_TOKEN", METRICS_TOKEN)
    client.get("/api/v1/templates/um")
    client.get("/api/v1/templates/dois")

    response = client.get("/metrics", headers={"Authorization": f"Bearer {METRICS_TOKEN}"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    body = response.text
    status = client.get("/api/v1/templates/um").status_code
    assert (
        f'http_requests_total{{method="GET",route="/api/v1/templates/{{template_id}}",'
        f'status="{status}"}} 2' in body
    )
    assert (
        'http_request_duration_seconds_count{method="GET",'
        'route="/api/v1/templates/{template_id}"} 2' in body
    )
    assert 'le="+Inf"} 2' in body
    assert "http_requests_in_progress 1" in body  # o próprio pedido a /metrics
    assert "process_uptime_seconds " in body
    assert "/um" not in body
    assert "/dois" not in body


class FakeAdmin:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    def command(self, name: str) -> dict:
        assert name == "ping"
        if self.error:
            raise self.error
        return {"ok": 1}


class FakeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.admin = FakeAdmin(error)


def test_ready_when_database_responds(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "get_client", lambda: FakeClient())
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_not_ready_when_database_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    error = RuntimeError("mongodb://utilizador:palavra-passe@host recusou a ligação")
    monkeypatch.setattr(health_module, "get_client", lambda: FakeClient(error))
    caplog.set_level(logging.WARNING)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"database": "unavailable"}}
    assert "palavra-passe" not in response.text
    assert "palavra-passe" not in caplog.text
    assert "RuntimeError" in caplog.text
