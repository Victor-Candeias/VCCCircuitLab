"""Segurança operacional da API (E5-04): CORS restrito, limite de corpo e rate limiting.

Configuração por variáveis de ambiente (lidas uma vez, no arranque):

- `CORS_ALLOWED_ORIGINS`: origens autorizadas a chamar a API a partir do browser, separadas por
  vírgulas (ex.: `https://utilizador.github.io`). Vazio = nenhuma (só pedidos da mesma origem,
  como o `vite dev` com proxy).
- `MAX_REQUEST_BODY_BYTES`: tamanho máximo do corpo de um pedido (omissão: 1 MiB) → 413.
- `RATE_LIMIT_PER_MINUTE`: pedidos por minuto e por IP (omissão: 120) → 429.
- `AUTH_RATE_LIMIT_PER_MINUTE`: idem para login e registo (omissão: 20), contra força bruta.

Um limite `0` desativa a respetiva proteção. O rate limiting é em memória, por processo: com
vários workers o limite efetivo multiplica-se pelo número de workers. O IP do cliente é o que o
uvicorn expõe em `scope["client"]` (com `--proxy-headers`/`FORWARDED_ALLOW_IPS`, o do
`X-Forwarded-For` enviado pelo reverse proxy).
"""

import math
import os
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.problems import ApiErrorCode, Issue, ProblemResponse, problem_response

WINDOW_S = 60.0
AUTH_ENDPOINTS = {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/users")}
EXEMPT_PATHS = {"/health"}


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} tem de ser um número inteiro (recebido {value!r}).") from exc
    if number < 0:
        raise ValueError(f"{name} não pode ser negativo.")
    return number


@dataclass(frozen=True)
class SecuritySettings:
    cors_origins: tuple[str, ...] = ()
    max_body_bytes: int = 1024 * 1024
    rate_limit_per_minute: int = 120
    auth_rate_limit_per_minute: int = 20

    @classmethod
    def from_env(cls) -> "SecuritySettings":
        load_dotenv(find_dotenv(), override=False)
        origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
        defaults = cls()
        return cls(
            cors_origins=tuple(o.strip().rstrip("/") for o in origins.split(",") if o.strip()),
            max_body_bytes=_int_env("MAX_REQUEST_BODY_BYTES", defaults.max_body_bytes),
            rate_limit_per_minute=_int_env("RATE_LIMIT_PER_MINUTE", defaults.rate_limit_per_minute),
            auth_rate_limit_per_minute=_int_env(
                "AUTH_RATE_LIMIT_PER_MINUTE", defaults.auth_rate_limit_per_minute
            ),
        )


# --- Limite do corpo -------------------------------------------------------------------------


class PayloadTooLargeError(HTTPException):
    """Corpo acima do limite, detetado ao ler um corpo sem `Content-Length` (streaming)."""

    def __init__(self, max_bytes: int) -> None:
        super().__init__(status_code=413)
        self.max_bytes = max_bytes


def _payload_too_large(request: Request, max_bytes: int) -> ProblemResponse:
    issue = Issue(
        code=ApiErrorCode.PAYLOAD_TOO_LARGE,
        message=f"O pedido excede o tamanho máximo de {max_bytes} bytes.",
    )
    return problem_response(
        request,
        status=413,
        kind="payload-too-large",
        title="Pedido demasiado grande",
        errors=[issue],
    )


async def _payload_too_large_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, PayloadTooLargeError)
    return _payload_too_large(request, exc.max_bytes)


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await _payload_too_large(Request(scope), self.max_bytes)(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise PayloadTooLargeError(self.max_bytes)
            return message

        await self.app(scope, limited_receive, send)


# --- Rate limiting ---------------------------------------------------------------------------


class RateLimiter:
    """Janela deslizante de `WINDOW_S` segundos por chave (grupo, IP), em memória."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._last_prune = clock()

    def reset(self) -> None:
        self._hits.clear()

    def hit(self, key: tuple[str, str], limit: int) -> float | None:
        """Regista um pedido; devolve `None` se for permitido ou os segundos até haver vaga."""
        now = self._clock()
        self._prune(now)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - WINDOW_S:
            hits.popleft()
        if len(hits) >= limit:
            return hits[0] + WINDOW_S - now
        hits.append(now)
        return None

    def _prune(self, now: float) -> None:
        # Remove chaves inativas de vez em quando, para a memória não crescer sem limite.
        if now - self._last_prune < WINDOW_S:
            return
        self._last_prune = now
        stale = [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - WINDOW_S]
        for key in stale:
            del self._hits[key]


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limiter: RateLimiter, api_limit: int, auth_limit: int) -> None:
        self.app = app
        self.limiter = limiter
        self.api_limit = api_limit
        self.auth_limit = auth_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        is_auth = (scope["method"], scope["path"].rstrip("/")) in AUTH_ENDPOINTS
        group, limit = ("auth", self.auth_limit) if is_auth else ("api", self.api_limit)
        if limit > 0:
            client = scope.get("client")
            retry_after = self.limiter.hit((group, client[0] if client else "?"), limit)
            if retry_after is not None:
                seconds = max(1, math.ceil(retry_after))
                issue = Issue(
                    code=ApiErrorCode.RATE_LIMITED,
                    message=f"Demasiados pedidos. Tente novamente dentro de {seconds} s.",
                )
                response = problem_response(
                    Request(scope),
                    status=429,
                    kind="rate-limited",
                    title="Demasiados pedidos",
                    errors=[issue],
                    headers={"Retry-After": str(seconds)},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


# --- Instalação ------------------------------------------------------------------------------


def install_security(app: FastAPI, settings: SecuritySettings | None = None) -> RateLimiter:
    """Instala, de fora para dentro: CORS → rate limiting → limite do corpo. O CORS fica por
    fora para que as respostas 413/429 também tragam os cabeçalhos CORS (o browser só deixa o
    frontend ler o erro assim). Devolve o `RateLimiter` (também em `app.state.rate_limiter`)."""
    settings = settings or SecuritySettings.from_env()
    limiter = RateLimiter()
    app.state.rate_limiter = limiter
    app.add_exception_handler(PayloadTooLargeError, _payload_too_large_handler)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        api_limit=settings.rate_limit_per_minute,
        auth_limit=settings.auth_rate_limit_per_minute,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Retry-After"],
        allow_credentials=False,
        max_age=600,
    )
    return limiter
