"""Solver DC por análise nodal modificada (MNA): ponto de funcionamento em corrente contínua.

Incógnitas: tensões das redes sem terra (as redes com terra ficam a 0 V) e correntes de ramo
das fontes de tensão e dos interruptores fechados. Estampas:

- resistência / lâmpada (R = ratedVoltageV² / ratedPowerW) → condutância;
- fonte de tensão → `V(positive) − V(negative) = voltageV`;
- interruptor fechado → fonte de 0 V (corrente definida, sem R = 0);
- interruptor aberto → sem estampa (corrente 0, sem R = ∞);
- fonte de corrente → `currentA` sai por `positive` para o circuito e entra por `negative`;
- condensador → aberto (corrente 0); bobina → fonte de 0 V (como um interruptor fechado);
- instrumentos ideais (F2-03): voltímetro → aberto (a leitura é `voltageV`), amperímetro →
  fonte de 0 V (a leitura é `currentA`), osciloscópio → sem ramo (as leituras são as tensões
  das redes dos canais);
- semicondutores (F2-04) → não lineares: díodos, LEDs e transístores (`app.solver.semiconductors`)
  linearizados em cada iteração do método de Newton, com rampa das fontes se não convergir.

As redes ligadas apenas a pontas de instrumentos (voltímetro/osciloscópio) não têm potencial
definido: ficam fora das incógnitas e de `nodeVoltagesV`, e os voltímetros ligados a elas não
têm resultado.

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
    AMMETER_MODEL,
    CAPACITOR_MODEL,
    CURRENT_SOURCE_MODEL,
    GROUND_MODEL,
    INDUCTOR_MODEL,
    OSCILLOSCOPE_MODEL,
    PROBE_MODELS,
    SEMICONDUCTOR_MODELS,
    SWITCH_MODEL,
    VOLTAGE_SOURCE_MODEL,
    VOLTMETER_MODEL,
    validate,
)
from app.models.circuit import CircuitDocument, Component
from app.solver.semiconductors import (
    NewtonSolver,
    Semiconductor,
    semiconductor_devices,
    semiconductor_results,
)

#: Acima deste número de condição os resultados deixam de ser fiáveis.
MAX_CONDITION_NUMBER = 1e12
#: Acima deste número de condição a matriz é numericamente singular.
SINGULAR_CONDITION_NUMBER = 1 / np.finfo(float).eps


class BranchKind(Enum):
    CONDUCTANCE = "conductance"
    VOLTAGE = "voltage"
    CURRENT = "current"
    OPEN = "open"
    CAPACITOR = "capacitor"
    """`value` = capacidade (F), `initial` = tensão inicial (V)."""
    INDUCTOR = "inductor"
    """`value` = indutância (H), `initial` = corrente inicial (A, do pino 1 para o pino 2)."""


@dataclass(frozen=True)
class Branch:
    """Componente de dois terminais: `a`/`b` são as redes dos pinos 1 e 2 (ordem do catálogo)."""

    component: str
    kind: BranchKind
    a: str
    b: str
    value: float
    initial: float = 0.0


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
    nets = defined_nets(normalized, catalog)
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

    devices = semiconductor_devices(normalized, catalog)
    if devices:
        newton = NewtonSolver(devices, index, size, _solve_nonlinear_step)
        solution, _ = newton.solve_with_source_stepping(matrix, rhs)
    else:
        solution = _solve(matrix, rhs)
    voltages = {net: _clean(solution[index[net]]) if net in index else 0.0 for net in nets}
    source_currents = {c: float(solution[k]) for c, k in extra.items()}
    results = component_results(branches, voltages, source_currents)
    for device in devices:
        terminals = [np.array(voltages[net]) for net in device.nets]
        results[device.component] = device_result(
            device, voltages, device.terminal_currents(terminals)
        )
    return DcResult(
        node_voltages_v=voltages,
        components=in_document_order(results, normalized),
        warnings=tuple(warnings),
    )


def device_result(
    device: Semiconductor, voltages: dict[str, float], currents: list[np.ndarray]
) -> ComponentResult:
    """Resultado de um semicondutor a partir das tensões das redes e das correntes que entram
    nos terminais (do modelo, ou das fontes de medida do SPICE)."""
    voltage, current, power = semiconductor_results(
        device, [voltages[net] for net in device.nets], currents
    )
    return ComponentResult(_clean(voltage), _clean(current), _clean(power))


def in_document_order(results: dict[str, Any], normalized: NormalizedCircuit) -> dict[str, Any]:
    """Resultados por componente pela ordem do documento."""
    return {c.id: results[c.id] for c in normalized.document.components if c.id in results}


def component_results(
    branches: list[Branch], voltages: dict[str, float], source_currents: dict[str, float]
) -> dict[str, ComponentResult]:
    """Tensão, corrente e potência (convenção passiva) a partir das tensões das redes e das
    correntes de ramo das fontes de tensão/interruptores fechados (as incógnitas extra do MNA,
    ou as correntes de ramo do SPICE — mesma orientação: entram pelo pino 1)."""
    results: dict[str, ComponentResult] = {}
    for br in branches:
        if br.kind is BranchKind.OPEN and (br.a not in voltages or br.b not in voltages):
            continue  # voltímetro com uma ponta numa rede de potencial indefinido
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


def defined_nets(normalized: NormalizedCircuit, catalog: ComponentCatalog) -> list[str]:
    """Redes com potencial definido (pela ordem do documento): todas exceto as que só ligam a
    pontas de instrumentos de impedância infinita (voltímetro/osciloscópio)."""
    probe_terminals = {
        c.terminal(pin)
        for c in normalized.document.components
        if (spec := catalog.get(c.type)) is not None and spec.simulation_model in PROBE_MODELS
        for pin in spec.pins
    }
    return [
        net.id
        for net in normalized.document.nets or []
        if not probe_terminals.issuperset(net.terminals)
    ]


def dc_branches(
    normalized: NormalizedCircuit, catalog: ComponentCatalog
) -> tuple[set[str], list[Branch]]:
    """Redes com terra e ramos de dois terminais (pela ordem do documento), com os condensadores
    e as bobinas substituídos pelos equivalentes DC (aberto e fonte de 0 V)."""
    grounded, branches = circuit_branches(normalized, catalog)
    return grounded, [_dc_equivalent(br) for br in branches]


def _dc_equivalent(br: Branch) -> Branch:
    if br.kind is BranchKind.CAPACITOR:
        return Branch(br.component, BranchKind.OPEN, br.a, br.b, 0.0)
    if br.kind is BranchKind.INDUCTOR:
        return Branch(br.component, BranchKind.VOLTAGE, br.a, br.b, 0.0)
    return br


def circuit_branches(
    normalized: NormalizedCircuit, catalog: ComponentCatalog
) -> tuple[set[str], list[Branch]]:
    """Redes com terra e ramos de dois terminais (pela ordem do documento), incluindo os
    condensadores e as bobinas (`BranchKind.CAPACITOR`/`INDUCTOR`)."""
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
        if spec.simulation_model == OSCILLOSCOPE_MODEL:
            continue  # sem ramo: as leituras são as tensões das redes
        if spec.simulation_model in SEMICONDUCTOR_MODELS:
            continue  # não lineares: `semiconductor_devices`
        kind, value, initial = _stamp(spec.simulation_model, c)
        branches.append(Branch(c.id, kind, nodes[0], nodes[1], value, initial))
    return grounded, branches


def _stamp(model: str | None, c: Component) -> tuple[BranchKind, float, float]:
    p = c.properties
    if model == "resistor":
        return BranchKind.CONDUCTANCE, 1 / float(p["resistanceOhm"]), 0.0
    if model == "resistive_lamp":
        conductance = float(p["ratedPowerW"]) / float(p["ratedVoltageV"]) ** 2
        return BranchKind.CONDUCTANCE, conductance, 0.0
    if model == VOLTAGE_SOURCE_MODEL:
        return BranchKind.VOLTAGE, float(p["voltageV"]), 0.0
    if model == CURRENT_SOURCE_MODEL:
        return BranchKind.CURRENT, float(p["currentA"]), 0.0
    if model == SWITCH_MODEL:
        kind = BranchKind.VOLTAGE if p.get("closed") is True else BranchKind.OPEN
        return kind, 0.0, 0.0
    if model == VOLTMETER_MODEL:
        return BranchKind.OPEN, 0.0, 0.0
    if model == AMMETER_MODEL:
        return BranchKind.VOLTAGE, 0.0, 0.0
    if model == CAPACITOR_MODEL:
        return BranchKind.CAPACITOR, float(p["capacitanceF"]), float(p["initialVoltageV"])
    if model == INDUCTOR_MODEL:
        return BranchKind.INDUCTOR, float(p["inductanceH"]), float(p["initialCurrentA"])
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


def _solve_nonlinear_step(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Iteração de Newton: só a matriz singular é erro. As condutâncias das junções vão de
    `GMIN` a ~1e8 S, por isso o número de condição é calculado depois de equilibrar linhas e
    colunas (escala pelo máximo absoluto), que não altera a solução."""
    if not matrix.size:
        return rhs
    with np.errstate(divide="ignore"):
        rows = 1.0 / np.max(np.abs(matrix), axis=1)
        scaled = rows[:, None] * matrix
        columns = 1.0 / np.max(np.abs(scaled), axis=0)
    if not (np.all(np.isfinite(rows)) and np.all(np.isfinite(columns))):
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, float("inf"))
    scaled *= columns[None, :]
    condition = float(np.linalg.cond(scaled))
    if not np.isfinite(condition) or condition > SINGULAR_CONDITION_NUMBER:
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition)
    try:
        return columns * np.linalg.solve(scaled, rows * rhs)
    except np.linalg.LinAlgError as exc:
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition) from exc


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
