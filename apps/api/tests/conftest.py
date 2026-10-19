from collections.abc import Iterator
from datetime import UTC, datetime

import mongomock
import pytest

from app.auth.dependencies import require_user
from app.circuit import catalog as catalog_module
from app.main import app
from app.models.user import UserOut

FAKE_USER = UserOut(
    id="000000000000000000000001",
    name="Utilizador de teste",
    email="teste@vcccircuitlab.test",
    created_at=datetime(2025, 1, 1, tzinfo=UTC),
)

#: Catálogo de testes (F2-10): os 6 componentes do antigo catálogo estático (mais o
#: condensador e a bobina da F2-02), inseridos num
#: MongoDB falso (`mongomock`) para que `load_catalog()` (lido da coleção `templates`) não
#: dependa de um MongoDB real nem de um ficheiro em disco durante os testes.
CATALOG_COMPONENTS: list[dict] = [
    {
        "type": "dc_voltage_source",
        "label": "Fonte de tensão DC",
        "description": (
            "Fonte de tensão contínua ideal. O terminal `positive` está a `voltageV` acima "
            "do terminal `negative`."
        ),
        "category": "source",
        "idPrefix": "V",
        "symbol": "dc_voltage_source_iec",
        "size": {"width": 40.0, "height": 80.0},
        "pins": [
            {"id": "positive", "kind": "positive", "position": {"x": 0.0, "y": -40.0}},
            {"id": "negative", "kind": "negative", "position": {"x": 0.0, "y": 40.0}},
        ],
        "properties": {
            "voltageV": {
                "type": "number",
                "title": "Tensão",
                "unit": "V",
                "default": 12.0,
                "maximum": 120.0,
                "exclusiveMinimum": 0.0,
            }
        },
        "simulationModel": "dc_voltage_source",
    },
    {
        "type": "dc_current_source",
        "label": "Fonte de corrente DC",
        "description": (
            "Fonte de corrente contínua ideal. A corrente `currentA` entra pelo terminal "
            "`negative` e sai pelo terminal `positive` para o circuito externo."
        ),
        "category": "source",
        "idPrefix": "I",
        "symbol": "dc_current_source_iec",
        "size": {"width": 40.0, "height": 80.0},
        "pins": [
            {"id": "positive", "kind": "positive", "position": {"x": 0.0, "y": -40.0}},
            {"id": "negative", "kind": "negative", "position": {"x": 0.0, "y": 40.0}},
        ],
        "properties": {
            "currentA": {
                "type": "number",
                "title": "Corrente",
                "unit": "A",
                "default": 0.1,
                "maximum": 10.0,
                "exclusiveMinimum": 0.0,
            }
        },
        "simulationModel": "dc_current_source",
    },
    {
        "type": "resistor",
        "label": "Resistência",
        "description": None,
        "category": "passive",
        "idPrefix": "R",
        "symbol": "resistor_iec",
        "size": {"width": 80.0, "height": 20.0},
        "pins": [
            {"id": "a", "kind": "passive", "position": {"x": -40.0, "y": 0.0}},
            {"id": "b", "kind": "passive", "position": {"x": 40.0, "y": 0.0}},
        ],
        "properties": {
            "resistanceOhm": {
                "type": "number",
                "title": "Resistência",
                "unit": "Ω",
                "default": 1000.0,
                "exclusiveMinimum": 0.0,
            }
        },
        "simulationModel": "resistor",
    },
    {
        "type": "switch",
        "label": "Interruptor",
        "description": "Interruptor ideal de dois terminais com estado explícito (aberto/fechado).",
        "category": "switch",
        "idPrefix": "S",
        "symbol": "switch_spst_iec",
        "size": {"width": 80.0, "height": 40.0},
        "pins": [
            {"id": "a", "kind": "passive", "position": {"x": -40.0, "y": 0.0}},
            {"id": "b", "kind": "passive", "position": {"x": 40.0, "y": 0.0}},
        ],
        "properties": {
            "closed": {"type": "boolean", "title": "Fechado", "default": False},
        },
        "simulationModel": "ideal_switch",
    },
    {
        "type": "lamp",
        "label": "Lâmpada",
        "description": (
            "Lâmpada modelada como resistência equivalente R = ratedVoltageV² / ratedPowerW "
            "(sem aquecimento nem corrente de arranque)."
        ),
        "category": "load",
        "idPrefix": "H",
        "symbol": "lamp_iec",
        "size": {"width": 80.0, "height": 40.0},
        "pins": [
            {"id": "a", "kind": "passive", "position": {"x": -40.0, "y": 0.0}},
            {"id": "b", "kind": "passive", "position": {"x": 40.0, "y": 0.0}},
        ],
        "properties": {
            "ratedVoltageV": {
                "type": "number",
                "title": "Tensão nominal",
                "unit": "V",
                "default": 12.0,
                "maximum": 120.0,
                "exclusiveMinimum": 0.0,
            },
            "ratedPowerW": {
                "type": "number",
                "title": "Potência nominal",
                "unit": "W",
                "default": 5.0,
                "exclusiveMinimum": 0.0,
            },
        },
        "simulationModel": "resistive_lamp",
    },
    {
        "type": "capacitor",
        "label": "Condensador",
        "description": "Condensador ideal (F2-02).",
        "category": "passive",
        "idPrefix": "C",
        "symbol": "capacitor_iec",
        "size": {"width": 80.0, "height": 40.0},
        "pins": [
            {"id": "a", "kind": "passive", "position": {"x": -40.0, "y": 0.0}},
            {"id": "b", "kind": "passive", "position": {"x": 40.0, "y": 0.0}},
        ],
        "properties": {
            "capacitanceF": {
                "type": "number",
                "title": "Capacidade",
                "unit": "F",
                "default": 0.0001,
                "exclusiveMinimum": 0.0,
                "maximum": 10.0,
            },
            "initialVoltageV": {
                "type": "number",
                "title": "Tensão inicial",
                "unit": "V",
                "default": 0.0,
                "minimum": -1000.0,
                "maximum": 1000.0,
            },
        },
        "simulationModel": "capacitor",
    },
    {
        "type": "inductor",
        "label": "Bobina",
        "description": "Bobina ideal (F2-02).",
        "category": "passive",
        "idPrefix": "L",
        "symbol": "inductor_iec",
        "size": {"width": 80.0, "height": 40.0},
        "pins": [
            {"id": "a", "kind": "passive", "position": {"x": -40.0, "y": 0.0}},
            {"id": "b", "kind": "passive", "position": {"x": 40.0, "y": 0.0}},
        ],
        "properties": {
            "inductanceH": {
                "type": "number",
                "title": "Indutância",
                "unit": "H",
                "default": 0.1,
                "exclusiveMinimum": 0.0,
                "maximum": 100.0,
            },
            "initialCurrentA": {
                "type": "number",
                "title": "Corrente inicial",
                "unit": "A",
                "default": 0.0,
                "minimum": -100.0,
                "maximum": 100.0,
            },
        },
        "simulationModel": "inductor",
    },
    {
        "type": "ground",
        "label": "Terra",
        "description": "Referência de potencial (0 V) do circuito.",
        "category": "reference",
        "idPrefix": "GND",
        "symbol": "ground_iec",
        "size": {"width": 40.0, "height": 40.0},
        "pins": [{"id": "gnd", "kind": "reference", "position": {"x": 0.0, "y": -20.0}}],
        "properties": {},
        "simulationModel": "ground",
    },
]


@pytest.fixture(autouse=True)
def authenticated(request: pytest.FixtureRequest) -> Iterator[None]:
    """As rotas protegidas recebem um utilizador falso, exceto nos testes `real_auth`."""
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(require_user, None)


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Cada teste começa com o rate limiter (E5-04) vazio: os testes partilham o mesmo IP."""
    app.state.rate_limiter.reset()


@pytest.fixture(autouse=True)
def catalog_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isola `load_catalog()` (F2-10, lido da coleção `templates`) de um MongoDB real: todos
    os testes passam a ver um `mongomock` pré-semeado com `CATALOG_COMPONENTS`. Testes que
    precisem de outro conteúdo podem sobrepor `app.circuit.catalog.get_database`
    explicitamente."""
    database = mongomock.MongoClient().get_database("teste-catalogo")
    database["templates"].insert_many([dict(c) for c in CATALOG_COMPONENTS])
    monkeypatch.setattr(catalog_module, "get_database", lambda: database)
