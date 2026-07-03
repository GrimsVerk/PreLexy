from datetime import datetime, timezone

import pytest

from prelexy.scheduler import ItemSchedule, ReviewOutcome, SimpleScheduler
from prelexy.store import Store

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "test.db") as s:
        yield s


def add_word(store, form, zipf):
    return store.get_or_create_item("en", form, lemma=form, pos="ADJ", metadata={"zipf": zipf})


def test_next_items_missed_first_then_new_rarest_first(store):
    profile = store.get_or_create_profile("p")
    add_word(store, "middling", zipf=3.0)
    add_word(store, "rare", zipf=2.0)
    add_word(store, "common", zipf=5.0)
    missed = add_word(store, "missed", zipf=4.0)
    known = add_word(store, "known", zipf=1.0)
    store.upsert_item_state(profile, missed, "learning", None, {})
    store.upsert_item_state(profile, known, "known", None, {})

    scheduler = SimpleScheduler()
    picked = scheduler.next_items(store, profile, "en", NOW, limit=10)
    assert [row["form"] for row in picked] == ["missed", "rare", "middling", "common"]

    picked = scheduler.next_items(store, profile, "en", NOW, limit=2)
    assert [row["form"] for row in picked] == ["missed", "rare"]


def test_record_review_transitions(store):
    profile = store.get_or_create_profile("p")
    item = add_word(store, "gaunt", zipf=2.5)
    (state,) = SimpleScheduler().next_items(store, profile, "en", NOW, 1)

    scheduler = SimpleScheduler()
    schedule = scheduler.record_review(state, ReviewOutcome(correct=True), NOW)
    assert schedule == ItemSchedule(status="known", due_at=None, scheduler_state={})

    schedule = scheduler.record_review(state, ReviewOutcome(correct=False), NOW)
    assert schedule.status == "learning"

    # a previously-missed word answered correctly graduates
    store.upsert_item_state(profile, item, "learning", None, {})
    (state,) = SimpleScheduler().next_items(store, profile, "en", NOW, 1)
    assert scheduler.record_review(state, ReviewOutcome(correct=True), NOW).status == "known"
