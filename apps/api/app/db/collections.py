"""CRUD genérico sobre collections do MongoDB (criar, ler, alterar e apagar).

Não está exposto por HTTP: é para ser usado pelo código do backend. As falhas de ligação ou de
permissões são convertidas em `DatabaseUnavailableError`.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.db.errors import DatabaseUnavailableError

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

Document = dict[str, Any]


@contextmanager
def database_errors() -> Iterator[None]:
    """Converte erros do driver em `DatabaseUnavailableError` (chaves duplicadas passam)."""
    try:
        yield
    except DuplicateKeyError:
        raise
    except PyMongoError as error:
        raise DatabaseUnavailableError("A base de dados não está disponível.") from error


def _collection(db: Database, name: str):
    if not _NAME.fullmatch(name):
        raise ValueError(f"Nome de collection inválido: {name!r}.")
    return db[name]


def create_collection(db: Database, name: str) -> None:
    _collection(db, name)
    with database_errors():
        if name not in db.list_collection_names():
            db.create_collection(name)


def drop_collection(db: Database, name: str) -> None:
    _collection(db, name)
    with database_errors():
        db.drop_collection(name)


def list_collections(db: Database) -> list[str]:
    with database_errors():
        return sorted(db.list_collection_names())


def insert_one(db: Database, name: str, document: Mapping[str, Any]) -> str:
    """Insere um documento e devolve o `_id` como texto."""
    with database_errors():
        return str(_collection(db, name).insert_one(dict(document)).inserted_id)


def insert_many(db: Database, name: str, documents: Sequence[Mapping[str, Any]]) -> list[str]:
    if not documents:
        return []
    with database_errors():
        result = _collection(db, name).insert_many([dict(d) for d in documents])
        return [str(i) for i in result.inserted_ids]


def find(
    db: Database,
    name: str,
    query: Mapping[str, Any] | None = None,
    *,
    limit: int = 100,
) -> list[Document]:
    with database_errors():
        return list(_collection(db, name).find(dict(query or {})).limit(limit))


def find_one(db: Database, name: str, query: Mapping[str, Any]) -> Document | None:
    with database_errors():
        return _collection(db, name).find_one(dict(query))


def update_many(
    db: Database, name: str, query: Mapping[str, Any], changes: Mapping[str, Any]
) -> int:
    """Faz `$set` de `changes` nos documentos que cumprem `query`; devolve quantos mudaram."""
    with database_errors():
        result = _collection(db, name).update_many(dict(query), {"$set": dict(changes)})
        return result.modified_count


def delete_many(db: Database, name: str, query: Mapping[str, Any]) -> int:
    with database_errors():
        return _collection(db, name).delete_many(dict(query)).deleted_count
