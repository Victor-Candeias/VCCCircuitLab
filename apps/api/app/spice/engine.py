"""Ponto de funcionamento DC e análise transitória calculados pelo ngspice, no mesmo formato
dos solvers internos (`app.solver.mna`, `app.solver.transient`)."""

import math

import numpy as np

from app.circuit.catalog import ComponentCatalog, load_catalog
from app.circuit.validate import validate
from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, component_results, device_result, finish_dc
from app.solver.transient import (
    MIN_INTERNAL_STEPS,
    TransientResult,
    finish_transient,
    output_intervals,
    transient_result,
)
from app.spice.errors import SimulationEngineError, singular_matrix_error
from app.spice.netlist import GROUND_NODE, build_netlist, build_transient_netlist
from app.spice.runner import NgspiceConfig, run_ngspice


def simulate_dc_ngspice(
    document: CircuitDocument,
    catalog: ComponentCatalog | None = None,
    *,
    timeout_s: float,
    config: NgspiceConfig | None = None,
) -> DcResult:
    """Valida, traduz para SPICE, corre o ngspice e converte o resultado.

    Lança `CircuitValidationError` (circuito inválido ou singular), `SimulationTimeoutError`
    ou `SimulationEngineError` (ngspice indisponível ou com falha).
    """
    catalog = catalog or load_catalog()
    report = validate(document, catalog)
    normalized = report.raise_for_errors()
    netlist = build_netlist(normalized, catalog)
    raw = run_ngspice(netlist.text, timeout_s, config)

    voltages: dict[str, float] = {}
    for net, node in netlist.nodes.items():
        if node == GROUND_NODE:
            voltages[net] = 0.0
        elif node in raw.voltages:
            voltages[net] = raw.voltages[node] + 0.0
        else:
            # Rede sem nenhum elemento SPICE (ex.: só ligada a um interruptor aberto): o MNA
            # dá matriz singular; aqui o resultado seria igualmente indefinido.
            raise singular_matrix_error()
    try:
        currents = {c: raw.currents[element] for c, element in netlist.sources.items()}
        sensed = {
            c: [np.array(raw.currents[e]) for e in elements]
            for c, elements in netlist.device_sources.items()
        }
    except KeyError as exc:
        raise SimulationEngineError(f"rawfile sem a corrente de {exc}") from None
    results = component_results(netlist.branches, voltages, currents)
    for device in netlist.devices:
        results[device.component] = device_result(device, voltages, sensed[device.component])
    components, protection = finish_dc(results, normalized, catalog)
    return DcResult(
        node_voltages_v=voltages,
        components=components,
        warnings=(*report.warnings, *protection),
    )


def simulate_transient_ngspice(
    document: CircuitDocument,
    catalog: ComponentCatalog | None = None,
    *,
    stop_time_s: float,
    time_step_s: float,
    timeout_s: float,
    config: NgspiceConfig | None = None,
) -> TransientResult:
    """Análise transitória com o ngspice (erros como em `simulate_dc_ngspice`)."""
    catalog = catalog or load_catalog()
    report = validate(document, catalog, analysis="transient")
    normalized = report.raise_for_errors()
    intervals = output_intervals(stop_time_s, time_step_s)
    netlist = build_transient_netlist(
        normalized,
        catalog,
        stop_time_s=stop_time_s,
        time_step_s=stop_time_s / intervals,
        max_step_s=stop_time_s / (intervals * math.ceil(MIN_INTERNAL_STEPS / intervals)),
    )
    raw = run_ngspice(netlist.text, timeout_s, config)
    if not raw.time:
        raise SimulationEngineError("rawfile sem a variável time")

    times = np.array(raw.time)
    voltages: dict[str, np.ndarray] = {}
    for net, node in netlist.nodes.items():
        if node == GROUND_NODE:
            voltages[net] = np.zeros(len(times))
        elif node in raw.voltage_series:
            voltages[net] = np.array(raw.voltage_series[node])
        else:
            raise singular_matrix_error()
    try:
        currents = {c: np.array(raw.current_series[e]) for c, e in netlist.sources.items()}
        sensed = {
            c: [np.array(raw.current_series[e]) for e in elements]
            for c, elements in netlist.device_sources.items()
        }
    except KeyError as exc:
        raise SimulationEngineError(f"rawfile sem a corrente de {exc}") from None
    result = transient_result(
        times,
        voltages,
        netlist.branches,
        currents,
        report.warnings,
        netlist.devices,
        sensed,
        order=[c.id for c in normalized.document.components],
    )
    return finish_transient(result, normalized, catalog)
