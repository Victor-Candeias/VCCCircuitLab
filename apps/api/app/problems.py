"""Respostas de erro `application/problem+json` (RFC 9457) para toda a API.

Cada problema tem `type`, `title`, `status`, `detail`, `instance` e duas extensões: `code`, o
código do primeiro erro, e `errors`, a lista de todos os erros (`code`, `message`, `refs` e,
nos erros de esquema, `pointer`, um JSON Pointer RFC 6901).
"""

import logging
from collections.abc import Sequence
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.errors import InvalidCredentialsError, NotAuthenticatedError, NotAuthorizedError
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.component_templates.errors import DuplicateTemplateTypeError, TemplateNotFoundError
from app.db.errors import DatabaseUnavailableError
from app.generation.errors import InvalidParametersError, UnknownTemplateError
from app.spice.errors import SimulationEngineError
from app.users.errors import EmailAlreadyRegisteredError

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"
TYPE_PREFIX = "urn:vcccircuitlab:problem:"


class ApiErrorCode(StrEnum):
    MALFORMED_JSON = "MALFORMED_JSON"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    INVALID_COMPONENT = "INVALID_COMPONENT"
    UNKNOWN_TEMPLATE = "UNKNOWN_TEMPLATE"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    SIMULATION_TIMEOUT = "SIMULATION_TIMEOUT"
    SIMULATION_ENGINE_ERROR = "SIMULATION_ENGINE_ERROR"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    TEMPLATE_TYPE_ALREADY_EXISTS = "TEMPLATE_TYPE_ALREADY_EXISTS"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


NUMERIC_CODES = {CircuitErrorCode.SINGULAR_MATRIX, CircuitErrorCode.ILL_CONDITIONED_MATRIX}


class CircuitIssue(BaseModel):
    code: str
    message: str
    refs: list[str] = []


class Issue(CircuitIssue):
    pointer: str | None = None


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str
    errors: list[Issue] = []


class ProblemResponse(JSONResponse):
    media_type = PROBLEM_MEDIA_TYPE


class SimulationTimeoutError(Exception):
    def __init__(self, timeout_s: float) -> None:
        self.timeout_s = timeout_s
        super().__init__(f"timeout de {timeout_s:g} s")


def problem_response(
    request: Request,
    *,
    status: int,
    kind: str,
    title: str,
    errors: Sequence[Issue],
    code: str | None = None,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
) -> ProblemResponse:
    """`kind` é o sufixo do `type` (`invalid-circuit`, …) ou `about:blank`."""
    if detail is None and errors:
        first = errors[0].message
        detail = first if len(errors) == 1 else f"{first} (+{len(errors) - 1} erro(s))"
    problem = Problem(
        type=kind if kind == "about:blank" else TYPE_PREFIX + kind,
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        code=code or errors[0].code,
        errors=list(errors),
    )
    return ProblemResponse(problem.model_dump(exclude_none=True), status, headers=headers)


def circuit_issues(errors: Sequence[CircuitError]) -> list[Issue]:
    return [Issue(code=str(e.code), message=e.message, refs=list(e.refs)) for e in errors]


# --- Erros de esquema (RequestValidationError) ----------------------------------------------

_TYPE_NAMES = {
    "bool_type": "booleano",
    "float_type": "número",
    "int_type": "inteiro",
    "string_type": "texto",
    "list_type": "lista",
    "dict_type": "objeto",
    "model_type": "objeto",
    "model_attributes_type": "objeto",
}
_MESSAGES = {
    "missing": "campo obrigatório em falta",
    "extra_forbidden": "campo não permitido",
    "finite_number": "tem de ser um número finito",
    "string_pattern_mismatch": "formato inválido",
    "string_too_short": "texto demasiado curto",
    "string_too_long": "texto demasiado longo",
    "too_short": "elementos a menos",
    "too_long": "elementos a mais",
}
_COMPARISONS = {
    "greater_than": (">", "gt"),
    "greater_than_equal": ("≥", "ge"),
    "less_than": ("<", "lt"),
    "less_than_equal": ("≤", "le"),
}


