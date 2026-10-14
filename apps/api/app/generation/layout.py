"""Layout ortogonal dos circuitos gerados (E3-03).

Usa o catálogo de componentes (`app.circuit.catalog`, partilhado com o validador e com o
editor) para alinhar os pinos à grelha, substituindo a grelha linear provisória da E3-01
(ver `Docs/arquitetura_simulador_circuitos.md` §6.1 passo 5).

Dois esquemas, reutilizados pelos templates (`app.generation.templates`):

- `chain_loop`: a fonte fica à esquerda, na vertical (`positive` em cima, `negative` em
  baixo); os componentes da cadeia ficam em fila, alinhados ao carril superior (a altura de
  `positive`). O fecho da malha, à direita, desce ao carril inferior e volta a `negative` — um
  canto explícito (`waypoints`), porque o traçado automático do editor liga sempre na
  horizontal primeiro (`apps/web/src/editor/wiring.ts:routeTo`) e, sem este ponto, cruzaria os
  restantes componentes da fila. Usado por `series_dc`, `voltage_divider` e `switch_circuit`.
- `parallel_ladder`: a fonte fica à esquerda; cada ramo fica na vertical, entre o carril
  superior e o inferior, lado a lado — os fios ficam todos alinhados aos carris, sem
  waypoints. Usado por `parallel_dc`.

Em ambos, a terra fica por baixo da fonte, ligada a `negative` por um fio vertical.
"""

from app.circuit.catalog import load_catalog
from app.models.circuit import CircuitDocument, Component, Point, Wire

_CATALOG = load_catalog()
_GRID = _CATALOG.grid_size

_SOURCE_X = 4 * _GRID  # 80: margem esquerda até à fonte.
_STEP_X = 8 * _GRID  # 160: espaço horizontal entre elementos da fila/ramos.
_SOURCE_CENTER_Y = 10 * _GRID  # 200: altura do centro da fonte.
_GROUND_GAP = 3 * _GRID  # 60: de `negative` ao símbolo de terra.


def _rotate(dx: float, dy: float, rotation: int) -> tuple[float, float]:
    """Deslocamento `(dx, dy)` rodado (sentido horário, eixo y para baixo); tem de produzir o
    mesmo resultado que `apps/web/src/editor/wiring.ts:rotateOffset`, para que a posição
    gerada coincida com a que o editor calcula ao desenhar o componente."""
    if rotation == 90:
        return (-dy, dx)
    if rotation == 180:
        return (-dx, -dy)
    if rotation == 270:
        return (dy, -dx)
    return (dx, dy)


def _pin_point(component: Component, pin: str) -> Point:
    spec = _CATALOG.get(component.type)
    if spec is None or pin not in spec.pin_positions:
        raise KeyError(f"{component.type}.{pin}")
    dx, dy = _rotate(*spec.pin_positions[pin], component.rotation)
    return Point(x=component.position.x + dx, y=component.position.y + dy)


def _half_height(component_type: str, rotation: int) -> float:
    """Metade da extensão vertical do símbolo, à rotação dada (as larguras/alturas trocam a
    90°/270°)."""
    spec = _CATALOG.get(component_type)
    if spec is None:
        raise KeyError(component_type)
    width, height = spec.size
    return (width if rotation in (90, 270) else height) / 2


def _place(component: Component, x: float, y: float, rotation: int) -> Component:
    return component.model_copy(update={"position": Point(x=x, y=y), "rotation": rotation})


def _wire(wid: str, source: str, target: str, waypoints: list[Point] | None = None) -> Wire:
    return Wire(id=wid, from_=source, to=target, waypoints=waypoints or [])


def _document(
    template: str, name: str, components: list[Component], wires: list[Wire]
) -> CircuitDocument:
    return CircuitDocument(
        schema_version="1.0",
        id=f"generated-{template}",
        name=name,
        units="SI",
        components=components,
        wires=wires,
    )


def chain_loop(
    template: str, name: str, source: Component, chain: list[Component], ground: Component
) -> CircuitDocument:
    """Fonte + `chain` em série, com terra em `negative` (ver docstring do módulo)."""
    source = _place(source, _SOURCE_X, _SOURCE_CENTER_Y, rotation=0)
    top_rail = _pin_point(source, "positive").y
    bottom_rail = _pin_point(source, "negative").y

    parts = [
        _place(part, _SOURCE_X + _STEP_X * i, top_rail, rotation=0)
        for i, part in enumerate(chain, start=1)
    ]

    wires = [_wire("W1", source.terminal("positive"), parts[0].terminal("a"))]
    for i in range(len(parts) - 1):
        wires.append(_wire(f"W{i + 2}", parts[i].terminal("b"), parts[i + 1].terminal("a")))

    last_pin = _pin_point(parts[-1], "b")
    corner = Point(x=last_pin.x, y=bottom_rail)
    wires.append(
        _wire(
            f"W{len(parts) + 1}",
            parts[-1].terminal("b"),
            source.terminal("negative"),
            waypoints=[corner],
        )
    )

    ground = _place(ground, _SOURCE_X, bottom_rail + _GROUND_GAP, rotation=0)
    wires.append(_wire(f"W{len(parts) + 2}", ground.terminal("gnd"), source.terminal("negative")))

    return _document(template, name, [source, *parts, ground], wires)


def parallel_ladder(
    template: str, name: str, source: Component, branches: list[Component], ground: Component
) -> CircuitDocument:
    """Fonte + `branches` em paralelo, com terra em `negative` (ver docstring do módulo)."""
    source = _place(source, _SOURCE_X, _SOURCE_CENTER_Y, rotation=0)
    top_rail = _pin_point(source, "positive").y
    bottom_rail = _pin_point(source, "negative").y

    parts: list[Component] = []
    wires: list[Wire] = []
    for i, branch in enumerate(branches, start=1):
        half = _half_height(branch.type, rotation=90)
        part = _place(branch, _SOURCE_X + _STEP_X * i, top_rail + half, rotation=90)
        parts.append(part)
        wires.append(_wire(f"W{2 * i - 1}", source.terminal("positive"), part.terminal("a")))
        wires.append(_wire(f"W{2 * i}", part.terminal("b"), source.terminal("negative")))

    ground = _place(ground, _SOURCE_X, bottom_rail + _GROUND_GAP, rotation=0)
    wires.append(
        _wire(f"W{2 * len(parts) + 1}", ground.terminal("gnd"), source.terminal("negative"))
    )

    return _document(template, name, [source, *parts, ground], wires)
