"""Criação de utilizadores na collection `users`.

Documento gravado: `name` e `email` encriptados, `emailIndex` (HMAC do email normalizado, com
índice único), `passwordHash` (scrypt) e `role` (`USER` no registo; `ADMIN` só pelo seed de
`app/users/seed_admin.py`). Nada em claro além de `role` e `createdAt`.
"""

from datetime import UTC, datetime

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.collections import database_errors, find_one, insert_one, update_many
from app.models.user import ADMIN_ROLE, USER_ROLE, Role, UserCreate, UserOut
from app.security.crypto import FieldCipher
from app.security.passwords import hash_password
from app.users.errors import EmailAlreadyRegisteredError

COLLECTION = "users"


def _document(
    cipher: FieldCipher, name: str, email: str, password: str, role: Role, created_at: datetime
) -> dict[str, object]:
    return {
        "name": cipher.encrypt(name),
        "email": cipher.encrypt(email),
        "emailIndex": cipher.blind_index(email),
        "passwordHash": hash_password(password),
        "role": role,
        "createdAt": created_at,
    }


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def create_user(db: Database, cipher: FieldCipher, data: UserCreate) -> UserOut:
    created_at = _now()
    document = _document(cipher, data.name, data.email, data.password, USER_ROLE, created_at)
    with database_errors():
        db[COLLECTION].create_index("emailIndex", unique=True)
        try:
            user_id = insert_one(db, COLLECTION, document)
        except DuplicateKeyError as error:
            raise EmailAlreadyRegisteredError from error
    return UserOut(
        id=user_id, name=data.name, email=data.email, role=USER_ROLE, created_at=created_at
    )


def ensure_admin(db: Database, cipher: FieldCipher, name: str, email: str, password: str) -> str:
    """Cria o administrador, ou repõe `role` e password se o email já existir. Devolve o `_id`.

    Não passa pela política de qualidade da password do registo: é chamado pelo operador
    (`app/users/seed_admin.py`), nunca por HTTP.
    """
    email = email.strip().lower()
    with database_errors():
        db[COLLECTION].create_index("emailIndex", unique=True)
    existing = find_one(db, COLLECTION, {"emailIndex": cipher.blind_index(email)})
    if existing is None:
        document = _document(cipher, name, email, password, ADMIN_ROLE, _now())
        return insert_one(db, COLLECTION, document)
    update_many(
        db,
        COLLECTION,
        {"_id": existing["_id"]},
        {"role": ADMIN_ROLE, "passwordHash": hash_password(password)},
    )
    return str(existing["_id"])
