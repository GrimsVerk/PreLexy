import random
from collections.abc import Iterator
from pathlib import Path

import pytest

import prelexy.definitions as definitions
import prelexy.session as session
from prelexy.scheduler import SimpleScheduler
from prelexy.session import SessionSummary, run_session
from prelexy.store import Store


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: None)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store(tmp_path / "test.db") as s:
        yield s


def add_word(store: Store, form: str, zipf: float = 2.5, gloss: str | None = None) -> int:
    item_id = store.get_or_create_item("en", form, lemma=form, pos="ADJ", metadata={"zipf": zipf})
    if gloss:
        store.add_sense(item_id, gloss, "en", "wordnet")
    return item_id


def feed_answers(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    answer_iterator = iter(answers)
    monkeypatch.setattr("click.prompt", lambda *args, **kwargs: next(answer_iterator))


def play(store: Store, profile: int, n_questions: int = 10) -> SessionSummary:
    return run_session(
        store,
        profile,
        "en",
        SimpleScheduler(),
        n_questions=n_questions,
        rng=random.Random(42),
    )


def test_session_records_reviews_and_state(
    store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = store.get_or_create_profile("p")
    target = add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    source = store.add_source("t", "en", "book", None)
    store.add_occurrences(target, source, [("A sagacious old man.", 2)])
    feed_answers(monkeypatch, ["1", "2"])

    summary = play(store, profile)
    assert summary.asked == 2
    assert summary.suspended == 0

    # the context sentence is revealed only after the answer
    out = capsys.readouterr().out
    assert "seen in:" in out
    assert out.index("A sagacious old man.") > out.index("What does “sagacious” mean?")

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


def test_quit_stops_early_without_logging(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    feed_answers(monkeypatch, ["q"])

    summary = play(store, profile)
    assert summary.asked == 0
    assert store._conn.execute("SELECT COUNT(*) c FROM review_log").fetchone()["c"] == 0


def test_invalid_input_reprompts(
    store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    feed_answers(monkeypatch, ["7", "nope", "1", "q"])

    summary = play(store, profile)
    assert summary.asked == 1
    assert "Please answer" in capsys.readouterr().out


def test_undefinable_words_get_suspended(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_p_pronounces_and_still_records_one_review(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", zipf=2.0, gloss="having keen judgement")  # served first
    add_word(store, "gaunt", zipf=2.6, gloss="very thin")
    spoken = []

    def fake_pronounce(word: str, language: str = "en", voice: str | None = None) -> bool:
        spoken.append(word)
        return True

    monkeypatch.setattr(session, "pronounce", fake_pronounce)
    feed_answers(monkeypatch, ["p", "1", "q"])

    summary = play(store, profile)
    assert spoken == ["sagacious"]
    assert summary.asked == 1
    assert store._conn.execute("SELECT COUNT(*) c FROM review_log").fetchone()["c"] == 1


def test_p_without_engine_shows_hint(
    store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    monkeypatch.setattr(session, "pronounce", lambda word, language="en", voice=None: False)
    feed_answers(monkeypatch, ["p", "q"])

    play(store, profile)
    assert "No speech engine found" in capsys.readouterr().out


def test_show_context_false_hides_the_sentence(
    store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = store.get_or_create_profile("p")
    target = add_word(store, "sagacious", gloss="having keen judgement")
    add_word(store, "gaunt", gloss="very thin")
    source = store.add_source("t", "en", "book", None)
    store.add_occurrences(target, source, [("A sagacious old man.", 2)])
    feed_answers(monkeypatch, ["1", "q"])

    run_session(
        store,
        profile,
        "en",
        SimpleScheduler(),
        rng=random.Random(42),
        show_context=False,
    )
    assert "seen in:" not in capsys.readouterr().out


def test_p_passes_language_and_voice_to_pronounce(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = store.get_or_create_profile("p")
    add_word(store, "sagacious", zipf=2.0, gloss="having keen judgement")
    add_word(store, "gaunt", zipf=2.6, gloss="very thin")
    calls = []

    def fake_pronounce(word: str, language: str = "en", voice: str | None = None) -> bool:
        calls.append((word, language, voice))
        return True

    monkeypatch.setattr(session, "pronounce", fake_pronounce)
    feed_answers(monkeypatch, ["p", "q"])

    run_session(
        store,
        profile,
        "en",
        SimpleScheduler(),
        rng=random.Random(42),
        tts_voice="en-gb",
    )
    assert calls == [("sagacious", "en", "en-gb")]


def test_empty_store_says_so(store: Store, capsys: pytest.CaptureFixture[str]) -> None:
    profile = store.get_or_create_profile("p")
    summary = play(store, profile)
    assert summary.asked == 0
    assert summary.had_items is False
    assert "Nothing stored for 'en'" in capsys.readouterr().out


def test_empty_session_points_at_other_languages(
    store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = store.get_or_create_profile("p")
    # a Dutch corpus exists, but we ask to play empty English
    for i in range(3):
        store.get_or_create_item("nl", f"woord{i}", lemma=f"woord{i}", pos="NOUN")
    summary = play(store, profile)  # plays "en"
    assert summary.had_items is False
    out = capsys.readouterr().out
    assert "nl (3 items)" in out
    assert "prelexy play --language nl" in out
