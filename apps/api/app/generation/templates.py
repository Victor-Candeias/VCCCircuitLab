"""Geradores de circuitos por template (E3-01): série, paralelo, divisor de tensão e
interruptor.

Cada gerador recebe parâmetros validados (`app.generation.params`) e devolve um
`CircuitDocument` canónico, pronto a validar/simular (`app.circuit.validate`,
`app.solver.mna`) ou a importar no editor. Não há execução de código fornecido pelo
utilizador: os templates são funções Python fixas e só os parâmetros variam (ver
`Docs/arquitetura_simulador_circuitos.md` §3.1, §6.1).

O layout (posições) é propositadamente simples — uma grelha linear — e serve só para que o
documento gerado seja imediatamente legível; o algoritmo de layout da E3-03 substitui estas
coordenadas.
"""

from app.generation.params import (
    ParallelDcParams,
    SeriesDcParams,
    SwitchCircuitParams,
    VoltageDividerParams,
)
from app.models.circuit import CircuitDocument, Component, Point, Wire

_TOP_Y = 120.0
_BOTTOM_Y = 320.0
_SOURCE_X = 80.0
_STEP_X = 160.0


def _resistor(rid: str, x: float, y: float, resistance_ohm: float) -> Component:
    return Component(
        id=rid,
        type="resistor",
        position=Point(x=x, y=y),
        rotation=0,
        properties={"resistanceOhm": resistance_ohm},
        pins=["a", "b"],
    )


def _source(voltage_v: float) -> Component:
    return Component(
        id="V1",
        type="dc_voltage_source",
        position=Point(x=_SOURCE_X, y=(_TOP_Y + _BOTTOM_Y) / 2),
        rotation=90,
        properties={"voltageV": voltage_v},
        pins=["positive", "negative"],
    )


def _ground(x: float) -> Component:
    return Component(
        id="GND1",
        type="ground",
        position=Point(x=x, y=_BOTTOM_Y + 80),
        rotation=0,
        properties={},
        pins=["gnd"],
    )


def _wire(wid: str, source: str, target: str) -> Wire:
    return Wire(id=wid, from_=source, to=target, waypoints=[])


def _document(
    template: str, name: str, components: list[Component], wires: list[Wire]
) -> CircuitDocument:
    return CircuitDocument(
        schema_version="1.0",
        id=f"generated-{template}",
        name=name,
        units="SI",
        components=components,
        wires=wires,
    )


def _series_chain(
    template: str, name: str, voltage_v: float, resistors_ohm: list[float]
) -> CircuitDocument:
    """Fonte e `R1..Rn` num único laço em série, com terra em `V1.negative`."""
    resistors = [
        _resistor(f"R{i}", _SOURCE_X + _STEP_X * i, _TOP_Y, value)
        for i, value in enumerate(resistors_ohm, start=1)
    ]
    components = [_source(voltage_v), *resistors, _ground(_SOURCE_X)]

    wires = [_wire("W1", "V1.positive", resistors[0].terminal("a"))]
    for i in range(len(resistors) - 1):
        wires.append(_wire(f"W{i + 2}", resistors[i].terminal("b"), resistors[i + 1].terminal("a")))
    wires.append(_wire(f"W{len(resistors) + 1}", resistors[-1].terminal("b"), "V1.negative"))
    wires.append(_wire(f"W{len(resistors) + 2}", "GND1.gnd", "V1.negative"))

    return _document(template, name, components, wires)


def build_series_dc(params: SeriesDcParams) -> CircuitDocument:
    """`series_dc`: `V1` e `R1..Rn` em série (ver `arquitetura_simulador_circuitos.md` §6.2)."""
    return _series_chain("series_dc", "Circuito em série", params.voltage_v, params.resistors_ohm)


def build_voltage_divider(params: VoltageDividerParams) -> CircuitDocument:
    """`voltage_divider`: mesma topologia de `series_dc`; cada junção interna é uma saída."""
    return _series_chain(
        "voltage_divider", "Divisor de tensão", params.voltage_v, params.resistors_ohm
    )


def build_parallel_dc(params: ParallelDcParams) -> CircuitDocument:
    """`parallel_dc`: `V1` e `R1..Rn` em paralelo, cada um ligado diretamente à fonte."""
    resistors = [
        _resistor(f"R{i}", _SOURCE_X + _STEP_X * i, _TOP_Y + (i - 1) * 80.0, value)
        for i, value in enumerate(params.resistors_ohm, start=1)
    ]
    components = [_source(params.voltage_v), *resistors, _ground(_SOURCE_X)]

    wires = []
    for i, r in enumerate(resistors, start=1):
        wires.append(_wire(f"W{2 * i - 1}", "V1.positive", r.terminal("a")))
        wires.append(_wire(f"W{2 * i}", r.terminal("b"), "V1.negative"))
    wires.append(_wire(f"W{2 * len(resistors) + 1}", "GND1.gnd", "V1.negative"))

    return _document("parallel_dc", "Circuito em paralelo", components, wires)


def build_switch_circuit(params: SwitchCircuitParams) -> CircuitDocument:
    """`switch_circuit`: `V1` → `S1` → `R1` em série, com terra em `V1.negative`."""
    switch = Component(
        id="S1",
        type="switch",
        position=Point(x=_SOURCE_X + _STEP_X, y=_TOP_Y),
        rotation=0,
        properties={"closed": params.closed},
        pins=["a", "b"],
    )
    load = _resistor("R1", _SOURCE_X + 2 * _STEP_X, _TOP_Y, params.load_ohm)
    components = [_source(params.voltage_v), switch, load, _ground(_SOURCE_X)]
    wires = [
        _wire("W1", "V1.positive", switch.terminal("a")),
        _wire("W2", switch.terminal("b"), load.terminal("a")),
        _wire("W3", load.terminal("b"), "V1.negative"),
        _wire("W4", "GND1.gnd", "V1.negative"),
    ]
    return _document("switch_circuit", "Circuito com interruptor", components, wires)
