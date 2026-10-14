import pytest
from mongomock import MongoClient

from app.db import collections as store


@pytest.fixture
def db():
    return MongoClient().get_database("teste")


def test_insert_and_find(db) -> None:
    doc_id = store.insert_one(db, "items", {"nome": "R1", "valor": 100})

    found = store.find(db, "items", {"nome": "R1"})

    assert len(found) == 1
    assert str(found[0]["_id"]) == doc_id
    assert found[0]["valor"] == 100
    assert store.find_one(db, "items", {"nome": "R2"}) is None


def test_insert_many_and_limit(db) -> None:
    ids = store.insert_many(db, "items", [{"n": i} for i in range(5)])

    assert len(ids) == 5
    assert len(store.find(db, "items", limit=3)) == 3
    assert store.insert_many(db, "items", []) == []


def test_update_many_changes_matching_documents(db) -> None:
    store.insert_many(db, "items", [{"tipo": "R", "v": 1}, {"tipo": "R", "v": 2}, {"tipo": "C"}])

    changed = store.update_many(db, "items", {"tipo": "R"}, {"v": 10})

    assert changed == 2
    assert {d["v"] for d in store.find(db, "items", {"tipo": "R"})} == {10}
    assert "v" not in store.find_one(db, "items", {"tipo": "C"})


def test_delete_many_removes_matching_documents(db) -> None:
    store.insert_many(db, "items", [{"tipo": "R"}, {"tipo": "R"}, {"tipo": "C"}])

    assert store.delete_many(db, "items", {"tipo": "R"}) == 2
    assert [d["tipo"] for d in store.find(db, "items")] == ["C"]


def test_create_list_and_drop_collection(db) -> None:
    store.create_collection(db, "a")
    store.create_collection(db, "a")  # idempotente
    store.create_collection(db, "b")
    assert store.list_collections(db) == ["a", "b"]

    store.drop_collection(db, "a")

    assert store.list_collections(db) == ["b"]


@pytest.mark.parametrize("name", ["", "1abc", "a-b", "$cmd", "system.users", "a" * 65])
def test_invalid_collection_names_are_rejected(db, name: str) -> None:
    with pytest.raises(ValueError, match="Nome de collection inválido"):
        store.insert_one(db, name, {})
