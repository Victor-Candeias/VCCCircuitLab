"""Leitura de um rawfile ASCII do ngspice (`write` com `filetype=ascii`) de um único ponto
(análise `op`). Consoante a versão, as variáveis chamam-se `v(n1)`/`i(v2)` ou `n1`/`v2#branch`.
"""

import re
from dataclasses import dataclass, field

from app.spice.errors import SimulationEngineError

_VOLTAGE = re.compile(r"v\((?P<name>[^)]+)\)")
_CURRENT = re.compile(r"i\((?P<name>[^)]+)\)|(?P<branch>.+)#branch")


@dataclass(frozen=True)
class RawResult:
    voltages: dict[str, float] = field(default_factory=dict)
    """Nó (minúsculas) → tensão."""
    currents: dict[str, float] = field(default_factory=dict)
    """Elemento (minúsculas) → corrente de ramo."""


def parse_rawfile(text: str) -> RawResult:
    lines = [line.strip() for line in text.splitlines()]
    lowered = [line.lower() for line in lines]
    if "variables:" not in lowered or "values:" not in lowered:
        raise SimulationEngineError("rawfile sem as secções Variables/Values")
    start, values_at = lowered.index("variables:"), lowered.index("values:")

    names = [p[1].lower() for line in lines[start + 1 : values_at] if len(p := line.split()) >= 2]
    # O primeiro token é o índice do ponto; seguem-se os valores pela ordem das variáveis.
    tokens = " ".join(lines[values_at + 1 :]).split()[1:]
    if not names or len(tokens) < len(names):
        raise SimulationEngineError("rawfile com variáveis ou valores em falta")
    try:
        values = [float(t) for t in tokens[: len(names)]]
    except ValueError:
        raise SimulationEngineError("rawfile com valores não numéricos") from None

    result = RawResult()
    for name, value in zip(names, values, strict=True):
        if m := _CURRENT.fullmatch(name):
            result.currents[m["name"] or m["branch"]] = value
        elif m := _VOLTAGE.fullmatch(name):
            result.voltages[m["name"]] = value
        else:
            result.voltages[name] = value
    return result
