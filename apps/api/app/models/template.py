"""Modelos da coleção `templates` (F2-10): CRUD de definições de componentes, restrito a
administradores (ver `app/auth/dependencies.py:require_admin` e `app/routes/templates.py`).
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.models.component import ComponentFields


class TemplateCreate(ComponentFields):
    """Corpo de `POST /api/v1/templates` e `PUT /api/v1/templates/{id}`."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TemplateOut(ComponentFields):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    #: Email do administrador que criou o template (ver `E5-10`).
    created_by: str = Field(alias="createdBy")
