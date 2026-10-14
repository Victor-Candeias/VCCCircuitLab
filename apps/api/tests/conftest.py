from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.auth.dependencies import require_user
from app.main import app
from app.models.user import UserOut

FAKE_USER = UserOut(
    id="000000000000000000000001",
    name="Utilizador de teste",
    email="teste@vcccircuitlab.test",
    created_at=datetime(2025, 1, 1, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def authenticated(request: pytest.FixtureRequest) -> Iterator[None]:
    """As rotas protegidas recebem um utilizador falso, exceto nos testes `real_auth`."""
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(require_user, None)
