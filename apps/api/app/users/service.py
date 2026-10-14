"""Criação de utilizadores na collection `users`.

Documento gravado: `name` e `email` encriptados, `emailIndex` (HMAC do email normalizado, com
índice único) e `passwordHash` (scrypt). Nada em claro além de `createdAt`.
"""

from datetime import UTC, datetime

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.collections import database_errors, insert_one
from app.models.user import UserCreate, UserOut
from app.security.crypto import FieldCipher
from app.security.passwords import hash_password
from app.users.errors import EmailAlreadyRegisteredError

COLLECTION = "users"


def create_user(db: Database, cipher: FieldCipher, data: UserCreate) -> UserOut:
    created_at = datetime.now(UTC).replace(microsecond=0)
    document = {
        "name": cipher.encrypt(data.name),
        "email": cipher.encrypt(data.email),
        "emailIndex": cipher.blind_index(data.email),
        "passwordHash": hash_password(data.password),
        "createdAt": created_at,
    }
    with database_errors():
        db[COLLECTION].create_index("emailIndex", unique=True)
        try:
            user_id = insert_one(db, COLLECTION, document)
        except DuplicateKeyError as error:
            raise EmailAlreadyRegisteredError from error
    return UserOut(id=user_id, name=data.name, email=data.email, created_at=created_at)
