"""Erros estruturados do domínio do circuito (base das respostas problem+json)."""

from dataclasses import dataclass, field
from enum import StrEnum


class CircuitErrorCode(StrEnum):
    # Normalizador de redes (E2-01)
    UNKNOWN_TERMINAL = "UNKNOWN_TERMINAL"
    UNKNOWN_JUNCTION = "UNKNOWN_JUNCTION"
    NET_INCONSISTENT = "NET_INCONSISTENT"
    # Documento
    DUPLICATE_ID = "DUPLICATE_ID"
    SELF_LOOP_WIRE = "SELF_LOOP_WIRE"
    # Componentes vs catálogo
    UNKNOWN_COMPONENT_TYPE = "UNKNOWN_COMPONENT_TYPE"
    UNSUPPORTED_MODEL = "UNSUPPORTED_MODEL"
    UNKNOWN_PIN = "UNKNOWN_PIN"
    MISSING_PIN = "MISSING_PIN"
    UNKNOWN_PROPERTY = "UNKNOWN_PROPERTY"
    MISSING_PROPERTY = "MISSING_PROPERTY"
    INVALID_PROPERTY_TYPE = "INVALID_PROPERTY_TYPE"
    INVALID_VALUE = "INVALID_VALUE"
    # Topologia
    UNCONNECTED_PIN = "UNCONNECTED_PIN"
    MISSING_GROUND = "MISSING_GROUND"
    FLOATING_NET = "FLOATING_NET"
    VOLTAGE_SOURCE_LOOP = "VOLTAGE_SOURCE_LOOP"
    CURRENT_SOURCE_CUTSET = "CURRENT_SOURCE_CUTSET"
    # Rede 230/400 V e proteções (F2-07)
    UNSUPPORTED_ANALYSIS = "UNSUPPORTED_ANALYSIS"
    MAINS_VOLTAGE = "MAINS_VOLTAGE"
    MISSING_PROTECTION = "MISSING_PROTECTION"
    OVERCURRENT = "OVERCURRENT"
    RESIDUAL_CURRENT = "RESIDUAL_CURRENT"
    # Solver
    SINGULAR_MATRIX = "SINGULAR_MATRIX"
    ILL_CONDITIONED_MATRIX = "ILL_CONDITIONED_MATRIX"
    NO_CONVERGENCE = "NO_CONVERGENCE"


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
