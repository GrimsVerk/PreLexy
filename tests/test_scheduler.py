import json
from datetime import datetime, timedelta, timezone

import pytest

from prelexy.scheduler import (
    ItemSchedule,
    ReviewOutcome,
    SimpleScheduler,
    SM2Scheduler,
)
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


def fake_state(blob=None):
    return {"scheduler_state": json.dumps(blob) if blob else None}


def due_in(schedule, days):
    return datetime.fromisoformat(schedule.due_at) == NOW + timedelta(days=days)


def test_sm2_interval_progression_on_success():
    scheduler = SM2Scheduler()

    first = scheduler.record_review(None, ReviewOutcome(correct=True), NOW)
    assert first.status == "learning"
    assert due_in(first, 1)
    assert first.scheduler_state == {"n": 1, "ef": 2.6, "interval_days": 1}

    second = scheduler.record_review(
        fake_state(first.scheduler_state), ReviewOutcome(correct=True), NOW
    )
    assert second.status == "learning"
    assert due_in(second, 6)

    third = scheduler.record_review(
        fake_state(second.scheduler_state), ReviewOutcome(correct=True), NOW
    )
    assert third.status == "known"
    assert due_in(third, round(6 * 2.7))  # interval × ease grows the spacing


def test_sm2_miss_resets_repetitions_but_keeps_ease():
    scheduler = SM2Scheduler()
    schedule = scheduler.record_review(
        fake_state({"n": 5, "ef": 2.9, "interval_days": 40}),
        ReviewOutcome(correct=False),
        NOW,
    )
    assert schedule.status == "learning"
    assert due_in(schedule, 1)
    assert schedule.scheduler_state == {"n": 0, "ef": 2.9, "interval_days": 1}

    # relearning after the miss starts the ladder again
    relearned = scheduler.record_review(
        fake_state(schedule.scheduler_state), ReviewOutcome(correct=True), NOW
    )
    assert due_in(relearned, 1)
    assert relearned.scheduler_state["ef"] == 3.0


def test_sm2_ease_never_drops_below_floor():
    schedule = SM2Scheduler().record_review(
        fake_state({"n": 1, "ef": 1.1, "interval_days": 1}),
        ReviewOutcome(correct=True),
        NOW,
    )
    assert schedule.scheduler_state["ef"] >= SM2Scheduler.MIN_EASE


def test_sm2_next_items_serves_due_then_new_and_respects_spacing(store):
    profile = store.get_or_create_profile("p")
    overdue = add_word(store, "overdue", zipf=4.0)
    not_yet = add_word(store, "notyet", zipf=1.0)
    legacy = add_word(store, "legacy", zipf=4.5)
    suspended = add_word(store, "suspended", zipf=0.5)
    add_word(store, "brandnew", zipf=3.0)
    store.upsert_item_state(
        profile, overdue, "known", (NOW - timedelta(days=2)).isoformat(), {}
    )
    store.upsert_item_state(
        profile, not_yet, "learning", (NOW + timedelta(days=3)).isoformat(), {}
    )
    store.upsert_item_state(profile, legacy, "learning", None, {})
    store.upsert_item_state(profile, suspended, "suspended", None, {})

    picked = SM2Scheduler().next_items(store, profile, "en", NOW, limit=10)
    assert [row["form"] for row in picked] == ["legacy", "overdue", "brandnew"]

    # once the future review matures it is served ahead of new words
    later = NOW + timedelta(days=4)
    picked = SM2Scheduler().next_items(store, profile, "en", later, limit=10)
    assert [row["form"] for row in picked][:3] == ["legacy", "overdue", "notyet"]


def test_sm2_new_ratio_trumps_review_backlog(store):
    profile = store.get_or_create_profile("p")
    for i in range(20):  # a big review backlog
        item = add_word(store, f"due{i}", zipf=3.0)
        store.upsert_item_state(
            profile, item, "learning", (NOW - timedelta(days=1)).isoformat(), {}
        )
    for i in range(5):
        add_word(store, f"new{i}", zipf=2.0)

    picked = SM2Scheduler(new_ratio=0.3).next_items(store, profile, "en", NOW, limit=10)
    forms = [row["form"] for row in picked]
    assert len(forms) == 10
    assert sum(form.startswith("new") for form in forms) == 3
    assert sum(form.startswith("due") for form in forms) == 7

    # with no new words left, the ratio yields and reviews fill the session
    empty_new = SM2Scheduler(new_ratio=0.3).next_items(store, profile, "nl", NOW, 10)
    assert empty_new == []
    all_new_profile = store.get_or_create_profile("fresh")
    picked = SM2Scheduler(new_ratio=0.3).next_items(store, all_new_profile, "en", NOW, 10)
    assert len(picked) == 10  # nothing due yet: new words fill everything


def test_sm2_shuffles_rarity_ties_between_sessions(store):
    import random

    profile = store.get_or_create_profile("p")
    for i in range(30):
        add_word(store, f"tied{i:02d}", zipf=0.0)

    order_a = [
        row["form"]
        for row in SM2Scheduler(rng=random.Random(1)).next_items(store, profile, "en", NOW, 10)
    ]
    order_b = [
        row["form"]
        for row in SM2Scheduler(rng=random.Random(2)).next_items(store, profile, "en", NOW, 10)
    ]
    order_a_again = [
        row["form"]
        for row in SM2Scheduler(rng=random.Random(1)).next_items(store, profile, "en", NOW, 10)
    ]
    assert order_a != order_b  # no longer deterministic alphabetical
    assert order_a == order_a_again  # but reproducible per seed


def test_sm2_full_loop_spaces_an_item_through_the_store(store):
    profile = store.get_or_create_profile("p")
    item = add_word(store, "gaunt", zipf=2.5)
    scheduler = SM2Scheduler()

    (state,) = scheduler.next_items(store, profile, "en", NOW, 1)
    schedule = scheduler.record_review(state, ReviewOutcome(correct=True), NOW)
    store.upsert_item_state(
        profile, item, schedule.status, schedule.due_at, schedule.scheduler_state
    )

    assert scheduler.next_items(store, profile, "en", NOW, 10) == []  # spaced out
    tomorrow = NOW + timedelta(days=1, minutes=1)
    assert [r["form"] for r in scheduler.next_items(store, profile, "en", tomorrow, 10)] == [
        "gaunt"
    ]
