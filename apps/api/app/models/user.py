"""Utilizadores: `POST /api/v1/users` (criar conta)."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from app.security.passwords import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LEVEL, password_level

_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


class UserCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_by_name=True, validate_by_alias=True, serialize_by_alias=True
    )

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]
    password: Annotated[str, Field(max_length=MAX_PASSWORD_LENGTH)]
    password_confirm: str = Field(alias="passwordConfirm")

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        if not _EMAIL.fullmatch(value):
            raise ValueError("email inválido")
        return value.lower()

    @field_validator("password")
    @classmethod
    def _strong_password(cls, value: str) -> str:
        if password_level(value) < MIN_PASSWORD_LEVEL:
            raise ValueError(
                "password demasiado fraca (mínimo 8 caracteres com letras, números e símbolos, "
                "ou 12 caracteres)"
            )
        return value

    @field_validator("password_confirm")
    @classmethod
    def _same_password(cls, value: str, info: ValidationInfo) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("as passwords não coincidem")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, serialize_by_alias=True
    )

    id: str
    name: str
    email: str
    created_at: datetime = Field(alias="createdAt")
