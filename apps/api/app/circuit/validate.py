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
"""

from collections import defaultdict, deque
from dataclasses import dataclass

from app.circuit.catalog import ComponentCatalog, ComponentSpec, load_catalog
from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.circuit.normalize import NormalizedCircuit, UnionFind, normalize
from app.models.circuit import CircuitDocument, Component

Code = CircuitErrorCode

RESISTIVE_MODELS = frozenset({"resistor", "resistive_lamp"})
SWITCH_MODEL = "ideal_switch"
VOLTAGE_SOURCE_MODEL = "dc_voltage_source"
CURRENT_SOURCE_MODEL = "dc_current_source"
GROUND_MODEL = "ground"
TWO_TERMINAL_MODELS = RESISTIVE_MODELS | {SWITCH_MODEL, VOLTAGE_SOURCE_MODEL, CURRENT_SOURCE_MODEL}
SUPPORTED_MODELS = TWO_TERMINAL_MODELS | {GROUND_MODEL}

#: Nó virtual de referência (0 V). O `\0` não é permitido em IDs, logo não colide com redes.
REFERENCE = "\0GND"

#: (componente, nó, nó)
Edge = tuple[str, str, str]


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
    document: CircuitDocument, catalog: ComponentCatalog | None = None
) -> ValidationReport:
    catalog = catalog or load_catalog()
    errors = [*_check_ids(document), *_check_wires(document)]
    component_errors, specs = _check_components(document, catalog)
    errors += component_errors

    if any(e.code is Code.DUPLICATE_ID for e in errors):
        return ValidationReport(errors=tuple(errors))
    try:
        normalized = normalize(document)
    except CircuitValidationError as exc:
        return ValidationReport(errors=(*errors, *exc.errors))

    warnings = _check_unconnected_pins(normalized)
    if len(specs) == len(document.components):
        errors += _check_topology(normalized, specs)
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
    normalized: NormalizedCircuit, specs: dict[str, ComponentSpec]
) -> list[CircuitError]:
    document = normalized.document
    nets = document.nets or []
    net_of = normalized.terminal_to_net

    has_ground = False
    zero: list[Edge] = []  # impedância nula sem fonte: terra e interruptores fechados
    voltage_sources: list[Edge] = []
    resistive: list[Edge] = []
    current_sources: list[Edge] = []
    for c in document.components:
        spec = specs[c.id]
        model = spec.simulation_model
        if model == GROUND_MODEL:
            has_ground = True
            zero += [(c.id, net_of[c.terminal(pin)], REFERENCE) for pin in spec.pins]
            continue
        if model not in TWO_TERMINAL_MODELS or len(spec.pins) != 2:
            continue
        edge = (c.id, net_of[c.terminal(spec.pins[0])], net_of[c.terminal(spec.pins[1])])
        if model == SWITCH_MODEL:
            if c.properties.get("closed") is True:
                zero.append(edge)
        elif model == VOLTAGE_SOURCE_MODEL:
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
        if root != reference:
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
