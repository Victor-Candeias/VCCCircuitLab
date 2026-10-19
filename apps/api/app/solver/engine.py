"""Escolha do motor de simulação DC (variável de ambiente `SIMULATION_ENGINE`).

- `mna` (por omissão): solver MNA interno em NumPy (`app.solver.mna`);
- `ngspice`: ngspice em modo batch, isolado (`app.spice`); necessário para os componentes
  não lineares e as análises transitórias das fases seguintes.

Os dois motores devolvem o mesmo `DcResult`, logo a resposta da API não muda.
"""

import os
from enum import StrEnum

from app.circuit.catalog import ComponentCatalog
from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, simulate_dc
from app.spice.engine import simulate_dc_ngspice
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
