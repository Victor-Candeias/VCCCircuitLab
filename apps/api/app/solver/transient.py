"""Análise transitória (F2-02): MNA com integração BDF2 de passo fixo.

As fontes DC ligam-se em t = 0 e os condensadores e as bobinas partem das condições iniciais
(`initialVoltageV`, `initialCurrentA`). Cada passo resolve um sistema linear em que os
elementos reativos são substituídos por modelos companheiros:

- condensador: `i_n = C/h · (α0·v_n + α1·v_{n−1} + α2·v_{n−2})` → condutância `α0·C/h` em
  paralelo com uma fonte de corrente de histórico;
- bobina: `v_n = L/h · (α0·i_n + α1·i_{n−1} + α2·i_{n−2})` → corrente de ramo como incógnita
  extra (como uma fonte de tensão), o que admite bobinas em paralelo com fontes de tensão.

O primeiro passo é de Euler implícito (α = 1, −1, 0) e os seguintes de BDF2 (α = 3/2, −2, 1/2),
um método L-estável sem as oscilações numéricas do trapézio. O passo interno divide o passo de
saída em subpassos de modo a haver pelo menos `MIN_INTERNAL_STEPS` passos.

O ponto t = 0 resolve o circuito com os condensadores como fontes de tensão e as bobinas como
fontes de corrente (condições iniciais). Se esse sistema for singular (ex.: condensador em
paralelo com uma fonte de tensão, ou bobina em série com uma fonte de corrente), o estado
salta: o ponto t = 0 passa a ser o estado logo após o salto (0⁺), obtido com um passo de Euler
implícito muito curto (`h · INITIAL_STEP_FRACTION`).

Com semicondutores (F2-04) o sistema deixa de ser linear: em vez da recorrência linear, cada
passo interno (mesmos coeficientes e passos) é resolvido pelo método de Newton
(`app.solver.semiconductors`), partindo da solução do passo anterior. Os semicondutores não têm
capacidades, logo não acrescentam estado.

Convenção de sinais igual à da análise DC (`app.solver.mna`).
"""

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from app.circuit.catalog import ComponentCatalog, load_catalog
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import NormalizedCircuit
from app.circuit.validate import component_of, validate
from app.models.circuit import CircuitDocument
from app.solver.mna import (
    MAX_CONDITION_NUMBER,
    SINGULAR_CONDITION_NUMBER,
    Branch,
    BranchKind,
    _numeric_error,
    _solve_nonlinear_step,
    circuit_branches,
    defined_nets,
)
from app.solver.protection import finish_components
from app.solver.semiconductors import (
    NewtonSolver,
    Semiconductor,
    semiconductor_devices,
    semiconductor_results,
)

#: Número mínimo de passos internos de integração.
MIN_INTERNAL_STEPS = 2000
#: Número máximo de intervalos de saída (`stopTimeS / timeStepS`); a resposta tem +1 ponto.
MAX_OUTPUT_INTERVALS = 10_000
#: Duração máxima da simulação, em segundos.
MAX_STOP_TIME_S = 1000.0
#: Passo do salto inicial (0⁺), em fração do passo interno.
INITIAL_STEP_FRACTION = 1e-3

_BACKWARD_EULER = (1.0, -1.0, 0.0)
_BDF2 = (1.5, -2.0, 0.5)


def output_intervals(stop_time_s: float, time_step_s: float) -> int:
    """Número de intervalos de saída: o passo efetivo é `stop_time_s / output_intervals(...)`
    (o passo pedido, ou ligeiramente menor para acabar exatamente em `stop_time_s`)."""
    return max(1, math.ceil(stop_time_s / time_step_s * (1 - 1e-9)))


@dataclass(frozen=True)
class ComponentSeries:
    voltage_v: list[float]
    current_a: list[float]
    power_w: list[float]

    def to_json_dict(self) -> dict[str, list[float]]:
        return {"voltageV": self.voltage_v, "currentA": self.current_a, "powerW": self.power_w}


@dataclass(frozen=True)
class TransientResult:
    time_s: list[float]
    node_voltages_v: dict[str, list[float]]
    """Série da tensão de cada rede em relação à terra."""
    components: dict[str, ComponentSeries]
    """Séries por componente (exceto terra), pela ordem do documento."""
    warnings: tuple[CircuitError, ...] = ()

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "analysis": "transient",
            "status": "success",
            "timeS": self.time_s,
            "nodeVoltagesV": dict(self.node_voltages_v),
            "components": {cid: s.to_json_dict() for cid, s in self.components.items()},
            "warnings": [
                {"code": str(w.code), "message": w.message, "refs": list(w.refs)}
                for w in self.warnings
            ],
        }


