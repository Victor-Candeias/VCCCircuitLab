"""Tradutor do circuito canónico (já validado e normalizado) para uma netlist SPICE.

Nada do documento do utilizador entra no texto da netlist: os nós e os elementos têm nomes
gerados (`n1`, `R1`, `V2`, …) e os valores são `float` validados. Assim não há injeção de
diretivas SPICE (`.control`, `.include`, `shell`, …) através de ids, nomes ou propriedades.

Correspondência (mesmas estampas do solver MNA, `app/solver/mna.py`):

- redes com terra → nó `0`; restantes → `n1`, `n2`, … pela ordem das redes do documento;
- resistência e lâmpada (R = ratedVoltageV² / ratedPowerW) → elemento `R`;
- fonte de tensão → `V pos neg DC v`; interruptor fechado → `V a b DC 0` (dá a corrente);
- interruptor aberto → sem elemento;
- fonte de corrente → `I neg pos DC i`: no SPICE a corrente atravessa a fonte de `n+` para
  `n-`, logo sai pelo terminal `positive` para o circuito externo, como no MNA.
"""

from dataclasses import dataclass

from app.circuit.catalog import ComponentCatalog
from app.circuit.normalize import NormalizedCircuit
from app.solver.mna import Branch, BranchKind, dc_branches

GROUND_NODE = "0"
RAWFILE_NAME = "result.raw"


@dataclass(frozen=True)
class Netlist:
    text: str
    nodes: dict[str, str]
    """Rede do documento → nó SPICE."""
    branches: list[Branch]
    sources: dict[str, str]
    """Componente com corrente de ramo (fonte de tensão, interruptor fechado) → elemento `V`."""


def build_netlist(normalized: NormalizedCircuit, catalog: ComponentCatalog) -> Netlist:
    grounded, branches = dc_branches(normalized, catalog)
    nodes: dict[str, str] = {}
    for net in normalized.document.nets or []:
        if net.id in grounded:
            nodes[net.id] = GROUND_NODE
        else:
            nodes[net.id] = f"n{sum(n != GROUND_NODE for n in nodes.values()) + 1}"

    lines = ["* VCCCircuitLab: ponto de funcionamento DC"]
    sources: dict[str, str] = {}
    for k, br in enumerate(branches, start=1):
        a, b = nodes[br.a], nodes[br.b]
        if br.kind is BranchKind.CONDUCTANCE:
            lines.append(f"R{k} {a} {b} {_value(1 / br.value)}")
        elif br.kind is BranchKind.VOLTAGE:
            sources[br.component] = f"v{k}"
            lines.append(f"V{k} {a} {b} DC {_value(br.value)}")
        elif br.kind is BranchKind.CURRENT:
            lines.append(f"I{k} {b} {a} DC {_value(br.value)}")
        # BranchKind.OPEN (interruptor aberto): sem elemento.
    lines += [".control", "set filetype=ascii", "op", f"write {RAWFILE_NAME}", ".endc", ".end", ""]
    return Netlist("\n".join(lines), nodes, branches, sources)


def _value(value: float) -> str:
    return repr(float(value))
