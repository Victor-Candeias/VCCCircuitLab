"""Testes do algoritmo de layout (E3-03): posições alinhadas à grelha do editor e fios sem
cantos desnecessários — só a malha fechada à direita (`chain_loop`) precisa de um waypoint; o
`parallel_ladder` fica todo alinhado aos carris, sem waypoints nenhuns.
"""

from app.circuit.catalog import load_catalog
from app.generation.layout import chain_loop, parallel_ladder
from app.models.circuit import CircuitDocument, Component, Point

CATALOG = load_catalog()
GRID = CATALOG.grid_size


def _component(cid: str, ctype: str, pins: list[str], properties: dict | None = None) -> Component:
    return Component(
        id=cid,
        type=ctype,
        position=Point(x=0, y=0),
        rotation=0,
        properties=properties or {},
        pins=pins,
    )


def _rotate(dx: float, dy: float, rotation: int) -> tuple[float, float]:
    if rotation == 90:
        return (-dy, dx)
    if rotation == 180:
        return (-dx, -dy)
    if rotation == 270:
        return (dy, -dx)
    return (dx, dy)


def _pin_positions(component: Component) -> dict[str, tuple[float, float]]:
    spec = CATALOG.get(component.type)
    assert spec is not None
    return {
        pin: (
            component.position.x + _rotate(*offset, component.rotation)[0],
            component.position.y + _rotate(*offset, component.rotation)[1],
        )
        for pin, offset in spec.pin_positions.items()
    }


def _on_grid(value: float) -> bool:
    return value % GRID == 0


def _source() -> Component:
    return _component("V1", "dc_voltage_source", ["positive", "negative"], {"voltageV": 12.0})


def _ground() -> Component:
    return _component("GND1", "ground", ["gnd"])


def _resistor(rid: str) -> Component:
    return _component(rid, "resistor", ["a", "b"], {"resistanceOhm": 100.0})


class TestChainLoop:
    def _build(self, n: int) -> CircuitDocument:
        chain = [_resistor(f"R{i}") for i in range(1, n + 1)]
        return chain_loop("t", "n", _source(), chain, _ground())

    def test_positions_are_grid_aligned(self) -> None:
        document = self._build(3)

        for component in document.components:
            assert _on_grid(component.position.x)
            assert _on_grid(component.position.y)

    def test_series_wires_are_straight(self) -> None:
        document = self._build(3)

        # W1 (fonte -> R1) e os fios entre resistores consecutivos: sem waypoints.
        for wire in document.wires[:-2]:
            assert wire.waypoints == []

    def test_top_rail_pins_share_the_same_height(self) -> None:
        document = self._build(2)
        positions = {c.id: _pin_positions(c) for c in document.components}

        top = positions["V1"]["positive"][1]
        assert positions["R1"]["a"][1] == top
        assert positions["R1"]["b"][1] == top
        assert positions["R2"]["a"][1] == top

    def test_closing_wire_has_one_orthogonal_corner(self) -> None:
        document = self._build(3)
        positions = {c.id: _pin_positions(c) for c in document.components}

        closing = document.wires[-2]
        assert len(closing.waypoints) == 1
        corner = closing.waypoints[0]

        from_component, from_pin = closing.from_.split(".")
        to_component, to_pin = closing.to.split(".")
        from_pos = positions[from_component][from_pin]
        to_pos = positions[to_component][to_pin]

        # Desce (mesmo x de "from") e depois vai para a esquerda (mesma y de "to").
        assert corner.x == from_pos[0]
        assert corner.y == to_pos[1]

    def test_ground_wire_is_vertical(self) -> None:
        document = self._build(1)
        positions = {c.id: _pin_positions(c) for c in document.components}

        ground_wire = document.wires[-1]
        assert ground_wire.waypoints == []
        assert positions["GND1"]["gnd"][0] == positions["V1"]["negative"][0]


class TestParallelLadder:
    def _build(self, n: int) -> CircuitDocument:
        branches = [_resistor(f"R{i}") for i in range(1, n + 1)]
        return parallel_ladder("t", "n", _source(), branches, _ground())

    def test_positions_are_grid_aligned(self) -> None:
        document = self._build(3)

        for component in document.components:
            assert _on_grid(component.position.x)
            assert _on_grid(component.position.y)

    def test_all_wires_are_straight(self) -> None:
        document = self._build(3)

        for wire in document.wires:
            assert wire.waypoints == []

    def test_branches_align_to_both_rails(self) -> None:
        document = self._build(3)
        positions = {c.id: _pin_positions(c) for c in document.components}

        top = positions["V1"]["positive"][1]
        bottom = positions["V1"]["negative"][1]
        for i in range(1, 4):
            assert positions[f"R{i}"]["a"][1] == top
            assert positions[f"R{i}"]["b"][1] == bottom

    def test_branches_do_not_overlap_horizontally(self) -> None:
        document = self._build(3)
        xs = [c.position.x for c in document.components if c.type == "resistor"]
        assert xs == sorted(set(xs))
