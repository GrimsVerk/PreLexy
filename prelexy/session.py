"""Interactive terminal practice session (docs/DESIGN.md; phase 3).

Renders multiple-choice questions, records every answer in the append-only
review log, and lets the scheduler digest each outcome into the item's next
state. Words for which no question can be built (no definition, no
distractors) are suspended so they stop being served.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import click

from prelexy.mcq import build_question
from prelexy.scheduler import ReviewOutcome

EXERCISE = "mcq_definition"


@dataclass
class SessionSummary:
    asked: int = 0
    correct: int = 0
    suspended: int = 0


def run_session(
    store,
    profile_id: int,
    language: str,
    scheduler,
    similarity=None,
    n_questions: int = 10,
    rng=None,
) -> SessionSummary:
    now = datetime.now(timezone.utc)
    items = scheduler.next_items(store, profile_id, language, now, n_questions)
    summary = SessionSummary()
    if not items:
        click.echo("Nothing to practice — ingest a text first, or you're all caught up.")
        return summary

    for item in items:
        question = build_question(store, item, similarity=similarity, rng=rng)
        if question is None:
            store.upsert_item_state(profile_id, item["id"], "suspended", None, {})
            summary.suspended += 1
            continue
        answered = _ask(question, number=summary.asked + 1)
        if answered is None:  # player quit (q / EOF)
            break
        choice, latency_ms = answered
        correct = choice == question.answer
        summary.asked += 1
        summary.correct += correct
        if correct:
            click.secho("  ✓ correct", fg="green")
        else:
            click.secho(f"  ✗ it means: {question.options[question.answer]}", fg="red")
        store.log_review(
            profile_id,
            item["id"],
            EXERCISE,
            response=question.options[choice],
            correct=correct,
            latency_ms=latency_ms,
        )
        schedule = scheduler.record_review(item, ReviewOutcome(correct=correct), now)
        store.upsert_item_state(
            profile_id, item["id"], schedule.status, schedule.due_at, schedule.scheduler_state
        )

    if summary.asked:
        click.echo(f"\nSession over: {summary.correct}/{summary.asked} correct.")
    if summary.suspended:
        click.echo(
            f"({summary.suspended} word(s) had no usable definition and were set aside.)"
        )
    return summary


def _ask(question, number: int) -> tuple[int, int] | None:
    """Render one question and return (chosen index, latency ms); None = quit."""
    click.echo()
    if question.context:
        click.echo(f"  “{question.context}”")
    click.echo(f"{number}. What does “{question.form}” mean?")
    for index, option in enumerate(question.options):
        click.echo(f"   {index + 1}. {option}")
    started = time.monotonic()
    while True:
        try:
            raw = click.prompt("Your answer (q to quit)", type=str).strip().lower()
        except (click.exceptions.Abort, EOFError):
            return None
        if raw == "q":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(question.options):
            latency_ms = int((time.monotonic() - started) * 1000)
            return int(raw) - 1, latency_ms
        click.echo(f"  Please answer 1–{len(question.options)}, or q.")
