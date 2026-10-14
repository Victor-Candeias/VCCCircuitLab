"""Ligação ao MongoDB, configurada por variáveis de ambiente (ver `.env.example`)."""

import os
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from app.db.errors import DatabaseUnavailableError

#: Tempo máximo para encontrar o servidor, em milissegundos.
SERVER_SELECTION_TIMEOUT_MS = 3000


def _setting(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise DatabaseUnavailableError(f"Variável de ambiente {name} em falta.")
    return value


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Cliente único do processo (o `MongoClient` já gere um pool de ligações)."""
    load_dotenv(find_dotenv(), override=False)
    try:
        port = int(_setting("MONGODB_PORT", "27017"))
    except ValueError as error:
        raise DatabaseUnavailableError("MONGODB_PORT tem de ser um número.") from error
    return MongoClient(
        host=_setting("MONGODB_HOST", "127.0.0.1"),
        port=port,
        username=_setting("MONGODB_USERNAME"),
        password=_setting("MONGODB_PASSWORD"),
        authSource=_setting("MONGODB_AUTH_SOURCE", _setting("MONGODB_DATABASE")),
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        tz_aware=True,
    )


def get_database() -> Database:
    client = get_client()
    return client[_setting("MONGODB_DATABASE")]


def close_client() -> None:
    if get_client.cache_info().currsize:
        get_client().close()
        get_client.cache_clear()
