"""Dependência que exige uma sessão válida (`Authorization: Bearer <token>`)."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.auth.errors import NotAuthenticatedError, NotAuthorizedError
from app.auth.service import to_user_out
from app.auth.sessions import find_session_user
from app.db.mongo import get_database
from app.models.user import ADMIN_ROLE, UserOut
from app.security.crypto import FieldCipher, get_cipher

_bearer = HTTPBearer(auto_error=False, description="Token devolvido por POST /api/v1/auth/login")


def bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None or not credentials.credentials:
        raise NotAuthenticatedError
    return credentials.credentials


# `token` vem primeiro: sem token a resposta é 401, mesmo que a BD não esteja disponível.
def require_user(
    token: Annotated[str, Depends(bearer_token)],
    db: Annotated[Database, Depends(get_database)],
    cipher: Annotated[FieldCipher, Depends(get_cipher)],
) -> UserOut:
    user = find_session_user(db, token)
    if user is None:
        raise NotAuthenticatedError
    return to_user_out(cipher, user)


CurrentUser = Annotated[UserOut, Depends(require_user)]


def require_admin(user: CurrentUser) -> UserOut:
    if user.role != ADMIN_ROLE:
        raise NotAuthorizedError
    return user


CurrentAdmin = Annotated[UserOut, Depends(require_admin)]
