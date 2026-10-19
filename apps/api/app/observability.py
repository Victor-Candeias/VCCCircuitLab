"""Observabilidade (E5-05): request ID, log de pedidos e métricas, sem dados sensíveis.

Cada pedido gera uma linha no logger `app.access`:

    request_id=… method=POST route=/api/v1/circuits/simulate status=200 duration_ms=12.3

A rota é o *template* (`/api/v1/templates/{template_id}`), nunca o caminho concreto, e não se
registam query strings, corpos, cabeçalhos (`Authorization`), emails nem IPs. As mesmas
dimensões alimentam as métricas Prometheus expostas em `GET /metrics` (`app/routes/metrics.py`).
"""

import logging
import os
import re
import threading
import time
import uuid
from collections import defaultdict

from starlette.types import ASGIApp, Message, Receive, Scope, Send

access_logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = b"x-request-id"
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
DURATION_BUCKETS_S = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
UNMATCHED_ROUTE = "unmatched"


def configure_logging() -> None:
    """Handler para os loggers `app.*` (o uvicorn só configura os seus), nível `LOG_LEVEL`."""
    logger = logging.getLogger("app")
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)


class Metrics:
    """Contadores e histograma em memória (por processo), no formato de texto do Prometheus."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
            self._buckets: dict[tuple[str, str], list[int]] = {}
            self._sums: dict[tuple[str, str], float] = defaultdict(float)
            self._counts: dict[tuple[str, str], int] = defaultdict(int)
            self._in_progress = 0

    def started(self) -> None:
        with self._lock:
            self._in_progress += 1

    def finished(self, method: str, route: str, status: int, duration_s: float) -> None:
        with self._lock:
            self._in_progress -= 1
            self._requests[(method, route, str(status))] += 1
            key = (method, route)
            buckets = self._buckets.setdefault(key, [0] * len(DURATION_BUCKETS_S))
            for i, bound in enumerate(DURATION_BUCKETS_S):
                if duration_s <= bound:
                    buckets[i] += 1
            self._sums[key] += duration_s
            self._counts[key] += 1

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP http_requests_total Pedidos HTTP concluídos.",
                "# TYPE http_requests_total counter",
            ]
            for (method, route, status), count in sorted(self._requests.items()):
                labels = _labels(method=method, route=route, status=status)
                lines.append(f"http_requests_total{{{labels}}} {count}")

            lines += [
                "# HELP http_request_duration_seconds Duração dos pedidos HTTP.",
                "# TYPE http_request_duration_seconds histogram",
            ]
            for (method, route), buckets in sorted(self._buckets.items()):
                base = _labels(method=method, route=route)
                for bound, count in zip(DURATION_BUCKETS_S, buckets, strict=True):
                    lines.append(
                        f'http_request_duration_seconds_bucket{{{base},le="{bound:g}"}} {count}'
                    )
                total = self._counts[(method, route)]
                lines.append(f'http_request_duration_seconds_bucket{{{base},le="+Inf"}} {total}')
                duration_sum = self._sums[(method, route)]
                lines.append(f"http_request_duration_seconds_sum{{{base}}} {duration_sum:.6f}")
                lines.append(f"http_request_duration_seconds_count{{{base}}} {total}")

            lines += [
                "# HELP http_requests_in_progress Pedidos HTTP em curso.",
                "# TYPE http_requests_in_progress gauge",
                f"http_requests_in_progress {self._in_progress}",
                "# HELP process_uptime_seconds Tempo desde o arranque do processo.",
                "# TYPE process_uptime_seconds gauge",
                f"process_uptime_seconds {time.monotonic() - self._started:.3f}",
            ]
        return "\n".join(lines) + "\n"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**labels: str) -> str:
    return ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels.items())


def _request_id(scope: Scope) -> str:
    incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER, b"").decode("latin-1")
    return incoming if _SAFE_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp, metrics: Metrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        status = 500
        start = time.perf_counter()
        self.metrics.started()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration = time.perf_counter() - start
            route_obj = scope.get("route")
            route = getattr(route_obj, "path", None) or UNMATCHED_ROUTE
            method = scope["method"]
            self.metrics.finished(method, route, status, duration)
            if route not in {"/health", "/health/ready", "/metrics"}:
                access_logger.info(
                    "request_id=%s method=%s route=%s status=%d duration_ms=%.1f",
                    request_id,
                    method,
                    route,
                    status,
                    duration * 1000,
                )
