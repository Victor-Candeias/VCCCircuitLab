"""CRUD da coleção `templates` (F2-10): definições de componentes geridas por administradores.

Documentos: os campos de `ComponentFields` (ver `app/models/component.py`) mais `createdAt`,
`updatedAt` e `createdBy` (email do administrador). `type` tem um índice único: não pode haver
dois templates para o mesmo tipo de componente.

Leitura exposta a qualquer utilizador autenticado em `GET /api/v1/templates`; escrita
(`POST`/`PUT`/`DELETE`) exige `CurrentAdmin` (ver `app/auth/dependencies.py`, E5-10).
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.component_templates.errors import DuplicateTemplateTypeError, TemplateNotFoundError
from app.db.collections import database_errors, delete_many, find, find_one, insert_one, update_many
from app.models.template import TemplateCreate, TemplateOut

COLLECTION = "templates"


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _object_id(template_id: str) -> ObjectId:
    try:
        return ObjectId(template_id)
    except InvalidId as error:
        raise TemplateNotFoundError(template_id) from error


def _to_out(document: dict[str, Any]) -> TemplateOut:
    return TemplateOut.model_validate({**document, "id": str(document["_id"])})


def _ensure_type_index(db: Database) -> None:
    with database_errors():
        db[COLLECTION].create_index("type", unique=True)


def list_templates(db: Database) -> list[TemplateOut]:
    return [_to_out(d) for d in find(db, COLLECTION, limit=1000)]


def get_template(db: Database, template_id: str) -> TemplateOut:
    document = find_one(db, COLLECTION, {"_id": _object_id(template_id)})
    if document is None:
        raise TemplateNotFoundError(template_id)
    return _to_out(document)


def create_template(db: Database, data: TemplateCreate, created_by: str) -> TemplateOut:
    _ensure_type_index(db)
    now = _now()
    document = data.model_dump(by_alias=True) | {
        "createdAt": now,
        "updatedAt": now,
        "createdBy": created_by,
    }
    try:
        template_id = insert_one(db, COLLECTION, document)
    except DuplicateKeyError as error:
        raise DuplicateTemplateTypeError(data.type) from error
    return _to_out({**document, "_id": ObjectId(template_id)})


def update_template(db: Database, template_id: str, data: TemplateCreate) -> TemplateOut:
    object_id = _object_id(template_id)
    _ensure_type_index(db)
    changes = data.model_dump(by_alias=True) | {"updatedAt": _now()}
    try:
        changed = update_many(db, COLLECTION, {"_id": object_id}, changes)
    except DuplicateKeyError as error:
        raise DuplicateTemplateTypeError(data.type) from error
    if not changed:
        raise TemplateNotFoundError(template_id)
    return get_template(db, template_id)


def delete_template(db: Database, template_id: str) -> None:
    object_id = _object_id(template_id)
    if not delete_many(db, COLLECTION, {"_id": object_id}):
        raise TemplateNotFoundError(template_id)
