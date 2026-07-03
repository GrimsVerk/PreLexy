import json

import pytest

from prelexy.store import SCHEMA_VERSION, Store

EXPECTED_TABLES = {
    "meta",
    "sources",
    "items",
    "occurrences",
    "senses",
    "profiles",
    "item_state",
    "review_log",
}


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.db"


def test_creates_full_schema(db):
    with Store(db) as store:
        rows = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert EXPECTED_TABLES <= {row["name"] for row in rows}


def test_schema_version_persists_and_mismatch_is_rejected(db):
    with Store(db):
        pass
    with Store(db) as store:
        row = store._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert int(row["value"]) == SCHEMA_VERSION
        store._conn.execute(
            "UPDATE meta SET value = '999' WHERE key = 'schema_version'"
        )
    with pytest.raises(RuntimeError, match="schema version 999"):
        Store(db)


def test_add_source_and_find_by_path(db):
    with Store(db) as store:
        source_id = store.add_source("Dorian Gray", "en", "book", "/tmp/dg.txt")
        assert source_id == 1
        found = store.find_source_by_path("/tmp/dg.txt")
        assert found["title"] == "Dorian Gray"
        assert store.find_source_by_path("/nowhere") is None


def test_get_or_create_item_dedupes_on_language_and_form(db):
    with Store(db) as store:
        a = store.get_or_create_item("en", "run", lemma="run", pos="VERB")
        b = store.get_or_create_item("en", "run")
        c = store.get_or_create_item("nl", "run")
        assert a == b
        assert a != c


def test_item_metadata_roundtrip(db):
    with Store(db) as store:
        item_id = store.get_or_create_item("en", "sagacious", metadata={"zipf": 2.5})
        row = store._conn.execute(
            "SELECT metadata FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        assert json.loads(row["metadata"]) == {"zipf": 2.5}


def test_list_items_counts_occurrences(db):
    with Store(db) as store:
        source_id = store.add_source("t", "en", "book", None)
        run = store.get_or_create_item("en", "run")
        walk = store.get_or_create_item("en", "walk")
        store.add_occurrences(run, source_id, [("He ran.", 0), ("She runs.", 10)])
        store.add_occurrences(walk, source_id, [("We walk.", 20)])
        counts = {row["form"]: row["n_occurrences"] for row in store.list_items("en")}
    assert counts == {"run": 2, "walk": 1}
    with Store(db) as store:
        assert store.list_items("nl") == []


def test_writes_persist_after_clean_exit(db):
    with Store(db) as store:
        store.add_source("kept", "en", "book", "/kept.txt")
    with Store(db) as store:
        assert store.find_source_by_path("/kept.txt") is not None


def test_writes_roll_back_on_exception(db):
    with pytest.raises(ValueError):
        with Store(db) as store:
            store.add_source("lost", "en", "book", "/lost.txt")
            raise ValueError("boom")
    with Store(db) as store:
        assert store.find_source_by_path("/lost.txt") is None
