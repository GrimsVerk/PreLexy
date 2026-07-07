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


def test_get_or_create_profile_is_idempotent(db):
    with Store(db) as store:
        first = store.get_or_create_profile("thom")
        assert store.get_or_create_profile("thom") == first
        assert store.get_or_create_profile("guest") != first


def test_meta_roundtrip(db):
    with Store(db) as store:
        assert store.get_meta("pod_subscriptions", []) == []
        store.set_meta("pod_subscriptions", [{"url": "u", "language": "nl"}])
        store.set_meta("pod_subscriptions", [{"url": "v", "language": "en"}])
        assert store.get_meta("pod_subscriptions") == [{"url": "v", "language": "en"}]
        # the schema_version key is untouched by meta helpers
        row = store._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row["value"] == "1"


def test_profile_settings_roundtrip_and_merge(db):
    with Store(db) as store:
        profile = store.get_or_create_profile("anna")
        assert store.get_profile_settings(profile) == {}
        store.update_profile_settings(profile, language="nl")
        store.update_profile_settings(profile, strong_language="en")
        assert store.get_profile_settings(profile) == {
            "language": "nl",
            "strong_language": "en",
        }


def test_upsert_item_state_inserts_then_updates(db):
    with Store(db) as store:
        profile = store.get_or_create_profile("p")
        item = store.get_or_create_item("en", "run")
        store.upsert_item_state(profile, item, "learning", None, {"box": 1})
        store.upsert_item_state(profile, item, "known", "2026-07-04T00:00:00", {"box": 2})
        rows = store._conn.execute("SELECT * FROM item_state").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "known"
    assert rows[0]["due_at"] == "2026-07-04T00:00:00"
    assert json.loads(rows[0]["scheduler_state"]) == {"box": 2}


def test_log_review_appends(db):
    with Store(db) as store:
        profile = store.get_or_create_profile("p")
        item = store.get_or_create_item("en", "run")
        store.log_review(profile, item, "mcq_definition", "a gloss", True, 1200)
        store.log_review(profile, item, "mcq_definition", "wrong gloss", False, None)
        rows = store._conn.execute("SELECT * FROM review_log ORDER BY id").fetchall()
    assert [row["correct"] for row in rows] == [1, 0]
    assert rows[0]["latency_ms"] == 1200
    assert rows[1]["response"] == "wrong gloss"


def test_items_for_review_joins_state_per_profile(db):
    with Store(db) as store:
        alice = store.get_or_create_profile("alice")
        bob = store.get_or_create_profile("bob")
        run = store.get_or_create_item("en", "run")
        store.get_or_create_item("en", "walk")
        store.get_or_create_item("nl", "lopen")
        store.upsert_item_state(alice, run, "learning", None, {})

        rows = {row["form"]: row for row in store.items_for_review(alice, "en")}
        assert set(rows) == {"run", "walk"}
        assert rows["run"]["status"] == "learning"
        assert rows["walk"]["status"] is None

        # bob's view is untouched by alice's progress
        bob_rows = {row["form"]: row for row in store.items_for_review(bob, "en")}
        assert bob_rows["run"]["status"] is None


def test_example_for_prefers_shortest_complete_sentence(db):
    monster = "He longed to see the curious table-napkins wrought for " + "x" * 300 + "."
    truncated = "But the staginess of her acting"  # no terminal punctuation
    ocr_start = "| remember your telling me years ago that it was lost."
    good = "Her little feet pattered overhead like a summer rain."
    with Store(db) as store:
        source = store.add_source("t", "en", "book", None)
        item = store.get_or_create_item("en", "patter")
        store.add_occurrences(
            item, source, [(monster, 0), (truncated, 10), (ocr_start, 20), (good, 30)]
        )
        assert store.example_for(item) == good

        # with no complete-looking sentence at all, the shortest one wins
        fragmentary = store.get_or_create_item("en", "fragment")
        store.add_occurrences(
            fragmentary, source, [("and the coat that Charles of", 0), (truncated, 5)]
        )
        assert store.example_for(fragmentary) == "and the coat that Charles of"

        assert store.example_for(store.get_or_create_item("en", "unseen")) is None


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
