"""Projetos guardados na conta (F2-09), na collection `projects`.

Documento: `name` (cópia de `circuit.name`, para listar sem ler o circuito), `circuit` (documento
canónico), `ownerId`, `shares` (`[{userId, role}]`), `version` (começa em 1 e sobe a cada
gravação do circuito), `createdAt`, `updatedAt` e `updatedById`.

Acesso: o dono pode tudo; um convidado `editor` lê e grava o circuito; um `viewer` só lê. Quem
não tem acesso recebe `ProjectNotFoundError` (404), para não revelar que o projeto existe.

Colaboração: `update_project` só grava se a `version` enviada for a atual (controlo otimista);
caso contrário lança `ProjectVersionConflictError` (409) e o cliente tem de reabrir o projeto.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.database import Database

from app.auth.errors import NotAuthorizedError
from app.auth.service import normalize_email
from app.db.collections import database_errors
from app.models.circuit import CircuitDocument
from app.models.project import (
    MAX_SHARES,
    ProjectAccess,
    ProjectCreate,
    ProjectOut,
    ProjectShare,
    ProjectSummary,
    ProjectUpdate,
    ProjectUser,
    ShareRequest,
)
from app.models.user import UserOut
from app.projects.errors import (
    InvalidShareError,
    ProjectNotFoundError,
    ProjectVersionConflictError,
    ShareUserNotFoundError,
)
from app.security.crypto import FieldCipher
from app.users.service import COLLECTION as USERS

COLLECTION = "projects"

#: Número máximo de projetos devolvidos pela listagem (os mais recentes primeiro).
MAX_LISTED = 500

Document = dict[str, Any]


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as error:
        raise ProjectNotFoundError(value) from error


def _access(document: Document, user_id: ObjectId) -> ProjectAccess | None:
    if document["ownerId"] == user_id:
        return "owner"
    for share in document.get("shares", []):
        if share["userId"] == user_id:
            return share["role"]
    return None


def _load(db: Database, project_id: str, user: UserOut) -> tuple[Document, ProjectAccess]:
    """Projeto e acesso do utilizador; sem acesso é como se não existisse."""
    with database_errors():
        document = db[COLLECTION].find_one({"_id": _object_id(project_id)})
    access = _access(document, ObjectId(user.id)) if document else None
    if document is None or access is None:
        raise ProjectNotFoundError(project_id)
    return document, access


def _require_owner(access: ProjectAccess) -> None:
    if access != "owner":
        raise NotAuthorizedError


def _users(
    db: Database, cipher: FieldCipher, ids: Iterable[ObjectId]
) -> dict[ObjectId, ProjectUser]:
    """Nome e email (desencriptados) dos utilizadores; contas apagadas ficam identificadas."""
    wanted = set(ids)
    with database_errors():
        found = list(db[USERS].find({"_id": {"$in": list(wanted)}}, {"name": 1, "email": 1}))
    users = {
        u["_id"]: ProjectUser(
            id=str(u["_id"]), name=cipher.decrypt(u["name"]), email=cipher.decrypt(u["email"])
        )
        for u in found
    }
    for missing in wanted - users.keys():
        users[missing] = ProjectUser(id=str(missing), name="(conta removida)", email="")
    return users


def _related_ids(document: Document) -> list[ObjectId]:
    ids = [document["ownerId"], document["updatedById"]]
    return ids + [s["userId"] for s in document.get("shares", [])]


def _summary_fields(
    document: Document, access: ProjectAccess, users: dict[ObjectId, ProjectUser]
) -> dict[str, Any]:
    return {
        "id": str(document["_id"]),
        "name": document["name"],
        "owner": users[document["ownerId"]],
        "access": access,
        "version": document["version"],
        "created_at": document["createdAt"],
        "updated_at": document["updatedAt"],
        "updated_by": users[document["updatedById"]],
    }


def _to_out(
    db: Database, cipher: FieldCipher, document: Document, access: ProjectAccess
) -> ProjectOut:
    users = _users(db, cipher, _related_ids(document))
    shares = [
        ProjectShare(user=users[s["userId"]], role=s["role"]) for s in document.get("shares", [])
    ]
    return ProjectOut(
        **_summary_fields(document, access, users),
        circuit=CircuitDocument.model_validate(document["circuit"]),
        shares=shares,
    )


def _circuit_fields(circuit: CircuitDocument) -> dict[str, Any]:
    return {"name": circuit.name, "circuit": circuit.to_json_dict()}


def list_projects(db: Database, cipher: FieldCipher, user: UserOut) -> list[ProjectSummary]:
    """Projetos do utilizador e partilhados com ele, do mais recente para o mais antigo."""
    user_id = ObjectId(user.id)
    with database_errors():
        documents = list(
            db[COLLECTION]
            .find({"$or": [{"ownerId": user_id}, {"shares.userId": user_id}]}, {"circuit": 0})
            .sort("updatedAt", DESCENDING)
            .limit(MAX_LISTED)
        )
    users = _users(db, cipher, (i for d in documents for i in _related_ids(d)))
    summaries = []
    for document in documents:
        access = _access(document, user_id)
        if access is not None:
            summaries.append(ProjectSummary(**_summary_fields(document, access, users)))
    return summaries


def create_project(
    db: Database, cipher: FieldCipher, user: UserOut, data: ProjectCreate
) -> ProjectOut:
    now = _now()
    user_id = ObjectId(user.id)
    document: Document = _circuit_fields(data.circuit) | {
        "ownerId": user_id,
        "shares": [],
        "version": 1,
        "createdAt": now,
        "updatedAt": now,
        "updatedById": user_id,
    }
    with database_errors():
        projects = db[COLLECTION]
        projects.create_index("ownerId")
        projects.create_index("shares.userId")
        document["_id"] = projects.insert_one(document).inserted_id
    return _to_out(db, cipher, document, "owner")


def get_project(db: Database, cipher: FieldCipher, user: UserOut, project_id: str) -> ProjectOut:
    document, access = _load(db, project_id, user)
    return _to_out(db, cipher, document, access)


def update_project(
    db: Database, cipher: FieldCipher, user: UserOut, project_id: str, data: ProjectUpdate
) -> ProjectOut:
    """Grava o circuito se `data.version` for a atual; a versão sobe uma unidade."""
    document, access = _load(db, project_id, user)
    if access == "viewer":
        raise NotAuthorizedError
    changes = _circuit_fields(data.circuit) | {
        "updatedAt": _now(),
        "updatedById": ObjectId(user.id),
    }
    with database_errors():
        result = db[COLLECTION].update_one(
            {"_id": document["_id"], "version": data.version},
            {"$set": changes, "$inc": {"version": 1}},
        )
    if result.matched_count == 0:
        current, _ = _load(db, project_id, user)
        raise ProjectVersionConflictError(current["version"])
    return get_project(db, cipher, user, project_id)


def delete_project(db: Database, user: UserOut, project_id: str) -> None:
    document, access = _load(db, project_id, user)
    _require_owner(access)
    with database_errors():
        db[COLLECTION].delete_one({"_id": document["_id"]})


def share_project(
    db: Database, cipher: FieldCipher, user: UserOut, project_id: str, data: ShareRequest
) -> ProjectOut:
    """Partilha com a conta do email indicado, ou altera a permissão se já estiver partilhado."""
    document, access = _load(db, project_id, user)
    _require_owner(access)
    with database_errors():
        target = db[USERS].find_one(
            {"emailIndex": cipher.blind_index(normalize_email(data.email))}, {"_id": 1}
        )
    if target is None:
        raise ShareUserNotFoundError
    target_id = target["_id"]
    if target_id == document["ownerId"]:
        raise InvalidShareError("O dono já tem acesso total ao projeto.")
    shares = document.get("shares", [])
    with database_errors():
        if any(s["userId"] == target_id for s in shares):
            db[COLLECTION].update_one(
                {"_id": document["_id"], "shares.userId": target_id},
                {"$set": {"shares.$.role": data.role}},
            )
        elif len(shares) >= MAX_SHARES:
            raise InvalidShareError(f"Um projeto pode ser partilhado com até {MAX_SHARES} contas.")
        else:
            db[COLLECTION].update_one(
                {"_id": document["_id"]},
                {"$push": {"shares": {"userId": target_id, "role": data.role}}},
            )
    return get_project(db, cipher, user, project_id)


def remove_share(db: Database, user: UserOut, project_id: str, user_id: str) -> None:
    """O dono remove um convidado; um convidado pode remover-se a si próprio (sair)."""
    document, access = _load(db, project_id, user)
    if access != "owner" and user_id != user.id:
        raise NotAuthorizedError
    try:
        target_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        return
    with database_errors():
        db[COLLECTION].update_one(
            {"_id": document["_id"]}, {"$pull": {"shares": {"userId": target_id}}}
        )
