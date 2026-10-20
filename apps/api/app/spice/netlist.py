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
  `n-`, logo sai pelo terminal `positive` para o circuito externo, como no MNA;
- condensador → aberto em DC; `C a b val IC=v0` na análise transitória (corrente `@cK[i]`);
- bobina → `V a b DC 0` em DC; `L a b val IC=i0` na análise transitória;
- voltímetro → sem elemento (aberto); amperímetro → `V a b DC 0` (dá a corrente);
  osciloscópio → sem elemento. As redes só ligadas a pontas de instrumentos não têm nó;
- díodo/LED → `D` com `.model DMj D(IS=… N=2)`; transístor → `Q` com
  `.model QMj NPN|PNP(IS=… BF=… BR=1)` (parâmetros de `app.solver.semiconductors`). Cada
  terminal medido tem em série uma fonte de 0 V (`VDj` no ânodo; `VQCj`/`VQBj` no coletor e na
  base) cuja corrente de ramo é a corrente que entra no terminal, em `op` e em `tran`.

A análise transitória (F2-02) usa `tran passo fim 0 passo_máx uic` (sem ponto de
funcionamento inicial: as fontes ligam-se em t = 0 e os elementos reativos partem de `IC=`),
com o método de Gear, e `linearize` para devolver pontos equidistantes.
"""

from dataclasses import dataclass, field

from app.circuit.catalog import ComponentCatalog
from app.circuit.normalize import NormalizedCircuit
from app.solver.mna import Branch, BranchKind, circuit_branches, dc_branches, defined_nets
from app.solver.semiconductors import Semiconductor, semiconductor_devices

GROUND_NODE = "0"
RAWFILE_NAME = "result.raw"


@dataclass(frozen=True)
class Netlist:
    text: str
    nodes: dict[str, str]
    """Rede do documento → nó SPICE."""
    branches: list[Branch]
    sources: dict[str, str]
    """Componente com corrente lida do rawfile (fonte de tensão, interruptor fechado e, na
    análise transitória, bobina e condensador) → elemento SPICE (minúsculas)."""
    devices: list[Semiconductor] = field(default_factory=list)
    device_sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Semicondutor → fontes de medida (minúsculas) das correntes que entram nos terminais:
    díodo (ânodo,); transístor (coletor, base)."""


def build_netlist(normalized: NormalizedCircuit, catalog: ComponentCatalog) -> Netlist:
    grounded, branches = dc_branches(normalized, catalog)
    nodes = _nodes(defined_nets(normalized, catalog), grounded)
    elements, sources = _elements(branches, nodes)
    devices = semiconductor_devices(normalized, catalog)
    device_lines, device_sources = _device_elements(devices, nodes)
    lines = ["* VCCCircuitLab: ponto de funcionamento DC", *elements, *device_lines]
    lines += [".control", "set filetype=ascii", "op", f"write {RAWFILE_NAME}", ".endc", ".end", ""]
    return Netlist("\n".join(lines), nodes, branches, sources, devices, device_sources)


def build_transient_netlist(
    normalized: NormalizedCircuit,
    catalog: ComponentCatalog,
    *,
    stop_time_s: float,
    time_step_s: float,
    max_step_s: float,
) -> Netlist:
    grounded, branches = circuit_branches(normalized, catalog)
    nodes = _nodes(defined_nets(normalized, catalog), grounded)
    elements, sources = _elements(branches, nodes)
    devices = semiconductor_devices(normalized, catalog)
    device_lines, device_sources = _device_elements(devices, nodes)
    device_currents = [f"@{e}[i]" for e in sources.values() if e.startswith("c")]
    lines = ["* VCCCircuitLab: analise transitoria", *elements, *device_lines]
    lines.append(".options method=gear")
    lines += [".control", "set filetype=ascii"]
    if device_currents:
        lines.append(f"save all {' '.join(device_currents)}")
    lines += [
        f"tran {_value(time_step_s)} {_value(stop_time_s)} 0 {_value(max_step_s)} uic",
        "linearize",
        f"write {RAWFILE_NAME}",
        ".endc",
        ".end",
        "",
    ]
    return Netlist("\n".join(lines), nodes, branches, sources, devices, device_sources)


def _nodes(nets: list[str], grounded: set[str]) -> dict[str, str]:
    nodes: dict[str, str] = {}
    for net in nets:
        if net in grounded:
            nodes[net] = GROUND_NODE
        else:
            nodes[net] = f"n{sum(n != GROUND_NODE for n in nodes.values()) + 1}"
    return nodes


def _elements(branches: list[Branch], nodes: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    lines: list[str] = []
    sources: dict[str, str] = {}
    for k, br in enumerate(branches, start=1):
        if br.kind is BranchKind.OPEN:
            continue  # interruptor aberto ou voltímetro: sem elemento
        a, b = nodes[br.a], nodes[br.b]
        if br.kind is BranchKind.CONDUCTANCE:
            lines.append(f"R{k} {a} {b} {_value(1 / br.value)}")
        elif br.kind is BranchKind.VOLTAGE:
            sources[br.component] = f"v{k}"
            lines.append(f"V{k} {a} {b} DC {_value(br.value)}")
        elif br.kind is BranchKind.CURRENT:
            lines.append(f"I{k} {b} {a} DC {_value(br.value)}")
        elif br.kind is BranchKind.CAPACITOR:
            sources[br.component] = f"c{k}"
            lines.append(f"C{k} {a} {b} {_value(br.value)} IC={_value(br.initial)}")
        elif br.kind is BranchKind.INDUCTOR:
            sources[br.component] = f"l{k}"
            lines.append(f"L{k} {a} {b} {_value(br.value)} IC={_value(br.initial)}")
    return lines, sources


def _device_elements(
    devices: list[Semiconductor], nodes: dict[str, str]
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    lines: list[str] = []
    sources: dict[str, tuple[str, ...]] = {}
    for j, device in enumerate(devices, start=1):
        if device.is_diode:
            anode, cathode = (nodes[net] for net in device.nets)
            sources[device.component] = (f"vd{j}",)
            lines += [
                f"VD{j} {anode} d{j} DC 0",
                f"D{j} d{j} {cathode} DM{j}",
                f".model DM{j} D(IS={_value(device.saturation_current)} "
                f"N={_value(device.emission)})",
            ]
        else:
            collector, base, emitter = (nodes[net] for net in device.nets)
            kind = "NPN" if device.polarity > 0 else "PNP"
            sources[device.component] = (f"vqc{j}", f"vqb{j}")
            lines += [
                f"VQC{j} {collector} qc{j} DC 0",
                f"VQB{j} {base} qb{j} DC 0",
                f"Q{j} qc{j} qb{j} {emitter} QM{j}",
                f".model QM{j} {kind}(IS={_value(device.saturation_current)} "
                f"BF={_value(device.beta_f)} BR={_value(device.beta_r)})",
            ]
    return lines, sources


def _value(value: float) -> str:
    return repr(float(value))
