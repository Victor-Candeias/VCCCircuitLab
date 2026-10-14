"""Autenticação por email e password."""

from functools import lru_cache
from typing import Any

from pymongo.database import Database

from app.auth.errors import InvalidCredentialsError
from app.db.collections import find_one
from app.models.user import USER_ROLE, UserOut
from app.security.crypto import FieldCipher
from app.security.passwords import hash_password, verify_password
from app.users.service import COLLECTION as USERS


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password("password-inexistente")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Database, cipher: FieldCipher, email: str, password: str) -> dict[str, Any]:
    """Devolve o documento do utilizador, ou lança `InvalidCredentialsError`."""
    user = find_one(db, USERS, {"emailIndex": cipher.blind_index(normalize_email(email))})
    # Verifica sempre um hash, mesmo sem utilizador, para o tempo de resposta não revelar se o
    # email está registado.
    valid = verify_password(password, user["passwordHash"] if user else _dummy_hash())
    if user is None or not valid:
        raise InvalidCredentialsError
    return user


def to_user_out(cipher: FieldCipher, user: dict[str, Any]) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        name=cipher.decrypt(user["name"]),
        email=cipher.decrypt(user["email"]),
        # Contas anteriores à introdução dos roles não têm o campo.
        role=user.get("role", USER_ROLE),
        created_at=user["createdAt"],
    )
