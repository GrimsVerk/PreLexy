"""Review scheduling (docs/DESIGN.md, "Scheduler interface").

The session loop talks to a scheduler only through the protocol below, and a
scheduler's per-item memory lives in the opaque `scheduler_state` blob that
core code never interprets — swapping algorithms is a config change, not a
migration.

SimpleScheduler is the phase-3 placeholder until SM-2 lands in phase 4: it
serves previously-missed words first, then new words rarest-first, and never
schedules future reviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


class SimpleScheduler:
    """Placeholder scheduling: missed words first, then new words rarest-first.

    One correct answer marks a word known, one miss re-queues it for the next
    session. No spacing — that is SM-2's job in phase 4.
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
