"""Escolha do motor de simulação (variável de ambiente `SIMULATION_ENGINE`).

- `mna` (por omissão): solvers internos em NumPy (`app.solver.mna` para DC,
  `app.solver.transient` para a análise transitória);
- `ngspice`: ngspice em modo batch, isolado (`app.spice`); necessário para os componentes
  não lineares das fases seguintes.

Os dois motores devolvem o mesmo `DcResult`/`TransientResult`, logo a resposta da API não muda.
"""

import os
from enum import StrEnum

from app.circuit.catalog import ComponentCatalog
from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, simulate_dc
from app.solver.transient import TransientResult
from app.solver.transient import simulate_transient as simulate_transient_mna
from app.spice.engine import simulate_dc_ngspice, simulate_transient_ngspice
from app.spice.errors import SimulationEngineError


class SimulationEngine(StrEnum):
    MNA = "mna"
    NGSPICE = "ngspice"


def configured_engine() -> SimulationEngine:
    value = os.environ.get("SIMULATION_ENGINE", "").strip().lower() or SimulationEngine.MNA
    try:
        return SimulationEngine(value)
    except ValueError:
        raise SimulationEngineError(f"SIMULATION_ENGINE inválido: {value!r}") from None


def simulate(document: CircuitDocument, catalog: ComponentCatalog, *, timeout_s: float) -> DcResult:
    """Valida e simula com o motor configurado (erros como em `simulate_dc`/ngspice)."""
    if configured_engine() is SimulationEngine.NGSPICE:
        return simulate_dc_ngspice(document, catalog, timeout_s=timeout_s)
    return simulate_dc(document, catalog)


def simulate_transient(
    document: CircuitDocument,
    catalog: ComponentCatalog,
    *,
    stop_time_s: float,
    time_step_s: float,
    timeout_s: float,
) -> TransientResult:
    """Análise transitória com o motor configurado."""
    if configured_engine() is SimulationEngine.NGSPICE:
        return simulate_transient_ngspice(
            document,
            catalog,
            stop_time_s=stop_time_s,
            time_step_s=time_step_s,
            timeout_s=timeout_s,
        )
    return simulate_transient_mna(
        document,
        catalog,
        stop_time_s=stop_time_s,
        time_step_s=time_step_s,
        timeout_s=timeout_s,
    )
