"""Semicondutores (F2-04): díodo/LED e transístores bipolares NPN/PNP, e o método de
Newton-Raphson que os resolve no MNA.

Modelos (os mesmos que `app/spice/netlist.py` escreve nos `.model` do ngspice, a 27 °C):

- díodo e LED (`diode`): Shockley, `i = IS·(exp(v/(N·Vt)) − 1)` com `N = 2`; `IS` vem da
  tensão direta `forwardVoltageV` à corrente `forwardCurrentA`. Sem resistência série,
  capacidades nem rutura inversa;
- transístores (`bjt_npn`/`bjt_pnp`): Ebers-Moll de transporte (Gummel-Poon do SPICE com os
  parâmetros por omissão), `IS = saturationCurrentA`, `BF = currentGain`, `BR = 1`, `NF = NR = 1`;
  sem efeito de Early, resistências nem capacidades.

Como no SPICE, cada junção tem a condutância `GMIN` em paralelo e, abaixo de `−3·N·Vt`, a
exponencial é substituída pela mesma extensão cúbica (corrente ≈ −IS). As tensões das junções
são limitadas entre iterações (`pnjlim`) para a exponencial não divergir.

Resultados (convenção do `app.solver.mna`): no díodo `voltageV = V(ânodo) − V(cátodo)` e
`currentA` entra pelo ânodo; no transístor `voltageV = V(coletor) − V(emissor)`, `currentA` é a
corrente que entra pelo coletor e `powerW = V_CE·I_C + V_BE·I_B` é a potência dissipada.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from app.circuit.catalog import ComponentCatalog
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import NormalizedCircuit
from app.circuit.validate import BJT_NPN_MODEL, BJT_PNP_MODEL, DIODE_MODEL

#: Tensão térmica kT/q a 27 °C (temperatura nominal do SPICE).
THERMAL_VOLTAGE_V = 8.617333262e-5 * 300.15
#: Coeficiente de emissão dos díodos e LEDs.
DIODE_EMISSION_COEFFICIENT = 2.0
#: Ganho de corrente inverso dos transístores.
BJT_REVERSE_GAIN = 1.0
#: Condutância mínima em paralelo com cada junção (como o `gmin` do SPICE).
GMIN = 1e-12
#: Acima deste argumento a exponencial passa a linear (evita overflow).
MAX_EXPONENT = 200.0
#: Iterações de Newton por resolução (como o `itl1` do SPICE).
MAX_ITERATIONS = 150
RELATIVE_TOLERANCE = 1e-9
ABSOLUTE_TOLERANCE = 1e-12
#: Menor fração de rampa das fontes (`source stepping`) antes de desistir.
MIN_SOURCE_STEP = 1e-4


@dataclass(frozen=True)
class Semiconductor:
    """Dispositivo não linear. `nets`: díodo (ânodo, cátodo); transístor (coletor, base,
    emissor). `polarity` é +1 (díodo, NPN) ou −1 (PNP)."""

    component: str
    model: str
    nets: tuple[str, ...]
    saturation_current: float
    emission: float = 1.0
    polarity: float = 1.0
    beta_f: float = 1.0
    beta_r: float = BJT_REVERSE_GAIN

    @property
    def is_diode(self) -> bool:
        return self.model == DIODE_MODEL

    @property
    def junction_vt(self) -> float:
        return self.emission * THERMAL_VOLTAGE_V

    @property
    def critical_voltage(self) -> float:
        vt = self.junction_vt
        return vt * math.log(vt / (math.sqrt(2) * self.saturation_current))

    def junction_map(self) -> np.ndarray:
        """Matriz (junções × terminais) das tensões das junções a partir das dos terminais:
        díodo `v_d = V_a − V_k`; transístor `v_be = p·(V_b − V_e)`, `v_bc = p·(V_b − V_c)`."""
        if self.is_diode:
            return np.array([[1.0, -1.0]])
        p = self.polarity
        return np.array([[0.0, p, -p], [-p, p, 0.0]])

    def output_map(self) -> np.ndarray:
        """Matriz (terminais × saídas) das correntes que entram nos terminais a partir das saídas
        do modelo: díodo (i_d); transístor (i_c, i_b) no sentido do NPN."""
        if self.is_diode:
            return np.array([[1.0], [-1.0]])
        p = self.polarity
        return p * np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, -1.0]])

    def evaluate(self, junctions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Saídas do modelo e jacobiano (saídas × junções) nas tensões de junção dadas."""
        vt = self.junction_vt
        if self.is_diode:
            current, conductance = junction_current(junctions[0], self.saturation_current, vt)
            return (
                np.array([current + GMIN * junctions[0]]),
                np.array([[conductance + GMIN]]),
            )
        vbe, vbc = junctions
        cbe, gbe = junction_current(vbe, self.saturation_current, vt)
        cbc, gbc = junction_current(vbc, self.saturation_current, vt)
        ic = cbe - cbc - cbc / self.beta_r - GMIN * vbc
        ib = cbe / self.beta_f + cbc / self.beta_r + GMIN * (vbe + vbc)
        jacobian = np.array(
            [
                [gbe, -gbc - gbc / self.beta_r - GMIN],
                [gbe / self.beta_f + GMIN, gbc / self.beta_r + GMIN],
            ]
        )
        return np.array([ic, ib]), jacobian

    def terminal_currents(self, voltages: Sequence[np.ndarray]) -> list[np.ndarray]:
        """Correntes que entram em cada terminal (aceita séries) a partir das tensões dos
        terminais: díodo (i_a,); transístor (i_c, i_b)."""
        junctions = self.junction_map() @ np.array([np.asarray(v, dtype=float) for v in voltages])
        vt = self.junction_vt
        if self.is_diode:
            current = _currents(junctions[0], self.saturation_current, vt)
            return [current + GMIN * junctions[0]]
        vbe, vbc = junctions
        cbe = _currents(vbe, self.saturation_current, vt)
        cbc = _currents(vbc, self.saturation_current, vt)
        ic = cbe - cbc - cbc / self.beta_r - GMIN * vbc
        ib = cbe / self.beta_f + cbc / self.beta_r + GMIN * (vbe + vbc)
        return [self.polarity * ic, self.polarity * ib]


