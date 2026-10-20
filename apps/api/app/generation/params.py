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


class StaircaseLightingParams(GenerationParams):
    """`staircase_lighting` (F2-08): iluminação de escada a 230 V com dois comutadores.

    Rede `AC1` → disjuntor `QF1` → comutadores `SC1`/`SC2` (ligados pelos dois condutores de
    retorno) → lâmpada `HR1` → neutro, com o neutro ligado à terra. A lâmpada acende quando
    os dois comutadores estão em posições diferentes (`switch1ToL2 != switch2ToL2`). Os
    limites são os do catálogo (`mains_source`, `mains_lamp`, `circuit_breaker`).
    """

    voltage_v: Annotated[float, Field(gt=0, le=400, allow_inf_nan=False)] = Field(
        default=230, alias="voltageV"
    )
    frequency_hz: Annotated[float, Field(ge=50, le=60, allow_inf_nan=False)] = Field(
        default=50, alias="frequencyHz"
    )
    lamp_power_w: Annotated[float, Field(gt=0, le=5000, allow_inf_nan=False)] = Field(
        default=60, alias="lampPowerW"
    )
    breaker_rated_a: Annotated[float, Field(gt=0, le=125, allow_inf_nan=False)] = Field(
        default=10, alias="breakerRatedA"
    )
    switch1_to_l2: bool = Field(default=False, alias="switch1ToL2")
    switch2_to_l2: bool = Field(default=False, alias="switch2ToL2")
