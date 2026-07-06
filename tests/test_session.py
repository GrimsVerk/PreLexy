import random

import pytest

import prelexy.definitions as definitions
import prelexy.session as session
from prelexy.scheduler import SimpleScheduler
from prelexy.session import run_session
from prelexy.store import Store


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: None)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "test.db") as s:
        yield s


def add_word(store, form, zipf=2.5, gloss=None):
    item_id = store.get_or_create_item(
        "en", form, lemma=form, pos="ADJ", metadata={"zipf": zipf}
    )
    if gloss:
        store.add_sense(item_id, gloss, "en", "wordnet")
    return item_id


def feed_answers(monkeypatch, answers):
    answer_iterator = iter(answers)
    monkeypatch.setattr(
        session.click, "prompt", lambda *args, **kwargs: next(answer_iterator)
    )


def play(store, profile, n_questions=10):
    return run_session(
        store,
        profile,
        "en",
        SimpleScheduler(),
        n_questions=n_questions,
        rng=random.Random(42),
    )


def test_session_records_reviews_and_state(store, monkeypatch):
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    feed_answers(monkeypatch, ["1", "2"])

    summary = play(store, profile)
    assert summary.asked == 2
    assert summary.suspended == 0

    logs = store._conn.execute("SELECT * FROM review_log ORDER BY id").fetchall()
    assert len(logs) == 2
    states = {
        row["item_id"]: row["status"]
        for row in store._conn.execute("SELECT * FROM item_state").fetchall()
    }
    for log in logs:
        expected = "known" if log["correct"] else "learning"
        assert states[log["item_id"]] == expected
        assert log["exercise"] == "mcq_definition"
        assert log["latency_ms"] >= 0
        assert log["response"]  # the chosen gloss text, from WordNet at large


def test_quit_stops_early_without_logging(store, monkeypatch):
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    feed_answers(monkeypatch, ["q"])

    summary = play(store, profile)
    assert summary.asked == 0
    assert store._conn.execute("SELECT COUNT(*) c FROM review_log").fetchone()["c"] == 0


def test_invalid_input_reprompts(store, monkeypatch, capsys):
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    feed_answers(monkeypatch, ["7", "nope", "1", "q"])

    summary = play(store, profile)
    assert summary.asked == 1
    assert "Please answer" in capsys.readouterr().out


def test_undefinable_words_get_suspended(store, monkeypatch):
    profile = store.get_or_create_profile("p")
    add_word(store, "xqzt", zipf=0.5)  # rarest → served first; no gloss anywhere
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    feed_answers(monkeypatch, ["1", "1"])

    summary = play(store, profile)
    assert summary.suspended == 1
    assert summary.asked == 2

    row = store._conn.execute(
        "SELECT item_state.status FROM item_state "
        "JOIN items ON items.id = item_state.item_id WHERE items.form = 'xqzt'"
    ).fetchone()
    assert row["status"] == "suspended"
    # suspended words are not served again (the rarest word would come first)
    feed_answers(monkeypatch, ["q"])
    assert play(store, profile).suspended == 0


def test_empty_store_says_so(store, capsys):
    profile = store.get_or_create_profile("p")
    summary = play(store, profile)
    assert summary.asked == 0
    assert "Nothing to practice" in capsys.readouterr().out
