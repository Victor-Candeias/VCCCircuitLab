"""Leitura de um rawfile ASCII do ngspice (`write` com `filetype=ascii`).

Serve o ponto de funcionamento (`op`, um ponto) e a análise transitória (`tran`, vários pontos,
com a variável `time` como escala). Consoante a versão, as variáveis chamam-se `v(n1)`/`i(v2)`
ou `n1`/`v2#branch`; as correntes de dispositivos guardadas com `save @c1[i]` chamam-se
`@c1[i]`.
"""

import re
from dataclasses import dataclass, field

from app.spice.errors import SimulationEngineError

_VOLTAGE = re.compile(r"v\((?P<name>[^)]+)\)")
_CURRENT = re.compile(r"i\((?P<name>[^)]+)\)|(?P<branch>.+)#branch|@(?P<device>[^\[]+)\[i\]")


@dataclass(frozen=True)
class RawResult:
    voltages: dict[str, float] = field(default_factory=dict)
    """Nó (minúsculas) → tensão no primeiro ponto."""
    currents: dict[str, float] = field(default_factory=dict)
    """Elemento (minúsculas) → corrente de ramo no primeiro ponto."""
    time: list[float] = field(default_factory=list)
    """Instantes (análise transitória); vazio sem variável `time`."""
    voltage_series: dict[str, list[float]] = field(default_factory=dict)
    """Nó (minúsculas) → tensão em cada ponto."""
    current_series: dict[str, list[float]] = field(default_factory=dict)
    """Elemento (minúsculas) → corrente em cada ponto."""


def parse_rawfile(text: str) -> RawResult:
    lines = [line.strip() for line in text.splitlines()]
    lowered = [line.lower() for line in lines]
    if "variables:" not in lowered or "values:" not in lowered:
        raise SimulationEngineError("rawfile sem as secções Variables/Values")
    start, values_at = lowered.index("variables:"), lowered.index("values:")

    variables = [p for line in lines[start + 1 : values_at] if len(p := line.split()) >= 2]
    names = [p[1].lower() for p in variables]
    kinds = [p[2].lower() if len(p) >= 3 else "" for p in variables]
    # Cada ponto: o índice do ponto seguido dos valores pela ordem das variáveis.
    tokens = " ".join(lines[values_at + 1 :]).split()
    width = len(names) + 1
    points = len(tokens) // width
    if not names or points == 0:
        raise SimulationEngineError("rawfile com variáveis ou valores em falta")
    try:
        rows = [[float(t) for t in tokens[p * width + 1 : (p + 1) * width]] for p in range(points)]
    except ValueError:
        raise SimulationEngineError("rawfile com valores não numéricos") from None

    result = RawResult()
    for column, (name, kind) in enumerate(zip(names, kinds, strict=True)):
        series = [row[column] for row in rows]
        if kind == "time" or name == "time":
            result.time.extend(series)
        elif m := _CURRENT.fullmatch(name):
            element = m["name"] or m["branch"] or m["device"]
            result.currents[element] = series[0]
            result.current_series[element] = series
        else:
            node = m["name"] if (m := _VOLTAGE.fullmatch(name)) else name
            result.voltages[node] = series[0]
            result.voltage_series[node] = series
    return result