def junction_current(v: float, saturation: float, vt: float) -> tuple[float, float]:
    """Corrente e condutância de uma junção pn ideal, com a extensão do SPICE em inversa."""
    if v >= -3 * vt:
        arg = v / vt
        if arg > MAX_EXPONENT:
            exp = math.exp(MAX_EXPONENT)
            return saturation * (exp * (1 + arg - MAX_EXPONENT) - 1), saturation * exp / vt
        exp = math.exp(arg)
        return saturation * (exp - 1), saturation * exp / vt
    arg = (3 * vt / (v * math.e)) ** 3
    return -saturation * (1 + arg), saturation * 3 * arg / v


def _currents(v: np.ndarray, saturation: float, vt: float) -> np.ndarray:
    """`junction_current` vetorizada (só a corrente)."""
    v = np.asarray(v, dtype=float)
    arg = v / vt
    forward = np.where(
        arg > MAX_EXPONENT,
        math.exp(MAX_EXPONENT) * (1 + arg - MAX_EXPONENT),
        np.exp(np.minimum(arg, MAX_EXPONENT)),
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        reverse = -(1 + (3 * vt / (v * math.e)) ** 3)
    return np.where(v >= -3 * vt, saturation * (forward - 1), saturation * reverse)


def pnjlim(vnew: float, vold: float, vt: float, vcrit: float) -> float:
    """Limitação da tensão de uma junção entre iterações (algoritmo do SPICE)."""
    if vnew > vcrit and abs(vnew - vold) > 2 * vt:
        if vold > 0:
            arg = 1 + (vnew - vold) / vt
            return vold + vt * math.log(arg) if arg > 0 else vcrit
        return vt * math.log(vnew / vt)
    return vnew


def semiconductor_devices(
    normalized: NormalizedCircuit, catalog: ComponentCatalog
) -> list[Semiconductor]:
    """Díodos, LEDs e transístores do circuito (pela ordem do documento)."""
    net_of = normalized.terminal_to_net
    devices: list[Semiconductor] = []
    for c in normalized.document.components:
        spec = catalog.get(c.type)
        if spec is None:
            continue
        model = spec.simulation_model
        p = c.properties
        if model == DIODE_MODEL:
            nets = tuple(net_of[c.terminal(pin)] for pin in ("anode", "cathode"))
            vt = DIODE_EMISSION_COEFFICIENT * THERMAL_VOLTAGE_V
            saturation = float(p["forwardCurrentA"]) / math.expm1(float(p["forwardVoltageV"]) / vt)
            devices.append(Semiconductor(c.id, model, nets, saturation, DIODE_EMISSION_COEFFICIENT))
        elif model in (BJT_NPN_MODEL, BJT_PNP_MODEL):
            nets = tuple(net_of[c.terminal(pin)] for pin in ("collector", "base", "emitter"))
            devices.append(
                Semiconductor(
                    c.id,
                    model,
                    nets,
                    float(p["saturationCurrentA"]),
                    polarity=1.0 if model == BJT_NPN_MODEL else -1.0,
                    beta_f=float(p["currentGain"]),
                )
            )
    return devices


class NewtonSolver:
    """Resolve `A·x + i(x) = b`, em que `A·x = b` é a parte linear do MNA e `i(x)` são as
    correntes que os semicondutores tiram das redes (linhas das redes em `index`)."""

    def __init__(
        self,
        devices: Sequence[Semiconductor],
        index: dict[str, int],
        size: int,
        linear_solve: Callable[[np.ndarray, np.ndarray], np.ndarray],
    ) -> None:
        self.devices = list(devices)
        self.size = size
        self.linear_solve = linear_solve
        self._junctions: list[np.ndarray] = []
        self._outputs: list[np.ndarray] = []
        for device in self.devices:
            selection = np.zeros((len(device.nets), size))
            for t, net in enumerate(device.nets):
                if net in index:
                    selection[t, index[net]] = 1.0
            self._junctions.append(device.junction_map() @ selection)
            self._outputs.append(selection.T @ device.output_map())

    def junctions(self, x: np.ndarray) -> list[np.ndarray]:
        return [d @ x for d in self._junctions]

    def solve(
        self,
        matrix: np.ndarray,
        rhs: np.ndarray,
        x0: np.ndarray,
        previous: list[np.ndarray] | None = None,
    ) -> tuple[np.ndarray, list[np.ndarray]]:
        """Solução e tensões das junções; lança `CircuitValidationError` (`NO_CONVERGENCE`) se
        não convergir em `MAX_ITERATIONS`."""
        x = x0
        limited_prev = previous if previous is not None else self.junctions(x0)
        for iteration in range(MAX_ITERATIONS):
            jacobian = matrix.copy()
            b = rhs.copy()
            limited_now: list[np.ndarray] = []
            clipped = False
            for device, d, o, vold, vnew in zip(
                self.devices,
                self._junctions,
                self._outputs,
                limited_prev,
                self.junctions(x),
                strict=True,
            ):
                vlim = np.array(
                    [
                        pnjlim(float(n), float(v), device.junction_vt, device.critical_voltage)
                        for n, v in zip(vnew, vold, strict=True)
                    ]
                )
                clipped |= bool(np.any(np.abs(vlim - vnew) > ABSOLUTE_TOLERANCE))
                outputs, gradient = device.evaluate(vlim)
                jacobian += o @ gradient @ d
                b -= o @ (outputs - gradient @ vlim)
                limited_now.append(vlim)
            x_new = self.linear_solve(jacobian, b)
            if not np.all(np.isfinite(x_new)):
                raise _no_convergence()
            converged = np.all(
                np.abs(x_new - x)
                <= RELATIVE_TOLERANCE * np.maximum(np.abs(x_new), np.abs(x)) + ABSOLUTE_TOLERANCE
            )
            x, limited_prev = x_new, limited_now
            if converged and not clipped and iteration > 0:
                return x, self.junctions(x)
        raise _no_convergence()

    def solve_with_source_stepping(
        self, matrix: np.ndarray, rhs: np.ndarray
    ) -> tuple[np.ndarray, list[np.ndarray]]:
        """Ponto de funcionamento a partir de x = 0; se não convergir, as fontes sobem em rampa
        (`source stepping`), partindo de cada solução para a seguinte."""
        x0 = np.zeros(self.size)
        try:
            return self.solve(matrix, rhs, x0)
        except CircuitValidationError as exc:
            if not _is_no_convergence(exc):
                raise
        scale, step = 0.0, 0.1
        x, junctions = self.solve(matrix, np.zeros(self.size), x0)
        while scale < 1.0:
            target = min(1.0, scale + step)
            try:
                x, junctions = self.solve(matrix, rhs * target, x, junctions)
            except CircuitValidationError as exc:
                if not _is_no_convergence(exc) or step / 2 < MIN_SOURCE_STEP:
                    raise
                step /= 2
                continue
            scale, step = target, min(step * 2, 0.25)
        return x, junctions


def semiconductor_results(
    device: Semiconductor, voltages: Sequence[np.ndarray], currents: Sequence[np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`voltageV`, `currentA`, `powerW` (aceita séries) a partir das tensões dos terminais e das
    correntes que entram neles: díodo (i_a,); transístor (i_c, i_b)."""
    if device.is_diode:
        voltage = np.asarray(voltages[0]) - np.asarray(voltages[1])
        current = np.asarray(currents[0])
        return voltage, current, voltage * current
    vc, vb, ve = (np.asarray(v) for v in voltages)
    ic, ib = (np.asarray(i) for i in currents)
    return vc - ve, ic, (vc - ve) * ic + (vb - ve) * ib


def _no_convergence() -> CircuitValidationError:
    return CircuitValidationError(
        [
            CircuitError(
                CircuitErrorCode.NO_CONVERGENCE,
                "O método de Newton não convergiu: o circuito com semicondutores não tem um "
                "ponto de funcionamento estável ou os valores são demasiado extremos.",
            )
        ]
    )


def _is_no_convergence(exc: CircuitValidationError) -> bool:
    return any(e.code is CircuitErrorCode.NO_CONVERGENCE for e in exc.errors)
