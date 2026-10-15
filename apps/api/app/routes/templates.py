"""Templates de componentes: `GET/POST/PUT/DELETE /api/v1/templates` (F2-10).

Leitura disponível a qualquer utilizador autenticado (herdado de `require_user`, ver
`app/main.py`); escrita (criar, atualizar, apagar) exige `role: "ADMIN"` (`CurrentAdmin`,
ver E5-10).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.auth.dependencies import CurrentAdmin
from app.component_templates.service import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)
from app.db.mongo import get_database
from app.models.template import TemplateCreate, TemplateOut
from app.problems import problem_responses

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

_Db = Annotated[Database, Depends(get_database)]


@router.get(
    "",
    response_model=list[TemplateOut],
    response_model_by_alias=True,
    summary="Listar templates de componentes",
)
def list_all(db: _Db) -> list[TemplateOut]:
    return list_templates(db)


@router.get(
    "/{template_id}",
    response_model=TemplateOut,
    response_model_by_alias=True,
    responses=problem_responses(404),
    summary="Obter um template de componente",
)
def get_one(template_id: str, db: _Db) -> TemplateOut:
    return get_template(db, template_id)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TemplateOut,
    response_model_by_alias=True,
    responses=problem_responses(403, 409, 422),
    summary="Criar um template de componente (admin)",
)
def create(body: TemplateCreate, admin: CurrentAdmin, db: _Db) -> TemplateOut:
    return create_template(db, body, admin.email)


@router.put(
    "/{template_id}",
    response_model=TemplateOut,
    response_model_by_alias=True,
    responses=problem_responses(403, 404, 409, 422),
    summary="Atualizar um template de componente (admin)",
)
def update(template_id: str, body: TemplateCreate, admin: CurrentAdmin, db: _Db) -> TemplateOut:
    return update_template(db, template_id, body)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(403, 404),
    summary="Apagar um template de componente (admin)",
)
def delete(template_id: str, admin: CurrentAdmin, db: _Db) -> None:
    delete_template(db, template_id)
