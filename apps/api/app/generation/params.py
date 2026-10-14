"""Parâmetros validados dos templates de geração (ver `app.generation.templates`).

Os parâmetros usam nomes JSON em camelCase (tal como `CircuitDocument`); são estritos e não
aceitam campos extra, para que pedidos inválidos sejam rejeitados antes de qualquer geração.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class GenerationParams(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", validate_by_name=True, validate_by_alias=True
    )


class SeriesDcParams(GenerationParams):
    """`series_dc`: fonte DC e um ou mais resistores em série, com terra no negativo."""

    voltage_v: PositiveFloat = Field(alias="voltageV")
    resistors_ohm: list[PositiveFloat] = Field(alias="resistorsOhm", min_length=1, max_length=12)


class ParallelDcParams(GenerationParams):
    """`parallel_dc`: fonte DC e um ou mais resistores em paralelo, com terra no negativo."""

    voltage_v: PositiveFloat = Field(alias="voltageV")
    resistors_ohm: list[PositiveFloat] = Field(alias="resistorsOhm", min_length=1, max_length=12)


class VoltageDividerParams(GenerationParams):
    """`voltage_divider`: cadeia de resistores em série entre a fonte e a terra.

    Cada junção entre dois resistores consecutivos é um ponto de saída do divisor (a sua
    tensão é a da rede correspondente); com dois resistores obtém-se o divisor clássico.
    """

    voltage_v: PositiveFloat = Field(alias="voltageV")
    resistors_ohm: list[PositiveFloat] = Field(alias="resistorsOhm", min_length=2, max_length=12)


class SwitchCircuitParams(GenerationParams):
    """`switch_circuit`: fonte, interruptor e resistência de carga em série."""

    voltage_v: PositiveFloat = Field(alias="voltageV")
    load_ohm: PositiveFloat = Field(alias="loadOhm")
    closed: bool = True
