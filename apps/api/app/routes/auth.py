"""Sessão: `POST /api/v1/auth/login`, `GET /api/v1/auth/me` e `POST /api/v1/auth/logout`."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pymongo.database import Database

from app.auth.dependencies import CurrentUser, bearer_token
from app.auth.service import authenticate, to_user_out
from app.auth.sessions import create_session, delete_session
from app.db.mongo import get_database
from app.models.user import UserOut
from app.problems import problem_responses
from app.security.crypto import FieldCipher, get_cipher
from app.security.passwords import MAX_PASSWORD_LENGTH

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]


class LoginResponse(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, serialize_by_alias=True
    )

    access_token: str = Field(alias="accessToken")
    token_type: Literal["bearer"] = Field("bearer", alias="tokenType")
    expires_at: datetime = Field(alias="expiresAt")
    user: UserOut


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Iniciar sessão",
    responses=problem_responses(401, 422, 503),
)
def login(
    body: LoginRequest,
    db: Annotated[Database, Depends(get_database)],
    cipher: Annotated[FieldCipher, Depends(get_cipher)],
) -> LoginResponse:
    user = authenticate(db, cipher, body.email, body.password)
    token, expires_at = create_session(db, user["_id"])
    return LoginResponse(access_token=token, expires_at=expires_at, user=to_user_out(cipher, user))


@router.get(
    "/me",
    response_model=UserOut,
    summary="Utilizador da sessão",
    responses=problem_responses(401, 503),
)
def me(user: CurrentUser) -> UserOut:
    return user


@router.post(
    "/logout",
    status_code=204,
    summary="Terminar sessão",
    responses=problem_responses(401, 503),
)
def logout(
    _user: CurrentUser,
    token: Annotated[str, Depends(bearer_token)],
    db: Annotated[Database, Depends(get_database)],
) -> Response:
    delete_session(db, token)
    return Response(status_code=204)
