"""Geradores de circuitos por template (E3-01): série, paralelo, divisor de tensão e
interruptor.

Cada gerador recebe parâmetros validados (`app.generation.params`) e devolve um
`CircuitDocument` canónico, pronto a validar/simular (`app.circuit.validate`,
`app.solver.mna`) ou a importar no editor. Não há execução de código fornecido pelo
utilizador: os templates são funções Python fixas e só os parâmetros variam (ver
`Docs/arquitetura_simulador_circuitos.md` §3.1, §6.1).

Os componentes são construídos sem posição definitiva (`_PLACEHOLDER`); quem calcula as
posições finais e os fios (incluindo waypoints ortogonais, quando necessários) é o algoritmo
de layout (`app.generation.layout`, E3-03).
"""

from app.generation.layout import chain_loop, parallel_ladder
from app.generation.params import (
    ParallelDcParams,
    SeriesDcParams,
    SwitchCircuitParams,
    VoltageDividerParams,
)
from app.models.circuit import CircuitDocument, Component, Point

_PLACEHOLDER = Point(x=0, y=0)


def _resistor(rid: str, resistance_ohm: float) -> Component:
    return Component(
        id=rid,
        type="resistor",
        position=_PLACEHOLDER,
        rotation=0,
        properties={"resistanceOhm": resistance_ohm},
        pins=["a", "b"],
    )


def _source(voltage_v: float) -> Component:
    return Component(
        id="V1",
        type="dc_voltage_source",
        position=_PLACEHOLDER,
        rotation=0,
        properties={"voltageV": voltage_v},
        pins=["positive", "negative"],
    )


def _ground() -> Component:
    return Component(
        id="GND1", type="ground", position=_PLACEHOLDER, rotation=0, properties={}, pins=["gnd"]
    )


def _resistor_chain(resistors_ohm: list[float]) -> list[Component]:
    return [_resistor(f"R{i}", value) for i, value in enumerate(resistors_ohm, start=1)]


def build_series_dc(params: SeriesDcParams) -> CircuitDocument:
    """`series_dc`: `V1` e `R1..Rn` em série (ver `arquitetura_simulador_circuitos.md` §6.2)."""
    return chain_loop(
        "series_dc",
        "Circuito em série",
        _source(params.voltage_v),
        _resistor_chain(params.resistors_ohm),
        _ground(),
    )


def build_voltage_divider(params: VoltageDividerParams) -> CircuitDocument:
    """`voltage_divider`: mesma topologia de `series_dc`; cada junção interna é uma saída."""
    return chain_loop(
        "voltage_divider",
        "Divisor de tensão",
        _source(params.voltage_v),
        _resistor_chain(params.resistors_ohm),
        _ground(),
    )


def build_parallel_dc(params: ParallelDcParams) -> CircuitDocument:
    """`parallel_dc`: `V1` e `R1..Rn` em paralelo, cada um ligado diretamente à fonte."""
    return parallel_ladder(
        "parallel_dc",
        "Circuito em paralelo",
        _source(params.voltage_v),
        _resistor_chain(params.resistors_ohm),
        _ground(),
    )


def build_switch_circuit(params: SwitchCircuitParams) -> CircuitDocument:
    """`switch_circuit`: `V1` → `S1` → `R1` em série, com terra em `V1.negative`."""
    switch = Component(
        id="S1",
        type="switch",
        position=_PLACEHOLDER,
        rotation=0,
        properties={"closed": params.closed},
        pins=["a", "b"],
    )
    load = _resistor("R1", params.load_ohm)
    return chain_loop(
        "switch_circuit",
        "Circuito com interruptor",
        _source(params.voltage_v),
        [switch, load],
        _ground(),
    )
