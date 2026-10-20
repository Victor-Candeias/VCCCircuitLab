"""Proteções (F2-07): avisos de disparo e resultados por componente dos contactos por polo.

O disjuntor e o diferencial são contactos ideais: a simulação não os faz disparar (nem simula
a curva de atuação), mas avisa quando, numa instalação real, disparariam:

- `OVERCURRENT`: a corrente num disjuntor (ou num polo do diferencial) excede a corrente
  estipulada `ratedCurrentA` (In);
- `RESIDUAL_CURRENT`: a corrente diferencial do diferencial (soma das correntes dos polos de
  fase e de neutro, ou seja, a fuga para a terra) excede a sensibilidade `residualCurrentA`.

Na análise transitória conta o valor máximo ao longo do tempo.

Os componentes com vários contactos têm um ramo por polo (`ID:L`, `ID:N`); o resultado do
componente é o do primeiro polo (tensão e corrente) com a potência somada de todos os polos.
"""

from collections.abc import Callable, Sequence

import numpy as np

from app.circuit.catalog import ComponentCatalog
from app.circuit.errors import CircuitError, CircuitErrorCode
from app.circuit.validate import BREAKER_MODEL, RCD_MODEL, component_of, pole_key
from app.models.circuit import CircuitDocument, Component

#: Tolerância relativa, para não avisar com a corrente exatamente igual ao limite.
_TOLERANCE = 1e-9


def finish_components[R](
    results: dict[str, R],
    document: CircuitDocument,
    catalog: ComponentCatalog,
    *,
    current: Callable[[R], Sequence[float]],
    merge: Callable[[R, R], R],
) -> tuple[dict[str, R], list[CircuitError]]:
    """Avisos das proteções (a partir das correntes de cada ramo) e resultados por componente,
    com os polos juntos (`merge`) e pela ordem do documento."""
    signed = {key: np.asarray(current(r), dtype=float) for key, r in results.items()}
    warnings: list[CircuitError] = []
    for c in document.components:
        spec = catalog.get(c.type)
        model = spec.simulation_model if spec is not None else None
        if model == BREAKER_MODEL:
            breaker = signed.get(c.id)
            warnings += _overcurrent(c, "disjuntor", None if breaker is None else np.abs(breaker))
        elif model == RCD_MODEL:
            line, neutral = signed.get(pole_key(c.id, "L")), signed.get(pole_key(c.id, "N"))
            poles = [np.abs(i) for i in (line, neutral) if i is not None]
            peak = np.maximum.reduce(poles) if poles else None
            warnings += _overcurrent(c, "diferencial", peak)
            if line is not None and neutral is not None:
                warnings += _residual(c, np.abs(line + neutral))

    merged: dict[str, R] = {}
    for key, r in results.items():
        cid = component_of(key)
        merged[cid] = merge(merged[cid], r) if cid in merged else r
    ordered = {c.id: merged[c.id] for c in document.components if c.id in merged}
    return ordered, warnings


def _overcurrent(c: Component, name: str, currents: np.ndarray | None) -> list[CircuitError]:
    rated = float(c.properties["ratedCurrentA"])
    if currents is None or not currents.size:
        return []
    peak = float(np.max(currents))
    if peak <= rated * (1 + _TOLERANCE):
        return []
    return [
        CircuitError(
            CircuitErrorCode.OVERCURRENT,
            f"A corrente no {name} {c.id} ({format_current(peak)}) excede a corrente estipulada "
            f"In = {format_current(rated)}: numa instalação real dispararia (o disparo não é "
            "simulado).",
            (c.id,),
        )
    ]


def _residual(c: Component, residual: np.ndarray) -> list[CircuitError]:
    sensitivity = float(c.properties["residualCurrentA"])
    peak = float(np.max(residual)) if residual.size else 0.0
    if peak <= sensitivity * (1 + _TOLERANCE):
        return []
    return [
        CircuitError(
            CircuitErrorCode.RESIDUAL_CURRENT,
            f"Corrente diferencial de {format_current(peak)} no diferencial {c.id} (fuga para a "
            f"terra acima de IΔn = {format_current(sensitivity)}): numa instalação real "
            "dispararia (o disparo não é simulado).",
            (c.id,),
        )
    ]


def format_current(value: float) -> str:
    if abs(value) < 1:
        return f"{value * 1000:.3g} mA"
    return f"{value:.3g} A"
