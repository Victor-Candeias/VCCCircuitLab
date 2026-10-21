"""Projetos na conta, partilha e colaboração: `/api/v1/projects` (F2-09).

Todas as rotas exigem sessão (`require_user`, ver `app/main.py`). O acesso a cada projeto é
verificado em `app/projects/service.py`: sem acesso → 404; acesso insuficiente → 403.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pymongo.database import Database

from app.auth.dependencies import CurrentUser
from app.db.mongo import get_database
from app.models.project import (
    ProjectCreate,
    ProjectOut,
    ProjectSummary,
    ProjectUpdate,
    ShareRequest,
)
from app.problems import problem_responses
from app.projects import service
from app.security.crypto import FieldCipher, get_cipher

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

_Db = Annotated[Database, Depends(get_database)]
_Cipher = Annotated[FieldCipher, Depends(get_cipher)]


@router.get(
    "",
    response_model=list[ProjectSummary],
    summary="Listar os projetos do utilizador e os partilhados com ele",
    responses=problem_responses(503),
)
def list_all(user: CurrentUser, db: _Db, cipher: _Cipher) -> list[ProjectSummary]:
    return service.list_projects(db, cipher, user)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectOut,
    summary="Guardar um circuito como novo projeto na conta",
    responses=problem_responses(422, 503),
)
def create(body: ProjectCreate, user: CurrentUser, db: _Db, cipher: _Cipher) -> ProjectOut:
    return service.create_project(db, cipher, user, body)


@router.get(
    "/{project_id}",
    response_model=ProjectOut,
    summary="Abrir um projeto",
    responses=problem_responses(404, 503),
)
def get_one(project_id: str, user: CurrentUser, db: _Db, cipher: _Cipher) -> ProjectOut:
    return service.get_project(db, cipher, user, project_id)


@router.put(
    "/{project_id}",
    response_model=ProjectOut,
    summary="Gravar o circuito de um projeto (dono ou editor)",
    responses=problem_responses(403, 404, 409, 422, 503),
)
def update(
    project_id: str, body: ProjectUpdate, user: CurrentUser, db: _Db, cipher: _Cipher
) -> ProjectOut:
    return service.update_project(db, cipher, user, project_id, body)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Apagar um projeto (dono)",
    responses=problem_responses(403, 404, 503),
)
def delete(project_id: str, user: CurrentUser, db: _Db) -> Response:
    service.delete_project(db, user, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{project_id}/shares",
    response_model=ProjectOut,
    summary="Partilhar um projeto com outra conta, ou mudar a permissão (dono)",
    responses=problem_responses(403, 404, 422, 503),
)
def share(
    project_id: str, body: ShareRequest, user: CurrentUser, db: _Db, cipher: _Cipher
) -> ProjectOut:
    return service.share_project(db, cipher, user, project_id, body)


@router.delete(
    "/{project_id}/shares/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover um convidado (dono) ou sair da partilha (o próprio convidado)",
    responses=problem_responses(403, 404, 503),
)
def unshare(project_id: str, user_id: str, user: CurrentUser, db: _Db) -> Response:
    service.remove_share(db, user, project_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
