"""Projetos guardados na conta (F2-09): circuito, dono, partilhas e versão."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.circuit import CircuitDocument

#: Permissão de um convidado: `viewer` só lê; `editor` também grava o circuito.
ShareRole = Literal["viewer", "editor"]
#: Acesso do utilizador da sessão a um projeto (`owner` pode ainda apagar e partilhar).
ProjectAccess = Literal["owner", "editor", "viewer"]

#: Número máximo de convidados por projeto.
MAX_SHARES = 50


class _ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_by_name=True, validate_by_alias=True, serialize_by_alias=True
    )


class ProjectCreate(_ApiModel):
    """Corpo de `POST /api/v1/projects`."""

    circuit: CircuitDocument


class ProjectUpdate(_ApiModel):
    """Corpo de `PUT /api/v1/projects/{id}`: `version` é a versão lida antes de editar."""

    circuit: CircuitDocument
    version: Annotated[int, Field(ge=1)]


class ShareRequest(_ApiModel):
    """Corpo de `PUT /api/v1/projects/{id}/shares` (cria ou altera a partilha)."""

    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    role: ShareRole


class ProjectUser(_ApiModel):
    id: str
    name: str
    email: str


class ProjectShare(_ApiModel):
    user: ProjectUser
    role: ShareRole


class ProjectSummary(_ApiModel):
    id: str
    name: str
    owner: ProjectUser
    access: ProjectAccess
    version: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    #: Quem gravou a última versão (dono ou `editor`).
    updated_by: ProjectUser = Field(alias="updatedBy")


class ProjectOut(ProjectSummary):
    circuit: CircuitDocument
    shares: list[ProjectShare]
