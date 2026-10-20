"""Validador topológico e de valores do circuito (corre antes do solver).

`validate(doc)` recolhe numa só passagem todos os erros e avisos estruturados, por fases:

1. Documento: IDs únicos em todo o documento e fios com extremidades distintas.
2. Componentes vs catálogo: tipo, modelo elétrico suportado, pinos e propriedades (tipo e
   limites; zero, negativos e valores não finitos são rejeitados conforme o catálogo).
3. Normalização das redes (`app.circuit.normalize`), se os IDs forem únicos.
4. Topologia, se todos os componentes forem interpretáveis: pinos desligados (aviso), terra
   ausente, malhas de impedância nula com fontes de tensão ideais e grupos de redes sem caminho
   condutor até à terra (nós flutuantes ou fontes de corrente sem caminho fechado).

Na topologia, cada rede é um nó e a terra liga a sua rede a um nó de referência virtual.
Resistências e lâmpadas são condutoras; interruptores fechados, fontes de tensão e terra têm
impedância nula; interruptores abertos e fontes de corrente não fixam potencial.

Os condensadores e as bobinas (F2-02) dependem da análise (`analysis`): em DC o condensador é
um circuito aberto e a bobina tem impedância nula (como um interruptor fechado); na análise
transitória ambos são condutores (modelos companheiros), pelo que malhas fonte de
tensão–condensador e cortes fonte de corrente–bobina são permitidos.

Os semicondutores (F2-04) são condutores entre os terminais de cada junção (díodo:
ânodo–cátodo; transístor: base–emissor e base–coletor), mesmo em inversa (condutância `GMIN`).

Rede 230/400 V e proteções (F2-07): a rede CA é uma fonte de tensão ideal com o valor eficaz,
só na análise DC e só com cargas resistivas (erro `UNSUPPORTED_ANALYSIS` caso contrário), e
gera sempre o aviso de segurança `MAINS_VOLTAGE` (mais `MISSING_PROTECTION` sem disjuntor). O
disjuntor é um interruptor; o comutador liga o comum ao contacto ativo (o inativo é um terminal
em aberto, como uma ponta de voltímetro); o diferencial tem um contacto por polo (`contacts`).
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

from app.circuit.catalog import ComponentCatalog, ComponentSpec, load_catalog
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import NormalizedCircuit, UnionFind, normalize
from app.models.circuit import CircuitDocument, Component

Code = CircuitErrorCode

RESISTIVE_MODELS = frozenset({"resistor", "resistive_lamp"})
SWITCH_MODEL = "ideal_switch"
BREAKER_MODEL = "circuit_breaker"
#: Interruptores de dois terminais com estado `closed`.
SWITCH_MODELS = frozenset({SWITCH_MODEL, BREAKER_MODEL})
#: Componentes com vários contactos (F2-07): um ramo por contacto fechado (`contacts`).
CHANGEOVER_MODEL = "changeover_switch"
RCD_MODEL = "rcd"
MULTI_CONTACT_MODELS = frozenset({CHANGEOVER_MODEL, RCD_MODEL})
VOLTAGE_SOURCE_MODEL = "dc_voltage_source"
#: Rede CA (F2-07): fonte de tensão ideal com o valor eficaz (RMS), só na análise DC.
AC_SOURCE_MODEL = "ac_voltage_source"
CURRENT_SOURCE_MODEL = "dc_current_source"
GROUND_MODEL = "ground"
CAPACITOR_MODEL = "capacitor"
INDUCTOR_MODEL = "inductor"
REACTIVE_MODELS = frozenset({CAPACITOR_MODEL, INDUCTOR_MODEL})
VOLTMETER_MODEL = "voltmeter"
AMMETER_MODEL = "ammeter"
OSCILLOSCOPE_MODEL = "oscilloscope"
#: Instrumentos de impedância infinita: os seus terminais não conduzem nem fixam potencial.
PROBE_MODELS = frozenset({VOLTMETER_MODEL, OSCILLOSCOPE_MODEL})
DIODE_MODEL = "diode"
BJT_NPN_MODEL = "bjt_npn"
BJT_PNP_MODEL = "bjt_pnp"
#: Semicondutores (F2-04): resolvidos pelo método de Newton (`app/solver/semiconductors.py`).
SEMICONDUCTOR_MODELS = frozenset({DIODE_MODEL, BJT_NPN_MODEL, BJT_PNP_MODEL})
TWO_TERMINAL_MODELS = (
    RESISTIVE_MODELS
    | REACTIVE_MODELS
    | SWITCH_MODELS
    | {
        VOLTMETER_MODEL,
        AMMETER_MODEL,
        VOLTAGE_SOURCE_MODEL,
        AC_SOURCE_MODEL,
        CURRENT_SOURCE_MODEL,
    }
)
SUPPORTED_MODELS = (
    TWO_TERMINAL_MODELS
    | SEMICONDUCTOR_MODELS
    | MULTI_CONTACT_MODELS
    | {GROUND_MODEL, OSCILLOSCOPE_MODEL}
)
#: Modelos que, com a rede CA, invalidam a equivalência em valores eficazes da análise DC.
NON_RESISTIVE_MODELS = (
    REACTIVE_MODELS
    | SEMICONDUCTOR_MODELS
    | {VOLTAGE_SOURCE_MODEL, CURRENT_SOURCE_MODEL, OSCILLOSCOPE_MODEL}
)

#: Separador entre o ID do componente e o polo (`ID1:L`) nos ramos dos componentes com vários
#: contactos. Não é permitido em IDs, logo não colide com outros componentes.
POLE_SEPARATOR = ":"

#: Pares de pinos de cada junção dos semicondutores.
_JUNCTIONS = {
    DIODE_MODEL: (("anode", "cathode"),),
    BJT_NPN_MODEL: (("base", "emitter"), ("base", "collector")),
    BJT_PNP_MODEL: (("base", "emitter"), ("base", "collector")),
}

#: Nó virtual de referência (0 V). O `\0` não é permitido em IDs, logo não colide com redes.
REFERENCE = "\0GND"

#: (componente, nó, nó)
Edge = tuple[str, str, str]

#: Análise para a qual o circuito é validado (`export`: netlist SPICE, regras da transitória
#: mas aceita a rede CA).
Analysis = Literal["dc", "transient", "export"]


def pole_key(component_id: str, pole: str) -> str:
    return f"{component_id}{POLE_SEPARATOR}{pole}"


def component_of(key: str) -> str:
    """ID do componente de um ramo (sem o polo)."""
    return key.split(POLE_SEPARATOR, 1)[0]


@dataclass(frozen=True)
class Contact:
    """Contacto de um componente com vários contactos (F2-07), entre os pinos `a` e `b`."""

    key: str
    """Chave do ramo/resultado: o ID do componente ou `pole_key(ID, polo)`."""
    a: str
    b: str
    closed: bool


def contacts(model: str | None, c: Component) -> list[Contact]:
    """Contactos do comutador (só o ativo, sempre fechado) e do diferencial (fase e neutro)."""
    if model == CHANGEOVER_MODEL:
        return [Contact(c.id, "common", _active_contact(c), True)]
    if model == RCD_MODEL:
        closed = c.properties.get("closed") is True
        return [
            Contact(pole_key(c.id, "L"), "line_in", "line_out", closed),
            Contact(pole_key(c.id, "N"), "neutral_in", "neutral_out", closed),
        ]
    return []


def open_terminals(model: str | None, c: Component) -> list[str]:
    """Terminais em aberto que não fixam potencial: o contacto inativo do comutador."""
    if model == CHANGEOVER_MODEL:
        inactive = "l1" if _active_contact(c) == "l2" else "l2"
        return [c.terminal(inactive)]
    return []


def _active_contact(c: Component) -> str:
    return "l2" if c.properties.get("toL2") is True else "l1"


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[CircuitError, ...] = ()
    warnings: tuple[CircuitError, ...] = ()
    normalized: NormalizedCircuit | None = None
    """Circuito normalizado, se a normalização das redes foi possível."""

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> NormalizedCircuit:
        """Lança `CircuitValidationError` se houver erros; senão devolve o circuito normalizado."""
        if self.errors:
            raise CircuitValidationError(list(self.errors))
        if self.normalized is None:  # pragma: no cover - sem erros a normalização correu sempre
            raise RuntimeError("relatório sem erros e sem circuito normalizado")
        return self.normalized


def validate(
    document: CircuitDocument,
    catalog: ComponentCatalog | None = None,
    analysis: Analysis = "dc",
) -> ValidationReport:
    catalog = catalog or load_catalog()
    errors = [*_check_ids(document), *_check_wires(document)]
    component_errors, specs = _check_components(document, catalog)
    errors += component_errors
    mains_errors, mains_warnings = _check_mains(document, specs, analysis)
    errors += mains_errors

    if any(e.code is Code.DUPLICATE_ID for e in errors):
        return ValidationReport(errors=tuple(errors))
    try:
        normalized = normalize(document)
    except CircuitValidationError as exc:
        return ValidationReport(errors=(*errors, *exc.errors))

    warnings = [*_check_unconnected_pins(normalized), *mains_warnings]
    if len(specs) == len(document.components):
        errors += _check_topology(normalized, specs, analysis)
    return ValidationReport(errors=tuple(errors), warnings=tuple(warnings), normalized=normalized)


def _check_ids(document: CircuitDocument) -> list[CircuitError]:
    kinds: dict[str, list[str]] = {}
    groups = (
        ("componente", document.components),
        ("junção", document.junctions or []),
        ("fio", document.wires),
        ("rede", document.nets or []),
    )
    for kind, items in groups:
        for item in items:
            kinds.setdefault(item.id, []).append(kind)
    return [
        CircuitError(
            Code.DUPLICATE_ID,
            f"O ID {ident} é usado por {len(found)} elementos ({', '.join(found)}).",
            (ident,),
        )
        for ident, found in kinds.items()
        if len(found) > 1
    ]


def _check_wires(document: CircuitDocument) -> list[CircuitError]:
    return [
        CircuitError(
            Code.SELF_LOOP_WIRE,
            f"O fio {w.id} começa e acaba em {w.to}.",
            (w.id, w.to),
        )
        for w in document.wires
        if w.from_ == w.to
    ]


def _check_components(
    document: CircuitDocument, catalog: ComponentCatalog
) -> tuple[list[CircuitError], dict[str, ComponentSpec]]:
    """Erros por componente e especificações dos componentes interpretáveis pela topologia."""
    errors: list[CircuitError] = []
    specs: dict[str, ComponentSpec] = {}
    for c in document.components:
        spec = catalog.get(c.type)
        if spec is None:
            errors.append(
                CircuitError(
                    Code.UNKNOWN_COMPONENT_TYPE,
                    f"O componente {c.id} tem o tipo desconhecido {c.type}.",
                    (c.id,),
                )
            )
            continue
        structural = _check_model_and_pins(c, spec)
        errors += structural
        errors += _check_properties(c, spec)
        if not structural:
            specs[c.id] = spec
    return errors, specs


def _check_model_and_pins(c: Component, spec: ComponentSpec) -> list[CircuitError]:
    errors: list[CircuitError] = []
    if spec.simulation_model not in SUPPORTED_MODELS:
        errors.append(
            CircuitError(
                Code.UNSUPPORTED_MODEL,
                f"O componente {c.id} ({spec.label}) não é suportado pelo solver.",
                (c.id,),
            )
        )
    errors += [
        CircuitError(
            Code.UNKNOWN_PIN,
            f"O componente {c.id} ({c.type}) não tem o pino {pin}.",
            (c.id, c.terminal(pin)),
        )
        for pin in c.pins
        if pin not in spec.pins
    ]
    errors += [
        CircuitError(
            Code.MISSING_PIN,
            f"Falta o pino {pin} no componente {c.id} ({c.type}).",
            (c.id, c.terminal(pin)),
        )
        for pin in spec.pins
        if pin not in c.pins
    ]
    return errors


def _check_properties(c: Component, spec: ComponentSpec) -> list[CircuitError]:
    errors: list[CircuitError] = []
    for name, value in c.properties.items():
        prop = spec.properties.get(name)
        if prop is None:
            errors.append(
                CircuitError(
                    Code.UNKNOWN_PROPERTY,
                    f"O componente {c.id} ({c.type}) não tem a propriedade {name}.",
                    (c.id,),
                )
            )
        elif not prop.type_matches(value):
            expected = "booleano" if prop.type == "boolean" else "número"
            errors.append(
                CircuitError(
                    Code.INVALID_PROPERTY_TYPE,
                    f"A propriedade {name} de {c.id} tem de ser um {expected}.",
                    (c.id,),
                )
            )
        elif prop.type == "number" and (violation := prop.range_violation(float(value))):
            errors.append(
                CircuitError(
                    Code.INVALID_VALUE,
                    f"A propriedade {name} de {c.id} ({prop.format(value)}) {violation}.",
                    (c.id,),
                )
            )
    errors += [
        CircuitError(
            Code.MISSING_PROPERTY,
            f"Falta a propriedade {name} no componente {c.id} ({c.type}).",
            (c.id,),
        )
        for name in spec.properties
        if name not in c.properties
    ]
    return errors


def _check_mains(
    document: CircuitDocument, specs: dict[str, ComponentSpec], analysis: Analysis
) -> tuple[list[CircuitError], list[CircuitError]]:
    """Rede CA (F2-07): análise e componentes suportados (erros) e avisos de segurança."""
    sources = [c for c in document.components if _model(specs, c) == AC_SOURCE_MODEL]
    if not sources:
        return [], []
    ids = tuple(c.id for c in sources)
    names = ", ".join(f"{c.id}: {_format(specs[c.id], c, 'voltageV')}" for c in sources)
    errors: list[CircuitError] = []
    if analysis == "transient":
        errors.append(
            CircuitError(
                Code.UNSUPPORTED_ANALYSIS,
                f"A rede CA ({', '.join(ids)}) não é suportada na análise transitória: use a "
                "análise DC, que dá os valores eficazes (RMS) equivalentes com cargas resistivas.",
                ids,
            )
        )
    elif analysis == "dc":
        others = tuple(
            c.id for c in document.components if _model(specs, c) in NON_RESISTIVE_MODELS
        )
        if others:
            errors.append(
                CircuitError(
                    Code.UNSUPPORTED_ANALYSIS,
                    "Com a rede CA, a análise DC só dá valores eficazes corretos com cargas "
                    "resistivas: condensadores, bobinas, semicondutores, fontes DC e "
                    f"osciloscópios não são suportados ({', '.join(others)}).",
                    (*ids, *others),
                )
            )
    warnings = [
        CircuitError(
            Code.MAINS_VOLTAGE,
            f"Tensão da rede ({names}): perigo de morte numa instalação real. Simulação "
            "didática em valores eficazes, sem certificação: não substitui o projeto nem a "
            "verificação por um técnico qualificado (RTIEBT). Nunca trabalhe com tensão.",
            ids,
        )
    ]
    if not any(_model(specs, c) == BREAKER_MODEL for c in document.components):
        warnings.append(
            CircuitError(
                Code.MISSING_PROTECTION,
                "O circuito de rede não tem disjuntor: numa instalação real cada circuito tem "
                "proteção contra sobreintensidades (e diferencial de 30 mA onde é obrigatório).",
                ids,
            )
        )
    return errors, warnings


def _format(spec: ComponentSpec, c: Component, name: str) -> str:
    value = c.properties.get(name)
    prop = spec.properties.get(name)
    return prop.format(value) if prop is not None else str(value)


def _model(specs: dict[str, ComponentSpec], c: Component) -> str | None:
    spec = specs.get(c.id)
    return spec.simulation_model if spec is not None else None


def _check_unconnected_pins(normalized: NormalizedCircuit) -> list[CircuitError]:
    return [
        CircuitError(
            Code.UNCONNECTED_PIN,
            f"O terminal {net.terminals[0]} não está ligado a nada.",
            (net.terminals[0],),
        )
        for net in normalized.document.nets or []
        if len(net.terminals) == 1
    ]


def _check_topology(
    normalized: NormalizedCircuit, specs: dict[str, ComponentSpec], analysis: Analysis
) -> list[CircuitError]:
    document = normalized.document
    nets = document.nets or []
    net_of = normalized.terminal_to_net

    has_ground = False
    # Impedância nula sem fonte: terra, interruptores fechados, amperímetros, bobinas em DC.
    zero: list[Edge] = []
    voltage_sources: list[Edge] = []
    resistive: list[Edge] = []
    current_sources: list[Edge] = []
    probe_terminals: set[str] = set()
    for c in document.components:
        spec = specs[c.id]
        model = spec.simulation_model
        if model in PROBE_MODELS:
            probe_terminals.update(c.terminal(pin) for pin in spec.pins)
            continue
        if model == GROUND_MODEL:
            has_ground = True
            zero += [(c.id, net_of[c.terminal(pin)], REFERENCE) for pin in spec.pins]
            continue
        if model in SEMICONDUCTOR_MODELS:
            resistive += [
                (c.id, net_of[c.terminal(a)], net_of[c.terminal(b)]) for a, b in _JUNCTIONS[model]
            ]
            continue
        if model in MULTI_CONTACT_MODELS:
            zero += [
                (c.id, net_of[c.terminal(k.a)], net_of[c.terminal(k.b)])
                for k in contacts(model, c)
                if k.closed
            ]
            probe_terminals.update(open_terminals(model, c))
            continue
        if model not in TWO_TERMINAL_MODELS or len(spec.pins) != 2:
            continue
        edge = (c.id, net_of[c.terminal(spec.pins[0])], net_of[c.terminal(spec.pins[1])])
        if model in SWITCH_MODELS:
            if c.properties.get("closed") is True:
                zero.append(edge)
        elif model == AMMETER_MODEL:
            zero.append(edge)
        elif model in REACTIVE_MODELS and analysis == "dc":
            if model == INDUCTOR_MODEL:
                zero.append(edge)
        elif model in (VOLTAGE_SOURCE_MODEL, AC_SOURCE_MODEL):
            voltage_sources.append(edge)
        elif model == CURRENT_SOURCE_MODEL:
            current_sources.append(edge)
        else:
            resistive.append(edge)

    nodes = [*(n.id for n in nets), REFERENCE]
    errors = _check_voltage_loops(nodes, zero, voltage_sources)
    if not has_ground:
        errors.append(
            CircuitError(
                Code.MISSING_GROUND,
                "O circuito não tem terra (referência de 0 V): adicione um componente de terra.",
            )
        )
        return errors

    connected = UnionFind(nodes)
    for _, a, b in (*zero, *voltage_sources, *resistive):
        connected.union(a, b)
    reference = connected.find(REFERENCE)
    floating: dict[str, list[str]] = {}
    for net in nets:
        root = connected.find(net.id)
        # Redes só com pontas de instrumentos: a leitura fica indefinida, mas não é um erro.
        if root != reference and not probe_terminals.issuperset(net.terminals):
            floating.setdefault(root, []).append(net.id)

    terminals_of = {n.id: n.terminals for n in nets}
    for group in floating.values():
        members = set(group)
        terminals = [t for net_id in group for t in terminals_of[net_id]]
        sources = [cid for cid, a, b in current_sources if a in members or b in members]
        if sources:
            errors.append(
                CircuitError(
                    Code.CURRENT_SOURCE_CUTSET,
                    f"Fonte de corrente sem caminho fechado ({', '.join(sources)}): "
                    f"{', '.join(terminals)} só se ligam à terra através de fontes de corrente "
                    "(fonte em aberto ou fontes em série).",
                    (*sources, *group),
                )
            )
        else:
            errors.append(
                CircuitError(
                    Code.FLOATING_NET,
                    f"Sem caminho condutor até à terra (potencial indefinido): "
                    f"{', '.join(terminals)}.",
                    (*group, *terminals),
                )
            )
    return errors


def _check_voltage_loops(
    nodes: list[str], zero: list[Edge], voltage_sources: list[Edge]
) -> list[CircuitError]:
    """Malhas só de impedância nula que incluem fontes de tensão ideais.

    As arestas sem fonte entram primeiro; assim, existe uma malha com fonte se e só se alguma
    fonte fecha um ciclo na floresta. Malhas só de interruptores/terra não são conflito.
    """
    forest = UnionFind(nodes)
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    errors: list[CircuitError] = []

    def add(component: str, a: str, b: str) -> None:
        forest.union(a, b)
        adjacency[a].append((b, component))
        adjacency[b].append((a, component))

    for component, a, b in zero:
        if forest.find(a) != forest.find(b):
            add(component, a, b)
    for component, a, b in voltage_sources:
        if forest.find(a) != forest.find(b):
            add(component, a, b)
            continue
        loop = [*_path(adjacency, a, b), component]
        if len(loop) == 1:
            message = f"A fonte de tensão {component} está em curto-circuito."
        else:
            message = (
                f"A fonte de tensão {component} está em curto-circuito ou em paralelo com outra "
                f"fonte ideal (malha sem impedância: {', '.join(loop)})."
            )
        errors.append(CircuitError(Code.VOLTAGE_SOURCE_LOOP, message, tuple(loop)))
    return errors


def _path(adjacency: dict[str, list[tuple[str, str]]], start: str, goal: str) -> list[str]:
    """Componentes no caminho (único) entre dois nós da floresta."""
    previous: dict[str, tuple[str, str] | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            break
        for neighbour, component in adjacency[node]:
            if neighbour not in previous:
                previous[neighbour] = (node, component)
                queue.append(neighbour)
    components: list[str] = []
    node = goal
    while (step := previous[node]) is not None:
        node, component = step
        components.append(component)
    return components[::-1]