def simulate_transient(
    document: CircuitDocument,
    catalog: ComponentCatalog | None = None,
    *,
    stop_time_s: float,
    time_step_s: float,
    timeout_s: float | None = None,
) -> TransientResult:
    """Valida (análise transitória) e simula; lança `CircuitValidationError` se o circuito não
    for simulável e `TimeoutError` se exceder `timeout_s`."""
    catalog = catalog or load_catalog()
    report = validate(document, catalog, analysis="transient")
    normalized = report.raise_for_errors()
    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    return solve_transient(
        normalized,
        catalog,
        stop_time_s=stop_time_s,
        time_step_s=time_step_s,
        warnings=report.warnings,
        deadline=deadline,
    )


def solve_transient(
    normalized: NormalizedCircuit,
    catalog: ComponentCatalog | None = None,
    *,
    stop_time_s: float,
    time_step_s: float,
    warnings: tuple[CircuitError, ...] = (),
    deadline: float | None = None,
) -> TransientResult:
    """Resolve um circuito já validado (ver `simulate_transient`)."""
    catalog = catalog or load_catalog()
    nets = defined_nets(normalized, catalog)
    grounded, branches = circuit_branches(normalized, catalog)
    devices = semiconductor_devices(normalized, catalog)
    order = [c.id for c in normalized.document.components]
    system = _System(nets, grounded, branches, devices, order)

    intervals = output_intervals(stop_time_s, time_step_s)
    substeps = math.ceil(MIN_INTERNAL_STEPS / intervals)
    h = stop_time_s / (intervals * substeps)
    times = np.arange(intervals + 1) * (stop_time_s / intervals)
    times[-1] = stop_time_s
    if devices:
        xs, ics = _integrate_nonlinear(system, intervals, substeps, h, deadline)
        return finish_transient(system.results(times, xs, ics, warnings), normalized, catalog)

    total = intervals * substeps
    x0, cap_currents0 = system.initial_state(h * INITIAL_STEP_FRACTION)
    first, rest = system.update(_BACKWARD_EULER, h), system.update(_BDF2, h)

    # Recorrência só no estado reativo z = (tensões dos condensadores, correntes das bobinas):
    # w_n = (z_n, z_{n−1}) = A·w_{n−1} + c. As restantes incógnitas são reconstruídas depois.
    states = np.empty((total + 1, system.state_size))
    states[0] = system.state(x0)
    states[1] = system.state(first.solve(states[0], states[0]))
    m = system.state_size
    transition = np.zeros((2 * m, 2 * m))
    transition[:m] = system.selector @ rest.gain
    transition[m:, :m] = np.eye(m)
    offset = np.concatenate([system.selector @ rest.constant, np.zeros(m)])
    w = np.concatenate([states[1], states[0]])
    for n in range(2, total + 1):
        w = transition.dot(w) + offset
        states[n] = w[:m]
        if deadline is not None and n % 1024 == 0 and time.monotonic() > deadline:
            raise TimeoutError("simulação transitória excedeu o tempo máximo")
    if not np.all(np.isfinite(states)):
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, math.inf)

    recorded = np.arange(1, intervals + 1) * substeps
    later = recorded[recorded >= 2]
    xs, ics = [x0[None, :]], [cap_currents0[None, :]]
    if substeps == 1:
        x1 = first.solve(states[0], states[0])
        xs.append(x1[None, :])
        ics.append(first.cap_currents(system, x1, states[0], states[0])[None, :])
    xs.append(rest.solve(states[later - 1], states[later - 2]))
    ics.append(rest.cap_currents(system, xs[-1], states[later - 1], states[later - 2]))
    result = system.results(times, np.concatenate(xs), np.concatenate(ics), warnings)
    return finish_transient(result, normalized, catalog)


def finish_transient(
    result: TransientResult, normalized: NormalizedCircuit, catalog: ComponentCatalog
) -> TransientResult:
    """Avisos das proteções (F2-07, pelo máximo ao longo do tempo) e séries por componente,
    com os polos juntos (ver `app.solver.protection`)."""
    components, protection = finish_components(
        result.components,
        normalized.document,
        catalog,
        current=lambda s: s.current_a,
        merge=lambda a, b: ComponentSeries(
            a.voltage_v,
            a.current_a,
            [x + y for x, y in zip(a.power_w, b.power_w, strict=True)],
        ),
    )
    return replace(result, components=components, warnings=(*result.warnings, *protection))