def _escape(segment: str | int) -> str:
    return str(segment).replace("~", "~0").replace("/", "~1")


def _pointer(loc: Sequence[str | int], body: Any) -> tuple[str, list[str | int]]:
    """JSON Pointer do erro. Pára nos segmentos que não pertencem ao corpo (variantes de uniões,
    como `bool`/`float`, que o Pydantic acrescenta depois de um valor escalar)."""
    path: list[str | int] = []
    current = body
    for segment in loc:
        if isinstance(current, dict):
            path.append(segment)
            current = current.get(segment) if isinstance(segment, str) else None
        elif isinstance(current, list) and isinstance(segment, int):
            path.append(segment)
            current = current[segment] if 0 <= segment < len(current) else None
        else:
            break
    return "".join(f"/{_escape(s)}" for s in path), path


def _message(group: list[dict[str, Any]]) -> str:
    # Numa união (ex.: `bool | número`), um erro que não seja de tipo indica a variante certa.
    specific = [e for e in group if e["type"] not in _TYPE_NAMES]
    if specific:
        error = specific[0]
        if error["type"] == "literal_error":
            return f"valor não permitido (esperado {error.get('ctx', {}).get('expected', '?')})"
        if error["type"] == "value_error":
            return str(error.get("ctx", {}).get("error", error["msg"])).rstrip(".")
        if error["type"] in _COMPARISONS:
            symbol, ctx_key = _COMPARISONS[error["type"]]
            bound = error.get("ctx", {}).get(ctx_key, "?")
            bound_text = f"{bound:g}" if isinstance(bound, int | float) else str(bound)
            return f"tem de ser {symbol} {bound_text}"
        return _MESSAGES.get(error["type"], error["msg"])
    names = list(dict.fromkeys(_TYPE_NAMES[e["type"]] for e in group))
    return f"tipo inválido (esperado {' ou '.join(names)})"


#: Parâmetros da análise transitória (`POST /circuits/simulate/transient`).
_ANALYSIS_PARAMETERS = {"stopTimeS", "timeStepS"}


def schema_issues(exc: RequestValidationError) -> list[Issue]:
    body = exc.body
    groups: dict[str, list[dict[str, Any]]] = {}
    paths: dict[str, list[str | int]] = {}
    for error in exc.errors():
        loc = list(error["loc"])
        if loc and loc[0] == "body":
            loc = loc[1:]
        pointer, path = _pointer(loc, body)
        groups.setdefault(pointer, []).append(error)
        paths[pointer] = path

    issues = []
    for pointer, group in groups.items():
        path = paths[pointer]
        code, refs = ApiErrorCode.INVALID_DOCUMENT, []
        # A análise transitória envolve o documento em `circuit` (F2-02).
        document, doc_path = body, path
        if path[:1] == ["circuit"] and isinstance(body, dict):
            document, doc_path = body["circuit"], path[1:]
        if len(path) == 1 and path[0] in _ANALYSIS_PARAMETERS:
            code = ApiErrorCode.INVALID_PARAMETERS
        elif len(doc_path) >= 2 and doc_path[0] == "components" and isinstance(doc_path[1], int):
            code = ApiErrorCode.INVALID_COMPONENT
            components = document["components"]
            component = components[doc_path[1]] if doc_path[1] < len(components) else None
            if isinstance(component, dict) and isinstance(component.get("id"), str):
                refs = [component["id"]]
        where = pointer or "/"
        message = f"{where}: {_message(group)}."
        issues.append(Issue(code=code, message=message, refs=refs, pointer=pointer))
    return issues


