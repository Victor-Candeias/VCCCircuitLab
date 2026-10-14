"""Registo dos templates de geração disponíveis (nome → parâmetros e função geradora).

Serve de base ao endpoint `POST /api/v1/circuits/generate` (E3-02): a validação dos
parâmetros e a escolha do gerador fazem-se sempre a partir daqui, nunca por execução de texto
ou código fornecido pelo utilizador.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.generation.params import (
    ParallelDcParams,
    SeriesDcParams,
    SwitchCircuitParams,
    VoltageDividerParams,
)
from app.generation.templates import (
    build_parallel_dc,
    build_series_dc,
    build_switch_circuit,
    build_voltage_divider,
)
from app.models.circuit import CircuitDocument


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    title: str
    params_model: type[Any]
    build: Callable[[Any], CircuitDocument]


_SPECS = (
    TemplateSpec("series_dc", "Circuito em série", SeriesDcParams, build_series_dc),
    TemplateSpec("parallel_dc", "Circuito em paralelo", ParallelDcParams, build_parallel_dc),
    TemplateSpec(
        "voltage_divider", "Divisor de tensão", VoltageDividerParams, build_voltage_divider
    ),
    TemplateSpec(
        "switch_circuit", "Circuito com interruptor", SwitchCircuitParams, build_switch_circuit
    ),
)

TEMPLATES: dict[str, TemplateSpec] = {spec.name: spec for spec in _SPECS}


def get_template(name: str) -> TemplateSpec:
    """Devolve o template `name`; lança `KeyError` se for desconhecido."""
    try:
        return TEMPLATES[name]
    except KeyError:
        raise KeyError(f"template de geração desconhecido: {name}") from None