def _integrate_nonlinear(
    system: "_System", intervals: int, substeps: int, h: float, deadline: float | None
) -> tuple[np.ndarray, np.ndarray]:
    """Incógnitas e correntes dos condensadores nos instantes de saída, passo a passo, com o
    método de Newton em cada passo interno."""
    newton = system.newton(system.size)
    x, cap_currents = system.initial_state(h * INITIAL_STEP_FRACTION)
    junctions = newton.junctions(x)
    xs, ics = [x], [cap_currents]
    matrices = {alphas: system.matrix(alphas[0], h) for alphas in (_BACKWARD_EULER, _BDF2)}
    z1 = z2 = system.state(x)
    for n in range(1, intervals * substeps + 1):
        alphas = _BACKWARD_EULER if n == 1 else _BDF2
        rhs = system.step_rhs(alphas, h, z1, z2)
        x, junctions = newton.solve(matrices[alphas], rhs, x, junctions)
        if n % substeps == 0:
            xs.append(x)
            ics.append(system.cap_currents(alphas, h, x, z1, z2))
        z1, z2 = system.state(x), z1
        if deadline is not None and n % 256 == 0 and time.monotonic() > deadline:
            raise TimeoutError("simulação transitória excedeu o tempo máximo")
    return np.array(xs), np.array(ics)


@dataclass(frozen=True)
class _Update:
    """Passo com coeficientes `alphas`: `x_n = constant + gain · (z_{n−1}, z_{n−2})`."""

    alphas: tuple[float, float, float]
    h: float
    constant: np.ndarray
    gain: np.ndarray

    def solve(self, z1: np.ndarray, z2: np.ndarray) -> np.ndarray:
        """Incógnitas no instante n (aceita lotes: uma linha por instante)."""
        return self.constant + np.concatenate([z1, z2], axis=-1) @ self.gain.T

    def cap_currents(
        self, system: "_System", x: np.ndarray, z1: np.ndarray, z2: np.ndarray
    ) -> np.ndarray:
        return system.cap_currents(self.alphas, self.h, x, z1, z2)


