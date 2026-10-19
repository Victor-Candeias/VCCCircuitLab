"""Solver DC por análise nodal modificada (MNA): ponto de funcionamento em corrente contínua.

Incógnitas: tensões das redes sem terra (as redes com terra ficam a 0 V) e correntes de ramo
das fontes de tensão e dos interruptores fechados. Estampas:

- resistência / lâmpada (R = ratedVoltageV² / ratedPowerW) → condutância;
- fonte de tensão → `V(positive) − V(negative) = voltageV`;
- interruptor fechado → fonte de 0 V (corrente definida, sem R = 0);
- interruptor aberto → sem estampa (corrente 0, sem R = ∞);
- fonte de corrente → `currentA` sai por `positive` para o circuito e entra por `negative`.

Convenção de sinais passiva para todos os componentes de dois terminais (pinos pela ordem do
catálogo): `voltageV = V(pino1) − V(pino2)`, `currentA` entra pelo pino 1 e atravessa o
componente até ao pino 2, `powerW = voltageV × currentA` é a potência absorvida (negativa
quando o componente fornece energia). A terra não tem resultado próprio.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from app.circuit.catalog import ComponentCatalog, load_catalog
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import NormalizedCircuit
from app.circuit.validate import (
    CURRENT_SOURCE_MODEL,
    GROUND_MODEL,
    SWITCH_MODEL,
    VOLTAGE_SOURCE_MODEL,
    validate,
)
from app.models.circuit import CircuitDocument, Component

#: Acima deste número de condição os resultados deixam de ser fiáveis.
MAX_CONDITION_NUMBER = 1e12
#: Acima deste número de condição a matriz é numericamente singular.
SINGULAR_CONDITION_NUMBER = 1 / np.finfo(float).eps


class BranchKind(Enum):
    CONDUCTANCE = "conductance"
    VOLTAGE = "voltage"
    CURRENT = "current"
    OPEN = "open"


@dataclass(frozen=True)
class Branch:
    """Componente de dois terminais: `a`/`b` são as redes dos pinos 1 e 2 (ordem do catálogo)."""

    component: str
    kind: BranchKind
    a: str
    b: str
    value: float


@dataclass(frozen=True)
class ComponentResult:
    voltage_v: float
    current_a: float
    power_w: float

    def to_json_dict(self) -> dict[str, float]:
        return {"voltageV": self.voltage_v, "currentA": self.current_a, "powerW": self.power_w}


@dataclass(frozen=True)
class DcResult:
    node_voltages_v: dict[str, float]
    """Tensão de cada rede em relação à terra."""
    components: dict[str, ComponentResult]
    """Resultados por componente (exceto terra), pela ordem do documento."""
    warnings: tuple[CircuitError, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "analysis": "dc_operating_point",
            "status": "success",
            "nodeVoltagesV": dict(self.node_voltages_v),
            "components": {cid: r.to_json_dict() for cid, r in self.components.items()},
            "warnings": [
                {"code": str(w.code), "message": w.message, "refs": list(w.refs)}
                for w in self.warnings
            ],
        }


def simulate_dc(document: CircuitDocument, catalog: ComponentCatalog | None = None) -> DcResult:
    """Valida e resolve o circuito; lança `CircuitValidationError` se não for simulável."""
    catalog = catalog or load_catalog()
    report = validate(document, catalog)
    normalized = report.raise_for_errors()
    return solve_dc(normalized, catalog, warnings=report.warnings)


def solve_dc(
    normalized: NormalizedCircuit,
    catalog: ComponentCatalog | None = None,
    warnings: tuple[CircuitError, ...] = (),
) -> DcResult:
    """Resolve um circuito já validado (ver `simulate_dc`)."""
    catalog = catalog or load_catalog()
    document = normalized.document
    nets = [n.id for n in document.nets or []]
    grounded, branches = dc_branches(normalized, catalog)

    index = {net: i for i, net in enumerate(n for n in nets if n not in grounded)}
    voltage_branches = [br for br in branches if br.kind is BranchKind.VOLTAGE]
    extra = {br.component: len(index) + k for k, br in enumerate(voltage_branches)}
    size = len(index) + len(voltage_branches)
    matrix = np.zeros((size, size))
    rhs = np.zeros(size)

    for br in branches:
        i, j = index.get(br.a), index.get(br.b)
        if br.kind is BranchKind.CONDUCTANCE:
            for p, q, sign in ((i, i, 1), (j, j, 1), (i, j, -1), (j, i, -1)):
                if p is not None and q is not None:
                    matrix[p, q] += sign * br.value
        elif br.kind is BranchKind.CURRENT:
            if i is not None:
                rhs[i] += br.value
            if j is not None:
                rhs[j] -= br.value
        elif br.kind is BranchKind.VOLTAGE:
            k = extra[br.component]
            for p, sign in ((i, 1), (j, -1)):
                if p is not None:
                    matrix[p, k] += sign
                    matrix[k, p] += sign
            rhs[k] = br.value

    solution = _solve(matrix, rhs)
    voltages = {net: _clean(solution[index[net]]) if net in index else 0.0 for net in nets}
    source_currents = {c: float(solution[k]) for c, k in extra.items()}
    results = component_results(branches, voltages, source_currents)
    return DcResult(node_voltages_v=voltages, components=results, warnings=tuple(warnings))


def component_results(
    branches: list[Branch], voltages: dict[str, float], source_currents: dict[str, float]
) -> dict[str, ComponentResult]:
    """Tensão, corrente e potência (convenção passiva) a partir das tensões das redes e das
    correntes de ramo das fontes de tensão/interruptores fechados (as incógnitas extra do MNA,
    ou as correntes de ramo do SPICE — mesma orientação: entram pelo pino 1)."""
    results: dict[str, ComponentResult] = {}
    for br in branches:
        if br.kind is BranchKind.VOLTAGE:
            voltage, current = br.value, source_currents[br.component]
        else:
            voltage = voltages[br.a] - voltages[br.b]
            current = {
                BranchKind.CONDUCTANCE: voltage * br.value,
                BranchKind.CURRENT: -br.value,
                BranchKind.OPEN: 0.0,
            }[br.kind]
        results[br.component] = ComponentResult(
            _clean(voltage), _clean(current), _clean(voltage * current)
        )
    return results


def dc_branches(
    normalized: NormalizedCircuit, catalog: ComponentCatalog
) -> tuple[set[str], list[Branch]]:
    """Redes com terra e ramos de dois terminais (pela ordem do documento)."""
    net_of = normalized.terminal_to_net
    grounded: set[str] = set()
    branches: list[Branch] = []
    for c in normalized.document.components:
        spec = catalog.get(c.type)
        if spec is None:
            raise ValueError(f"tipo {c.type} fora do catálogo: validar antes de resolver")
        nodes = [net_of[c.terminal(pin)] for pin in spec.pins]
        if spec.simulation_model == GROUND_MODEL:
            grounded.update(nodes)
            continue
        kind, value = _stamp(spec.simulation_model, c)
        branches.append(Branch(c.id, kind, nodes[0], nodes[1], value))
    return grounded, branches


def _stamp(model: str | None, c: Component) -> tuple[BranchKind, float]:
    p = c.properties
    if model == "resistor":
        return BranchKind.CONDUCTANCE, 1 / float(p["resistanceOhm"])
    if model == "resistive_lamp":
        return BranchKind.CONDUCTANCE, float(p["ratedPowerW"]) / float(p["ratedVoltageV"]) ** 2
    if model == VOLTAGE_SOURCE_MODEL:
        return BranchKind.VOLTAGE, float(p["voltageV"])
    if model == CURRENT_SOURCE_MODEL:
        return BranchKind.CURRENT, float(p["currentA"])
    if model == SWITCH_MODEL:
        return (BranchKind.VOLTAGE, 0.0) if p.get("closed") is True else (BranchKind.OPEN, 0.0)
    raise ValueError(f"modelo {model} não suportado: validar antes de resolver")


def _solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    if not matrix.size:
        return rhs
    condition = float(np.linalg.cond(matrix))
    if not np.isfinite(condition) or condition > SINGULAR_CONDITION_NUMBER:
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition)
    if condition > MAX_CONDITION_NUMBER:
        raise _numeric_error(CircuitErrorCode.ILL_CONDITIONED_MATRIX, condition)
    try:
        solution = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError as exc:
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition) from exc
    if not np.all(np.isfinite(solution)):
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition)
    return solution


def _numeric_error(code: CircuitErrorCode, condition: float) -> CircuitValidationError:
    if code is CircuitErrorCode.SINGULAR_MATRIX:
        message = "O sistema de equações é singular: o circuito não tem solução única."
    else:
        message = (
            f"O sistema de equações é mal condicionado (número de condição {condition:.1e}): "
            "os valores dos componentes são demasiado díspares para um resultado fiável."
        )
    return CircuitValidationError([CircuitError(code, message)])


def _clean(value: float) -> float:
    """`float` nativo, sem `-0.0`."""
    return float(value) + 0.0
