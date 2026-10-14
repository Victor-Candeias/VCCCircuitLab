"""Utilizadores: `POST /api/v1/users`."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.db.mongo import get_database
from app.models.user import UserCreate, UserOut
from app.problems import problem_responses
from app.security.crypto import FieldCipher, get_cipher
from app.users.service import create_user

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post(
    "",
    status_code=201,
    response_model=UserOut,
    summary="Criar utilizador",
    responses=problem_responses(409, 422, 503),
)
def create(
    body: UserCreate,
    db: Annotated[Database, Depends(get_database)],
    cipher: Annotated[FieldCipher, Depends(get_cipher)],
) -> UserOut:
    return create_user(db, cipher, body)
