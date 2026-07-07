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
from prelexy.speech import INSTALL_HINT, pronounce

EXERCISE = "mcq_definition"


@dataclass
class SessionSummary:
    asked: int = 0
    correct: int = 0
    suspended: int = 0
    had_items: bool = False  # did the language have anything to serve?


def run_session(
    store,
    profile_id: int,
    language: str,
    scheduler,
    similarity=None,
    n_questions: int = 10,
    rng=None,
    band=None,
    pool_size=None,
    show_context: bool = True,
    tts_voice: str | None = None,
    code_own_pool=None,
) -> SessionSummary:
    now = datetime.now(timezone.utc)
    items = scheduler.next_items(store, profile_id, language, now, n_questions)
    summary = SessionSummary(had_items=bool(items))
    if not items:
        _report_nothing_to_practice(store, language)
        return summary

    for item in items:
        question = build_question(
            store, item, similarity=similarity, rng=rng, band=band,
            pool_size=pool_size, code_own_pool=code_own_pool,
        )
        if question is None:
            store.upsert_item_state(profile_id, item["id"], "suspended", None, {})
            summary.suspended += 1
            continue
        answered = _ask(
            question, number=summary.asked + 1, language=language, tts_voice=tts_voice
        )
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
        if question.context and show_context:
            # revealed only after answering: seeing the sentence first makes
            # the definition guessable from context
            click.echo(f"  seen in: “{question.context}”")
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


def _report_nothing_to_practice(store, language: str) -> None:
    """Explain the empty session and point at languages that do have items."""
    counts = store.language_item_counts()
    if not counts.get(language):
        click.echo(f"Nothing stored for {language!r} yet — ingest a text first.")
    else:
        click.echo(f"Nothing due in {language!r} right now — you're all caught up.")
    others = [(lang, n) for lang, n in counts.items() if lang != language and n]
    if others:
        summary = ", ".join(f"{lang} ({n} items)" for lang, n in others)
        click.echo(f"Other languages with words: {summary}")
        click.echo(f"Practice one with: prelexy play --language {others[0][0]}")


def _ask(
    question, number: int, language: str = "en", tts_voice: str | None = None
) -> tuple[int, int] | None:
    """Render one question and return (chosen index, latency ms); None = quit."""
    click.echo()
    click.echo(f"{number}. What does “{question.form}” mean?")
    for index, option in enumerate(question.options):
        click.echo(f"   {index + 1}. {option}")
    started = time.monotonic()
    prompt_text = f"Your answer (1–{len(question.options)}, p to hear it, q to quit)"
    while True:
        try:
            raw = click.prompt(prompt_text, type=str).strip().lower()
        except (click.exceptions.Abort, EOFError):
            return None
        if raw == "q":
            return None
        if raw == "p":
            if not pronounce(question.form, language, voice=tts_voice):
                click.echo(f"  ({INSTALL_HINT})")
            continue
        if raw.isdigit() and 1 <= int(raw) <= len(question.options):
            latency_ms = int((time.monotonic() - started) * 1000)
            return int(raw) - 1, latency_ms
        click.echo(f"  Please answer 1–{len(question.options)}, p, or q.")
