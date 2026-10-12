"""Normalizador de redes: reconstrói as redes elétricas a partir de fios e junções.

`wires` + `junctions` são a fonte de verdade da conectividade; `nets` é derivado. O
normalizador une (union-find) os terminais `Componente.pino` e as junções ligados por fios.
Cada classe resultante com pelo menos um terminal é uma rede; terminais soltos ficam em redes
singleton. As junções só servem de ponte e não aparecem em `terminals`.

Se o documento trouxer `nets`, a partição tem de coincidir exatamente com a reconstruída
(caso contrário `NET_INCONSISTENT`) e os IDs fornecidos são preservados. Sem `nets`, os IDs
são gerados (`N1`, `N2`, ...) de forma determinística pela ordem dos componentes e dos pinos.
"""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass

from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError
from app.models.circuit import CircuitDocument, Net


class UnionFind[T: Hashable]:
    def __init__(self, items: Iterable[T] = ()) -> None:
        self._parent: dict[T, T] = {}
        self._rank: dict[T, int] = {}
        for item in items:
            self.add(item)

    def add(self, item: T) -> None:
        if item not in self._parent:
            self._parent[item] = item
            self._rank[item] = 0

    def find(self, item: T) -> T:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: T, b: T) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


@dataclass(frozen=True)
class NormalizedCircuit:
    document: CircuitDocument
    """Documento com `nets` preenchido (redes por ordem determinística)."""
    terminal_to_net: dict[str, str]
    """`Componente.pino` → ID da rede."""


def _node(kind: str, ident: str) -> tuple[str, str]:
    return (kind, ident)


def build_nets(document: CircuitDocument) -> list[list[str]]:
    """Partição dos terminais em redes, ordenada pela primeira ocorrência de cada terminal."""
    terminals = [c.terminal(p) for c in document.components for p in c.pins]
    junction_ids = [j.id for j in document.junctions or []]
    known_terminals = set(terminals)
    known_junctions = set(junction_ids)

    uf: UnionFind[tuple[str, str]] = UnionFind(
        [_node("t", t) for t in terminals] + [_node("j", j) for j in junction_ids]
    )
    errors: list[CircuitError] = []

    def resolve(wire_id: str, endpoint: str) -> tuple[str, str] | None:
        if "." in endpoint:
            if endpoint in known_terminals:
                return _node("t", endpoint)
            errors.append(
                CircuitError(
                    CircuitErrorCode.UNKNOWN_TERMINAL,
                    f"O fio {wire_id} liga ao terminal inexistente {endpoint}.",
                    (wire_id, endpoint),
                )
            )
            return None
        if endpoint in known_junctions:
            return _node("j", endpoint)
        errors.append(
            CircuitError(
                CircuitErrorCode.UNKNOWN_JUNCTION,
                f"O fio {wire_id} liga à junção inexistente {endpoint}.",
                (wire_id, endpoint),
            )
        )
        return None

    for wire in document.wires:
        a = resolve(wire.id, wire.from_)
        b = resolve(wire.id, wire.to)
        if a is not None and b is not None:
            uf.union(a, b)

    if errors:
        raise CircuitValidationError(errors)

    groups: dict[tuple[str, str], list[str]] = {}
    for terminal in terminals:
        groups.setdefault(uf.find(_node("t", terminal)), []).append(terminal)
    return list(groups.values())


def _check_declared_nets(
    declared: list[Net], computed: list[list[str]], known_terminals: set[str]
) -> dict[frozenset[str], str]:
    """Valida `nets` declarado contra a partição calculada; devolve conjunto → ID declarado."""
    errors: list[CircuitError] = []
    seen: dict[str, str] = {}
    for net in declared:
        for terminal in net.terminals:
            if terminal not in known_terminals:
                errors.append(
                    CircuitError(
                        CircuitErrorCode.UNKNOWN_TERMINAL,
                        f"A rede {net.id} referencia o terminal inexistente {terminal}.",
                        (net.id, terminal),
                    )
                )
            elif terminal in seen:
                errors.append(
                    CircuitError(
                        CircuitErrorCode.NET_INCONSISTENT,
                        f"O terminal {terminal} aparece nas redes {seen[terminal]} e {net.id}.",
                        (seen[terminal], net.id, terminal),
                    )
                )
            else:
                seen[terminal] = net.id
    if errors:
        raise CircuitValidationError(errors)

    by_set = {frozenset(n.terminals): n.id for n in declared}
    computed_sets = {frozenset(group) for group in computed}
    for net in declared:
        if frozenset(net.terminals) not in computed_sets:
            errors.append(
                CircuitError(
                    CircuitErrorCode.NET_INCONSISTENT,
                    f"A rede {net.id} não corresponde à ligação definida pelos fios.",
                    (net.id,),
                )
            )
    for group in computed:
        if frozenset(group) not in by_set:
            errors.append(
                CircuitError(
                    CircuitErrorCode.NET_INCONSISTENT,
                    "Os terminais ligados por fios "
                    f"{', '.join(group)} não formam uma rede declarada em nets.",
                    tuple(group),
                )
            )
    if errors:
        raise CircuitValidationError(errors)
    return by_set


def _generate_ids(count: int, taken: set[str]) -> list[str]:
    ids: list[str] = []
    n = 1
    while len(ids) < count:
        candidate = f"N{n}"
        if candidate not in taken:
            ids.append(candidate)
        n += 1
    return ids


def normalize(document: CircuitDocument) -> NormalizedCircuit:
    """Reconstrói `nets` a partir de `wires`/`junctions`.

    Lança `CircuitValidationError` com `UNKNOWN_TERMINAL`, `UNKNOWN_JUNCTION` ou
    `NET_INCONSISTENT`.
    """
    computed = build_nets(document)
    known_terminals = {t for group in computed for t in group}

    if document.nets is not None:
        declared_ids = _check_declared_nets(document.nets, computed, known_terminals)
        net_ids = [declared_ids[frozenset(group)] for group in computed]
    else:
        # Evita colidir com IDs de componentes, junções ou fios (os IDs partilham namespace).
        taken = {c.id for c in document.components}
        taken |= {j.id for j in document.junctions or []}
        taken |= {w.id for w in document.wires}
        net_ids = _generate_ids(len(computed), taken)

    nets = [
        Net(id=net_id, terminals=group) for net_id, group in zip(net_ids, computed, strict=True)
    ]
    terminal_to_net = {t: net.id for net in nets for t in net.terminals}
    return NormalizedCircuit(
        document=document.model_copy(update={"nets": nets}),
        terminal_to_net=terminal_to_net,
    )
