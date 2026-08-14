import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from prelexy.scheduler import (
    ItemSchedule,
    ReviewOutcome,
    SimpleScheduler,
    SM2Scheduler,
)
from prelexy.store import Store

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store(tmp_path / "test.db") as s:
        yield s


def add_word(store: Store, form: str, zipf: float) -> int:
    return store.get_or_create_item("en", form, lemma=form, pos="ADJ", metadata={"zipf": zipf})


def test_next_items_missed_first_then_new_rarest_first(store: Store) -> None:
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


def test_record_review_transitions(store: Store) -> None:
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


def fake_state(blob: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"scheduler_state": json.dumps(blob) if blob else None}


def due_in(schedule: ItemSchedule, days: int) -> bool:
    assert schedule.due_at is not None
    return datetime.fromisoformat(schedule.due_at) == NOW + timedelta(days=days)


def test_sm2_interval_progression_on_success() -> None:
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


def test_sm2_miss_resets_repetitions_but_keeps_ease() -> None:
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


def test_sm2_ease_never_drops_below_floor() -> None:
    schedule = SM2Scheduler().record_review(
        fake_state({"n": 1, "ef": 1.1, "interval_days": 1}),
        ReviewOutcome(correct=True),
        NOW,
    )
    assert schedule.scheduler_state["ef"] >= SM2Scheduler.MIN_EASE


def test_sm2_next_items_serves_due_then_new_and_respects_spacing(store: Store) -> None:
    profile = store.get_or_create_profile("p")
    overdue = add_word(store, "overdue", zipf=4.0)
    not_yet = add_word(store, "notyet", zipf=1.0)
    legacy = add_word(store, "legacy", zipf=4.5)
    suspended = add_word(store, "suspended", zipf=0.5)
    add_word(store, "brandnew", zipf=3.0)
    store.upsert_item_state(profile, overdue, "known", (NOW - timedelta(days=2)).isoformat(), {})
    store.upsert_item_state(profile, not_yet, "learning", (NOW + timedelta(days=3)).isoformat(), {})
    store.upsert_item_state(profile, legacy, "learning", None, {})
    store.upsert_item_state(profile, suspended, "suspended", None, {})

    picked = SM2Scheduler().next_items(store, profile, "en", NOW, limit=10)
    assert [row["form"] for row in picked] == ["legacy", "overdue", "brandnew"]

    # once the future review matures it is served ahead of new words
    later = NOW + timedelta(days=4)
    picked = SM2Scheduler().next_items(store, profile, "en", later, limit=10)
    assert [row["form"] for row in picked][:3] == ["legacy", "overdue", "notyet"]


def test_sm2_quotas_trump_review_backlog(store: Store) -> None:
    profile = store.get_or_create_profile("p")
    for i in range(20):  # a big review backlog
        item = add_word(store, f"due{i}", zipf=3.0)
        store.upsert_item_state(
            profile, item, "learning", (NOW - timedelta(days=1)).isoformat(), {}
        )
    for i in range(30):
        add_word(store, f"new{i}", zipf=2.0)

    picked = SM2Scheduler(new_words=7, seen_words=3).next_items(store, profile, "en", NOW, limit=10)
    forms = [row["form"] for row in picked]
    assert len(forms) == 10
    assert sum(form.startswith("new") for form in forms) == 7
    assert sum(form.startswith("due") for form in forms) == 3

    # with no new words left, reviews fill the whole session
    all_seen = store.get_or_create_profile("p")
    empty = SM2Scheduler(new_words=7, seen_words=3).next_items(store, all_seen, "nl", NOW, 10)
    assert empty == []
    picked = SM2Scheduler(new_words=25, seen_words=3).next_items(
        store, profile, "en", NOW, limit=28
    )
    forms = [row["form"] for row in picked]
    assert sum(form.startswith("due") for form in forms) == 3
    assert sum(form.startswith("new") for form in forms) == 25

    # and when new words run short, reviews refill the gap
    picked = SM2Scheduler(new_words=50, seen_words=3).next_items(
        store, profile, "en", NOW, limit=53
    )
    forms = [row["form"] for row in picked]
    assert sum(form.startswith("new") for form in forms) == 30  # all there are
    assert sum(form.startswith("due") for form in forms) == 20  # backlog refills


def test_sm2_shuffles_rarity_ties_between_sessions(store: Store) -> None:
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


def test_code_items_are_served_in_inventory_order(store: Store) -> None:
    import random

    for i, name in enumerate(["zlib.compress", "abc.register", "os.walk"]):
        store.get_or_create_item(
            "python",
            name,
            lemma=name,
            pos="function",
            metadata={"order": i},
        )
    profile = store.get_or_create_profile("p")
    forms = [
        row["form"]
        for row in SM2Scheduler(rng=random.Random(1)).next_items(store, profile, "python", NOW, 10)
    ]
    assert forms == ["zlib.compress", "abc.register", "os.walk"]  # not alphabetical


def test_sm2_full_loop_spaces_an_item_through_the_store(store: Store) -> None:
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
