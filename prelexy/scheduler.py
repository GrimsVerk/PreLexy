"""Review scheduling (docs/DESIGN.md, "Scheduler interface").

The session loop talks to a scheduler only through the protocol below, and a
scheduler's per-item memory lives in the opaque `scheduler_state` blob that
core code never interprets — swapping algorithms is a config change, not a
migration.

SM2Scheduler is the default: a binary-outcome adaptation of the classic
SM-2 spaced-repetition algorithm. SimpleScheduler (no spacing) is kept as
the minimal reference implementation of the protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from prelexy.store import item_zipf


@dataclass
class ReviewOutcome:
    correct: bool


@dataclass
class ItemSchedule:
    """A scheduler's verdict on an item after one review."""

    status: str
    due_at: str | None  # ISO timestamp; None = no scheduled review
    scheduler_state: dict


class Scheduler(Protocol):
    def next_items(
        self, store, profile_id: int, language: str, now: datetime, limit: int
    ) -> list:
        """Items to practice this session, most urgent first."""

    def record_review(
        self, state, outcome: ReviewOutcome, now: datetime
    ) -> ItemSchedule:
        """Digest one review into the item's next schedule.

        `state` is the item's row from Store.items_for_review — its status,
        due_at, and scheduler_state columns are None on first review.
        """


class SM2Scheduler:
    """Binary-outcome adaptation of SM-2 (the classic Anki algorithm).

    Correct answers grow the review interval (1 day, 6 days, then
    interval × ease factor, with the ease factor drifting up by 0.1 per
    success); a miss resets the repetition count and brings the word back
    tomorrow, leaving the ease factor untouched (as in original SM-2 for
    low-quality responses). A word counts as "known" from the third
    consecutive success; due dates, not statuses, drive scheduling.
    """

    INITIAL_EASE = 2.5
    MIN_EASE = 1.3
    KNOWN_AFTER = 3  # consecutive successes

    def next_items(self, store, profile_id, language, now, limit):
        rows = store.items_for_review(profile_id, language)
        due, new = [], []
        for row in rows:
            status = row["status"]
            if status == "suspended":
                continue
            if status is None:
                new.append(row)
            elif _is_due(row, now):
                due.append(row)
        due.sort(key=lambda row: row["due_at"] or "")  # un-dated legacy rows first
        new.sort(key=item_zipf)
        return (due + new)[:limit]

    def record_review(self, state, outcome, now):
        previous = _blob(state)
        successes = previous.get("n", 0)
        ease = previous.get("ef", self.INITIAL_EASE)
        interval = previous.get("interval_days", 0)
        if outcome.correct:
            successes += 1
            if successes == 1:
                interval = 1
            elif successes == 2:
                interval = 6
            else:
                interval = round(interval * ease)
            ease = max(ease + 0.1, self.MIN_EASE)
        else:
            successes = 0
            interval = 1
        return ItemSchedule(
            status="known" if successes >= self.KNOWN_AFTER else "learning",
            due_at=(now + timedelta(days=interval)).isoformat(),
            scheduler_state={
                "n": successes,
                "ef": round(ease, 3),
                "interval_days": interval,
            },
        )


def _blob(state) -> dict:
    raw = state["scheduler_state"] if state is not None else None
    return json.loads(raw) if raw else {}


def _is_due(row, now: datetime) -> bool:
    if row["due_at"] is None:
        return row["status"] == "learning"  # rows written before spacing existed
    return datetime.fromisoformat(row["due_at"]) <= now


class SimpleScheduler:
    """Minimal reference scheduler: missed words first, then new rarest-first.

    One correct answer marks a word known, one miss re-queues it for the next
    session. No spacing.
    """

    def next_items(self, store, profile_id, language, now, limit):
        rows = store.items_for_review(profile_id, language)
        missed = [row for row in rows if row["status"] == "learning"]
        new = sorted(
            (row for row in rows if row["status"] is None), key=item_zipf
        )
        return (missed + new)[:limit]

    def record_review(self, state, outcome, now):
        return ItemSchedule(
            status="known" if outcome.correct else "learning",
            due_at=None,
            scheduler_state={},
        )
