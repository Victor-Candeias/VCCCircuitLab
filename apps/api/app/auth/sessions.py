"""Sessões de login na collection `sessions`.

O token entregue ao cliente é aleatório (256 bits) e só o seu SHA-256 fica na BD, para que uma
cópia da BD não permita usar sessões. `expiresAt` tem um índice TTL: o MongoDB apaga as sessões
expiradas, e a validação também as recusa enquanto não forem apagadas.
"""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.db.collections import database_errors

COLLECTION = "sessions"

#: Duração de uma sessão (variável de ambiente `SESSION_TTL_HOURS`, por omissão 8 h).
SESSION_TTL = timedelta(hours=float(os.environ.get("SESSION_TTL_HOURS", "8")))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def create_session(db: Database, user_id: ObjectId) -> tuple[str, datetime]:
    """Cria uma sessão e devolve `(token, expiresAt)`; o token não é guardado."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = (now + SESSION_TTL).replace(microsecond=0)
    with database_errors():
        sessions = db[COLLECTION]
        sessions.create_index("tokenHash", unique=True)
        sessions.create_index("expiresAt", expireAfterSeconds=0)
        sessions.insert_one(
            {
                "tokenHash": _token_hash(token),
                "userId": user_id,
                "createdAt": now,
                "expiresAt": expires_at,
            }
        )
    return token, expires_at


def find_session_user(db: Database, token: str) -> dict[str, Any] | None:
    """Utilizador da sessão, ou `None` se o token não existir ou já tiver expirado."""
    with database_errors():
        session = db[COLLECTION].find_one({"tokenHash": _token_hash(token)})
        if session is None or _aware(session["expiresAt"]) <= datetime.now(UTC):
            return None
        return db["users"].find_one({"_id": session["userId"]})


def delete_session(db: Database, token: str) -> None:
    with database_errors():
        db[COLLECTION].delete_one({"tokenHash": _token_hash(token)})
