"""Ponto de funcionamento DC calculado pelo ngspice, no mesmo formato do solver MNA."""

from app.circuit.catalog import ComponentCatalog, load_catalog
from app.circuit.validate import validate
from app.models.circuit import CircuitDocument
from app.solver.mna import DcResult, component_results
from app.spice.errors import SimulationEngineError, singular_matrix_error
from app.spice.netlist import GROUND_NODE, build_netlist
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
    except KeyError as exc:
        raise SimulationEngineError(f"rawfile sem a corrente de {exc}") from None
    results = component_results(netlist.branches, voltages, currents)
    return DcResult(node_voltages_v=voltages, components=results, warnings=report.warnings)