def parameter_issues(exc: PydanticValidationError) -> list[Issue]:
    """Erros de parâmetros de um template de geração, com `pointer` sob `/parameters`."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for error in exc.errors():
        pointer = "/parameters" + "".join(f"/{_escape(s)}" for s in error["loc"])
        groups.setdefault(pointer, []).append(error)
    return [
        Issue(
            code=ApiErrorCode.INVALID_PARAMETERS,
            message=f"{pointer}: {_message(group)}.",
            pointer=pointer,
        )
        for pointer, group in groups.items()
    ]


def _is_json(request: Request) -> bool:
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


# --- Handlers -------------------------------------------------------------------------------


async def _request_validation_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    if any(e["type"] == "json_invalid" for e in errors):
        issue = Issue(code=ApiErrorCode.MALFORMED_JSON, message="O corpo não é JSON válido.")
        return problem_response(
            request, status=400, kind="malformed-json", title="JSON inválido", errors=[issue]
        )
    if request.method in {"POST", "PUT", "PATCH"} and not _is_json(request):
        issue = Issue(
            code=ApiErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message="O corpo tem de ser enviado como application/json.",
        )
        return problem_response(
            request, status=415, kind="about:blank", title="Unsupported Media Type", errors=[issue]
        )
    is_user_request = request.url.path.startswith(("/api/v1/users", "/api/v1/auth"))
    return problem_response(
        request,
        status=422,
        kind="invalid-document",
        title="Dados inválidos" if is_user_request else "Documento de circuito inválido",
        errors=schema_issues(exc),
    )


async def _circuit_error_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, CircuitValidationError)
    if any(e.code in NUMERIC_CODES for e in exc.errors):
        kind, title = "simulation-failed", "Simulação impossível"
    else:
        kind, title = "invalid-circuit", "Circuito inválido"
    return problem_response(
        request, status=422, kind=kind, title=title, errors=circuit_issues(exc.errors)
    )


async def _unknown_template_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, UnknownTemplateError)
    issue = Issue(
        code=ApiErrorCode.UNKNOWN_TEMPLATE, message=f"O template de geração {exc.name} não existe."
    )
    return problem_response(
        request,
        status=422,
        kind="unknown-template",
        title="Template de geração desconhecido",
        errors=[issue],
    )


async def _invalid_parameters_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, InvalidParametersError)
    return problem_response(
        request,
        status=422,
        kind="invalid-parameters",
        title="Parâmetros de geração inválidos",
        errors=parameter_issues(exc.cause),
    )


async def _timeout_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, SimulationTimeoutError)
    issue = Issue(
        code=ApiErrorCode.SIMULATION_TIMEOUT,
        message=f"A simulação excedeu o limite de {exc.timeout_s:g} s.",
    )
    return problem_response(
        request,
        status=503,
        kind="simulation-timeout",
        title="Tempo de simulação esgotado",
        errors=[issue],
    )


async def _engine_error_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, SimulationEngineError)
    # O detalhe (executável em falta, saída do ngspice) fica só no log do servidor.
    logger.error("Motor de simulação indisponível: %s", exc)
    issue = Issue(
        code=ApiErrorCode.SIMULATION_ENGINE_ERROR,
        message="O motor de simulação está temporariamente indisponível.",
    )
    return problem_response(
        request,
        status=503,
        kind="simulation-engine-error",
        title="Motor de simulação indisponível",
        errors=[issue],
    )


async def _email_registered_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, EmailAlreadyRegisteredError)
    issue = Issue(
        code=ApiErrorCode.EMAIL_ALREADY_REGISTERED, message="Já existe uma conta com este email."
    )
    return problem_response(
        request,
        status=409,
        kind="email-already-registered",
        title="Email já registado",
        errors=[issue],
    )


async def _invalid_credentials_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, InvalidCredentialsError)
    issue = Issue(code=ApiErrorCode.INVALID_CREDENTIALS, message="Email ou password incorretos.")
    return problem_response(
        request, status=401, kind="invalid-credentials", title="Login inválido", errors=[issue]
    )


async def _not_authenticated_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, NotAuthenticatedError)
    issue = Issue(
        code=ApiErrorCode.NOT_AUTHENTICATED,
        message="Sessão inexistente ou expirada. Inicie sessão.",
    )
    return problem_response(
        request,
        status=401,
        kind="not-authenticated",
        title="Autenticação necessária",
        errors=[issue],
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _not_authorized_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, NotAuthorizedError)
    issue = Issue(code=ApiErrorCode.FORBIDDEN, message="Sem permissões para aceder a este recurso.")
    return problem_response(
        request, status=403, kind="forbidden", title="Acesso negado", errors=[issue]
    )


async def _template_not_found_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, TemplateNotFoundError)
    issue = Issue(
        code=ApiErrorCode.TEMPLATE_NOT_FOUND, message="Template de componente não encontrado."
    )
    return problem_response(
        request,
        status=404,
        kind="template-not-found",
        title="Template não encontrado",
        errors=[issue],
    )


async def _duplicate_template_type_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, DuplicateTemplateTypeError)
    issue = Issue(
        code=ApiErrorCode.TEMPLATE_TYPE_ALREADY_EXISTS,
        message="Já existe um template com este tipo de componente.",
    )
    return problem_response(
        request,
        status=409,
        kind="template-type-already-exists",
        title="Tipo de componente já existe",
        errors=[issue],
    )


async def _database_unavailable_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, DatabaseUnavailableError)
    # A causa (configuração em falta, credenciais, ligação) fica só no log do servidor.
    logger.warning("Base de dados indisponível: %s (%s)", exc, exc.__cause__)
    issue = Issue(
        code=ApiErrorCode.SERVICE_UNAVAILABLE, message="Serviço temporariamente indisponível."
    )
    return problem_response(
        request,
        status=503,
        kind="service-unavailable",
        title="Serviço indisponível",
        errors=[issue],
    )


async def _http_error_handler(request: Request, exc: Exception) -> ProblemResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = HTTPStatus(exc.status_code)
    detail = exc.detail if isinstance(exc.detail, str) else None
    if detail == status.phrase:
        detail = None
    return problem_response(
        request,
        status=status.value,
        kind="about:blank",
        title=status.phrase,
        errors=[],
        code=status.name,
        detail=detail,
        headers=exc.headers,
    )


async def _internal_error_handler(request: Request, exc: Exception) -> ProblemResponse:
    # Sem detalhes da exceção na resposta; o traceback fica no log do servidor.
    issue = Issue(code=ApiErrorCode.INTERNAL_ERROR, message="Erro interno do servidor.")
    return problem_response(
        request, status=500, kind="internal-error", title="Erro interno", errors=[issue]
    )


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Entradas `responses=` do OpenAPI para erros problem+json."""
    return {s: {"model": Problem, "description": HTTPStatus(s).phrase} for s in statuses}


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _request_validation_handler)
    app.add_exception_handler(CircuitValidationError, _circuit_error_handler)
    app.add_exception_handler(UnknownTemplateError, _unknown_template_handler)
    app.add_exception_handler(InvalidParametersError, _invalid_parameters_handler)
    app.add_exception_handler(SimulationTimeoutError, _timeout_handler)
    app.add_exception_handler(SimulationEngineError, _engine_error_handler)
    app.add_exception_handler(EmailAlreadyRegisteredError, _email_registered_handler)
    app.add_exception_handler(DatabaseUnavailableError, _database_unavailable_handler)
    app.add_exception_handler(InvalidCredentialsError, _invalid_credentials_handler)
    app.add_exception_handler(NotAuthenticatedError, _not_authenticated_handler)
    app.add_exception_handler(NotAuthorizedError, _not_authorized_handler)
    app.add_exception_handler(TemplateNotFoundError, _template_not_found_handler)
    app.add_exception_handler(DuplicateTemplateTypeError, _duplicate_template_type_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _internal_error_handler)

    original_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        # O FastAPI documenta os modelos de `responses=` como application/json.
        if app.openapi_schema is None:
            schema = original_openapi()
            for path in schema.get("paths", {}).values():
                for operation in path.values():
                    for status, response in operation.get("responses", {}).items():
                        content = response.get("content", {})
                        is_error = status.isdigit() and int(status) >= 400
                        if is_error and "application/json" in content:
                            content[PROBLEM_MEDIA_TYPE] = content.pop("application/json")
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