class _System:
    """Sistema MNA: tensões das redes sem terra, depois correntes das fontes de tensão (e
    interruptores fechados) e das bobinas. Os semicondutores (`devices`) ficam fora da parte
    linear e entram em cada iteração de Newton."""

    def __init__(
        self,
        nets: list[str],
        grounded: set[str],
        branches: list[Branch],
        devices: Sequence[Semiconductor] = (),
        order: Sequence[str] = (),
    ) -> None:
        self.nets = nets
        self.branches = branches
        self.devices = list(devices)
        self.order = list(order)
        self.index = {net: i for i, net in enumerate(n for n in nets if n not in grounded)}
        by_kind = {kind: [br for br in branches if br.kind is kind] for kind in BranchKind}
        self.capacitors = by_kind[BranchKind.CAPACITOR]
        extra = by_kind[BranchKind.VOLTAGE] + by_kind[BranchKind.INDUCTOR]
        self.extra = {br.component: len(self.index) + k for k, br in enumerate(extra)}
        self.cap_column = {br.component: k for k, br in enumerate(self.capacitors)}
        self.size = len(self.index) + len(extra)

        inductors = by_kind[BranchKind.INDUCTOR]
        self.ind_rows = np.array([self.extra[br.component] for br in inductors], dtype=int)
        self.inductance = np.array([br.value for br in inductors])
        self.capacitance = np.array([br.value for br in self.capacitors])
        self.v0 = np.array([br.initial for br in self.capacitors])
        self.i0 = np.array([br.initial for br in inductors])

        self.incidence = np.zeros((self.size, len(self.capacitors)))
        for k, br in enumerate(self.capacitors):
            for net, sign in ((br.a, 1.0), (br.b, -1.0)):
                if net in self.index:
                    self.incidence[self.index[net], k] += sign

        # Parte constante: resistências, fontes, interruptores e incidência das bobinas.
        self.base = np.zeros((self.size, self.size))
        self.rhs = np.zeros(self.size)
        for br in branches:
            i, j = self.index.get(br.a), self.index.get(br.b)
            if br.kind is BranchKind.CONDUCTANCE:
                self._conductance(self.base, i, j, br.value)
            elif br.kind is BranchKind.CURRENT:
                if i is not None:
                    self.rhs[i] += br.value
                if j is not None:
                    self.rhs[j] -= br.value
            elif br.kind in (BranchKind.VOLTAGE, BranchKind.INDUCTOR):
                k = self.extra[br.component]
                for p, sign in ((i, 1.0), (j, -1.0)):
                    if p is not None:
                        self.base[p, k] += sign
                        self.base[k, p] += sign
                if br.kind is BranchKind.VOLTAGE:
                    self.rhs[k] = br.value

    @staticmethod
    def _conductance(matrix: np.ndarray, i: int | None, j: int | None, g: float) -> None:
        for p, q, sign in ((i, i, 1), (j, j, 1), (i, j, -1), (j, i, -1)):
            if p is not None and q is not None:
                matrix[p, q] += sign * g

    def matrix(self, alpha0: float, h: float) -> np.ndarray:
        matrix = self.base.copy()
        matrix += self.incidence @ np.diag(alpha0 * self.capacitance / h) @ self.incidence.T
        matrix[self.ind_rows, self.ind_rows] -= alpha0 * self.inductance / h
        return matrix

    @property
    def state_size(self) -> int:
        return len(self.capacitors) + len(self.ind_rows)

    @property
    def selector(self) -> np.ndarray:
        """Matriz que extrai o estado reativo z das incógnitas x."""
        selection = np.zeros((len(self.ind_rows), self.size))
        selection[np.arange(len(self.ind_rows)), self.ind_rows] = 1.0
        return np.vstack([self.incidence.T, selection])

    def state(self, x: np.ndarray) -> np.ndarray:
        return self.selector @ x

    def history(self, h: float) -> np.ndarray:
        """Matriz que leva o estado reativo de um instante anterior ao lado direito."""
        n_ind = len(self.ind_rows)
        ind_columns = np.zeros((self.size, n_ind))
        ind_columns[self.ind_rows, np.arange(n_ind)] = 1.0
        return np.hstack(
            [-self.incidence * (self.capacitance / h), ind_columns * (self.inductance / h)]
        )

    def step_rhs(
        self, alphas: tuple[float, float, float], h: float, z1: np.ndarray, z2: np.ndarray
    ) -> np.ndarray:
        """Lado direito do passo n, a partir dos estados z_{n−1} e z_{n−2}."""
        _, alpha1, alpha2 = alphas
        return self.rhs + self.history(h) @ (alpha1 * z1 + alpha2 * z2)

    def cap_currents(
        self,
        alphas: tuple[float, float, float],
        h: float,
        x: np.ndarray,
        z1: np.ndarray,
        z2: np.ndarray,
    ) -> np.ndarray:
        alpha0, alpha1, alpha2 = alphas
        n = len(self.capacitors)
        scale = self.capacitance / h
        return scale * (alpha0 * (x @ self.incidence) + alpha1 * z1[..., :n] + alpha2 * z2[..., :n])

    def newton(self, size: int) -> NewtonSolver:
        """Método de Newton para um sistema com as primeiras incógnitas iguais às do MNA."""
        return NewtonSolver(self.devices, self.index, size, _solve_nonlinear_step)

    def _solve(self, matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
        if not self.devices:
            return _inverse(matrix) @ rhs
        return self.newton(len(rhs)).solve_with_source_stepping(matrix, rhs)[0]

    def update(self, alphas: tuple[float, float, float], h: float) -> _Update:
        alpha0, alpha1, alpha2 = alphas
        inverse = _inverse(self.matrix(alpha0, h))
        history = self.history(h)
        gain = inverse @ np.hstack([alpha1 * history, alpha2 * history])
        return _Update(alphas, h, inverse @ self.rhs, gain)

    def initial_state(self, jump_step: float) -> tuple[np.ndarray, np.ndarray]:
        """Ponto t = 0 consistente com as condições iniciais ou, se singular, o estado 0⁺."""
        n_caps = len(self.capacitors)
        size = self.size + n_caps
        matrix = np.zeros((size, size))
        matrix[: self.size, : self.size] = self.base
        rhs = np.zeros(size)
        rhs[: self.size] = self.rhs
        # Condensadores como fontes de tensão (incógnita extra = corrente).
        matrix[: self.size, self.size :] = self.incidence
        matrix[self.size :, : self.size] = self.incidence.T
        rhs[self.size :] = self.v0
        # Bobinas como fontes de corrente: a linha da bobina passa a `i = i0`.
        matrix[self.ind_rows, :] = 0.0
        matrix[self.ind_rows, self.ind_rows] = 1.0
        rhs[self.ind_rows] = self.i0
        try:
            solution = self._solve(matrix, rhs)
        except CircuitValidationError:
            z0 = np.concatenate([self.v0, self.i0])
            jump = self.matrix(_BACKWARD_EULER[0], jump_step)
            x = self._solve(jump, self.step_rhs(_BACKWARD_EULER, jump_step, z0, z0))
            return x, self.cap_currents(_BACKWARD_EULER, jump_step, x, z0, z0)
        return solution[: self.size], solution[self.size :]

    def results(
        self,
        times: np.ndarray,
        xs: np.ndarray,
        cap_currents: np.ndarray,
        warnings: tuple[CircuitError, ...],
    ) -> TransientResult:
        points = len(times)
        voltages = {
            net: xs[:, self.index[net]] if net in self.index else np.zeros(points)
            for net in self.nets
        }
        currents = {c: xs[:, k] for c, k in self.extra.items()}
        currents |= {c: cap_currents[:, k] for c, k in self.cap_column.items()}
        return transient_result(
            times, voltages, self.branches, currents, warnings, self.devices, order=self.order
        )


def transient_result(
    times: np.ndarray,
    voltages: dict[str, np.ndarray],
    branches: list[Branch],
    currents: dict[str, np.ndarray],
    warnings: tuple[CircuitError, ...],
    devices: Sequence[Semiconductor] = (),
    device_currents: dict[str, list[np.ndarray]] | None = None,
    order: Sequence[str] = (),
) -> TransientResult:
    """Séries por componente (convenção passiva) a partir das tensões das redes e das correntes
    das fontes de tensão, interruptores fechados, bobinas e condensadores (incógnitas do MNA ou
    vetores do rawfile do ngspice — mesma orientação: entram pelo pino 1).

    Nos semicondutores, as correntes que entram nos terminais vêm de `device_currents` (fontes
    de medida do ngspice) ou, se omitido, do modelo. Com `order`, os componentes ficam por essa
    ordem (a do documento)."""
    points = len(times)
    components: dict[str, ComponentSeries] = {}
    for br in branches:
        if br.kind is BranchKind.OPEN and (br.a not in voltages or br.b not in voltages):
            continue  # voltímetro com uma ponta numa rede de potencial indefinido
        voltage = voltages[br.a] - voltages[br.b]
        if br.kind is BranchKind.VOLTAGE:
            voltage = np.full(points, br.value)
            current = currents[br.component]
        elif br.kind in (BranchKind.INDUCTOR, BranchKind.CAPACITOR):
            current = currents[br.component]
        elif br.kind is BranchKind.CONDUCTANCE:
            current = voltage * br.value
        elif br.kind is BranchKind.CURRENT:
            current = np.full(points, -br.value)
        else:
            current = np.zeros(points)
        components[br.component] = ComponentSeries(
            _series(voltage), _series(current), _series(voltage * current)
        )
    for device in devices:
        terminals = [voltages[net] for net in device.nets]
        if device_currents is None:
            sensed = device.terminal_currents(terminals)
        else:
            sensed = device_currents[device.component]
        voltage, current, power = semiconductor_results(device, terminals, sensed)
        components[device.component] = ComponentSeries(
            _series(voltage), _series(current), _series(power)
        )
    if order:
        positions = {cid: k for k, cid in enumerate(order)}
        components = dict(
            sorted(components.items(), key=lambda item: positions[component_of(item[0])])
        )
    return TransientResult(
        time_s=_series(times),
        node_voltages_v={net: _series(v) for net, v in voltages.items()},
        components=components,
        warnings=tuple(warnings),
    )


def _inverse(matrix: np.ndarray) -> np.ndarray:
    """Inversa (a matriz é constante durante a integração), com as verificações de condição
    do solver DC."""
    if not matrix.size:
        return matrix
    condition = float(np.linalg.cond(matrix))
    if not np.isfinite(condition) or condition > SINGULAR_CONDITION_NUMBER:
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition)
    if condition > MAX_CONDITION_NUMBER:
        raise _numeric_error(CircuitErrorCode.ILL_CONDITIONED_MATRIX, condition)
    try:
        return np.linalg.inv(matrix)
    except np.linalg.LinAlgError as exc:
        raise _numeric_error(CircuitErrorCode.SINGULAR_MATRIX, condition) from exc


def _series(values: np.ndarray) -> list[float]:
    """`float` nativos, sem `-0.0`."""
    return (np.asarray(values, dtype=float) + 0.0).tolist()
