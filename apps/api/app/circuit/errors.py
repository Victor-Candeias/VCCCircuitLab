"""Erros estruturados do domínio do circuito (base das respostas problem+json)."""

from dataclasses import dataclass, field
from enum import StrEnum


class CircuitErrorCode(StrEnum):
    UNKNOWN_TERMINAL = "UNKNOWN_TERMINAL"
    UNKNOWN_JUNCTION = "UNKNOWN_JUNCTION"
    NET_INCONSISTENT = "NET_INCONSISTENT"


@dataclass(frozen=True)
class CircuitError:
    code: CircuitErrorCode
    message: str
    #: IDs/terminais envolvidos (ex.: `["W3", "R9.a"]`), para o editor poder destacá-los.
    refs: tuple[str, ...] = field(default_factory=tuple)


class CircuitValidationError(Exception):
    """Um ou mais erros que impedem processar o circuito."""

    def __init__(self, errors: list[CircuitError]) -> None:
        if not errors:
            raise ValueError("CircuitValidationError exige pelo menos um erro")
        self.errors = errors
        super().__init__("; ".join(f"{e.code}: {e.message}" for e in errors))
