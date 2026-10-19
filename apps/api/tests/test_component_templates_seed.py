"""Seed da coleção `templates` a partir de um catálogo JSON (E5-06)."""

import json
from pathlib import Path

import mongomock
import pytest
from pydantic import ValidationError

from app.component_templates import seed
from app.component_templates.seed import load_components, seed_templates

CATALOG_FIXTURE = (
    Path(__file__).resolve().parents[3] / "packages/circuit-schema/test/fixtures/catalog.json"
)


@pytest.fixture
def db():
    return mongomock.MongoClient().get_database("teste-seed")


def test_seeds_fixture_catalog_and_is_idempotent(db) -> None:
    components = load_components(CATALOG_FIXTURE)

    inserted = seed_templates(db, components)

    assert inserted == [c.type for c in components]
    assert db["templates"].count_documents({"createdBy": "seed"}) == len(components)
    assert seed_templates(db, components) == []
    assert db["templates"].count_documents({}) == len(components)


def test_keeps_templates_edited_by_admins(db) -> None:
    components = load_components(CATALOG_FIXTURE)
    db["templates"].insert_one({"type": "resistor", "label": "Editado"})

    inserted = seed_templates(db, components)

    assert "resistor" not in inserted
    assert db["templates"].find_one({"type": "resistor"})["label"] == "Editado"


def test_rejects_invalid_catalog(tmp_path: Path) -> None:
    missing = tmp_path / "sem-componentes.json"
    missing.write_text(json.dumps({"catalogVersion": "1.0"}), encoding="utf-8")
    with pytest.raises(ValueError, match="components"):
        load_components(missing)

    invalid = tmp_path / "invalido.json"
    invalid.write_text(json.dumps({"components": [{"type": "x", "extra": 1}]}), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_components(invalid)


def test_main_reports_usage_and_invalid_file(tmp_path: Path, capsys) -> None:
    assert seed.main([]) == 2
    assert seed.main([str(tmp_path / "nao-existe.json")]) == 1
    assert "Catálogo inválido" in capsys.readouterr().err
