"""SQLite persistence layer.

All database access goes through `Store`; nothing else in the codebase touches
SQL. Schema and rationale: docs/DESIGN.md ("Data model").

Use `Store` as a context manager: writes are committed on clean exit and
rolled back if the block raises.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Content: derived from input texts, profile-independent
CREATE TABLE IF NOT EXISTS sources (
    id       INTEGER PRIMARY KEY,
    title    TEXT NOT NULL,
    language TEXT NOT NULL,
    kind     TEXT NOT NULL,
    path     TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id       INTEGER PRIMARY KEY,
    language TEXT NOT NULL,
    form     TEXT NOT NULL,
    lemma    TEXT,
    pos      TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    UNIQUE (language, form)
);

CREATE TABLE IF NOT EXISTS occurrences (
    id        INTEGER PRIMARY KEY,
    item_id   INTEGER NOT NULL REFERENCES items(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    context   TEXT NOT NULL,
    position  INTEGER
);

-- Knowledge: cached definitions, shared across profiles
CREATE TABLE IF NOT EXISTS senses (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES items(id),
    gloss          TEXT NOT NULL,
    gloss_language TEXT NOT NULL,
    provider       TEXT NOT NULL,
    fetched_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Learner: per profile, mutable
CREATE TABLE IF NOT EXISTS profiles (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    settings TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS item_state (
    profile_id      INTEGER NOT NULL REFERENCES profiles(id),
    item_id         INTEGER NOT NULL REFERENCES items(id),
    status          TEXT NOT NULL DEFAULT 'new',
    due_at          TEXT,
    scheduler_state TEXT NOT NULL DEFAULT '{}',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (profile_id, item_id)
);

CREATE TABLE IF NOT EXISTS review_log (
    id         INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    item_id    INTEGER NOT NULL REFERENCES items(id),
    ts         TEXT NOT NULL DEFAULT (datetime('now')),
    exercise   TEXT NOT NULL,
    response   TEXT,
    correct    INTEGER NOT NULL,
    latency_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_occurrences_item   ON occurrences(item_id);
CREATE INDEX IF NOT EXISTS idx_occurrences_source ON occurrences(source_id);
CREATE INDEX IF NOT EXISTS idx_item_state_due     ON item_state(profile_id, due_at);
"""


def default_db_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
    return base / "prelexy" / "prelexy.db"


def _new_id(cur: sqlite3.Cursor) -> int:
    """The rowid an INSERT just created (sqlite3 types this as optional)."""
    assert cur.lastrowid is not None, "INSERT did not produce a rowid"
    return cur.lastrowid


def item_zipf(row: sqlite3.Row) -> float:
    """Rarity score stored in an item row's metadata at ingest time."""
    return float(json.loads(row["metadata"]).get("zipf", 0.0))


def item_order(row: sqlite3.Row) -> int:
    """Corpus position for code items (inventory order); 0 for natural."""
    return int(json.loads(row["metadata"]).get("order", 0))


def _sentence_complete(text: str) -> bool:
    """Whether a context excerpt reads as a whole sentence."""
    text = text.strip()
    if len(text) < 20:
        return False
    first = text.lstrip("“”\"'‘’(")[:1]
    if not first or not first.isupper():
        return False
    return text.rstrip("“”\"'‘’)")[-1:] in ".!?…"


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._init_version()

    def _init_version(self) -> None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()
        elif int(row["value"]) != SCHEMA_VERSION:
            raise RuntimeError(
                f"Database {self.path} has schema version {row['value']}, "
                f"but this build supports version {SCHEMA_VERSION} "
                "and no migration exists yet"
            )

    # -- content ----------------------------------------------------------

    def add_source(self, title: str, language: str, kind: str, path: str | None) -> int:
        cur = self._conn.execute(
            "INSERT INTO sources (title, language, kind, path) VALUES (?, ?, ?, ?)",
            (title, language, kind, path),
        )
        return _new_id(cur)

    def find_source_by_path(self, path: str) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self._conn.execute(
            "SELECT * FROM sources WHERE path = ?", (path,)
        ).fetchone()
        return row

    def get_or_create_item(
        self,
        language: str,
        form: str,
        lemma: str | None = None,
        pos: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        self._conn.execute(
            "INSERT OR IGNORE INTO items (language, form, lemma, pos, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (language, form, lemma, pos, json.dumps(metadata or {})),
        )
        row = self._conn.execute(
            "SELECT id FROM items WHERE language = ? AND form = ?", (language, form)
        ).fetchone()
        return int(row["id"])

    def add_occurrences(
        self, item_id: int, source_id: int, occurrences: Iterable[tuple[str, int | None]]
    ) -> None:
        self._conn.executemany(
            "INSERT INTO occurrences (item_id, source_id, context, position) VALUES (?, ?, ?, ?)",
            ((item_id, source_id, context, position) for context, position in occurrences),
        )

    def find_item(self, language: str, form: str) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self._conn.execute(
            "SELECT * FROM items WHERE language = ? AND form = ?", (language, form)
        ).fetchone()
        return row

    def example_for(self, item_id: int) -> str | None:
        """The item's best example sentence: shortest complete-looking one.

        OCR page breaks truncate some occurrences mid-sentence and others
        run to enormous lengths (a 1,400-character monster in the
        2026-07-06 playtest); prefer the shortest occurrence that reads as
        a whole sentence, falling back to the shortest of whatever exists.

        Only the shortest handful are inspected: after a large ingest a
        common word can have tens of thousands of occurrences, and the best
        sentence is always among the shortest, so the SQL LIMIT keeps
        question building fast without changing the choice.
        """
        rows = self._conn.execute(
            "SELECT context FROM occurrences WHERE item_id = ? ORDER BY length(context) LIMIT 200",
            (item_id,),
        ).fetchall()
        if not rows:
            return None
        contexts = [row["context"] for row in rows]
        complete = [c for c in contexts if _sentence_complete(c)]
        return str(min(complete or contexts, key=len))

    def unsuspend_items(self, item_ids: Iterable[int]) -> int:
        """Return suspended items to play (all profiles); count of rows freed.

        Words are suspended when no definition can be found; an import that
        glosses them must bring them back (2026-07-07 playtest: 7/10 words
        were parked forever).
        """
        ids = list(item_ids)
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        cur = self._conn.execute(
            f"DELETE FROM item_state WHERE status = 'suspended' AND item_id IN ({placeholders})",
            ids,
        )
        return cur.rowcount

    def code_pool(
        self, pos: str, languages: Sequence[str], exclude_item_id: int
    ) -> list[tuple[str, str]]:
        """Distractor material for code items: same-kind forms + glosses.

        Unlike natural languages (WordNet-wide pools), code distractors come
        from the ingested corpora themselves — spanning all code languages
        by default to maximize difficulty (DECISIONS 024).
        """
        langs = list(languages)
        placeholders = ",".join("?" * len(langs))
        rows = self._conn.execute(
            f"SELECT items.form, senses.gloss FROM items "
            f"JOIN senses ON senses.item_id = items.id "
            f"WHERE items.pos = ? AND items.language IN ({placeholders}) "
            f"AND items.id != ?",
            [pos, *langs, exclude_item_id],
        ).fetchall()
        return [(row["form"], row["gloss"]) for row in rows]

    def language_item_counts(self) -> dict[str, int]:
        """Item count per language, most-populated first — for empty-session
        guidance so the player knows what else is available to practice."""
        rows = self._conn.execute(
            "SELECT language, COUNT(*) AS n FROM items GROUP BY language ORDER BY n DESC"
        ).fetchall()
        return {row["language"]: row["n"] for row in rows}

    def items_missing_senses(self, language: str) -> list[sqlite3.Row]:
        """Items with no cached definition — targets for a gloss import."""
        return self._conn.execute(
            "SELECT items.* FROM items "
            "LEFT JOIN senses ON senses.item_id = items.id "
            "WHERE items.language = ? AND senses.id IS NULL",
            (language,),
        ).fetchall()

    def list_items(self, language: str) -> list[sqlite3.Row]:
        """All items for a language, each with its total occurrence count."""
        return self._conn.execute(
            "SELECT items.*, COUNT(occurrences.id) AS n_occurrences "
            "FROM items LEFT JOIN occurrences ON occurrences.item_id = items.id "
            "WHERE items.language = ? "
            "GROUP BY items.id",
            (language,),
        ).fetchall()

    # -- meta -------------------------------------------------------------

    def get_meta(self, key: str, default: Any = None) -> Any:
        """JSON value from the meta table (new-style keys only)."""
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )

    # -- knowledge --------------------------------------------------------

    def senses_for(self, item_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM senses WHERE item_id = ? ORDER BY id", (item_id,)
        ).fetchall()

    def add_sense(self, item_id: int, gloss: str, gloss_language: str, provider: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO senses (item_id, gloss, gloss_language, provider) VALUES (?, ?, ?, ?)",
            (item_id, gloss, gloss_language, provider),
        )
        return _new_id(cur)

    # -- learner ----------------------------------------------------------

    def list_profiles(self) -> list[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM profiles ORDER BY name").fetchall()

    def get_or_create_profile(self, name: str) -> int:
        self._conn.execute("INSERT OR IGNORE INTO profiles (name) VALUES (?)", (name,))
        row = self._conn.execute("SELECT id FROM profiles WHERE name = ?", (name,)).fetchone()
        return int(row["id"])

    def get_profile_settings(self, profile_id: int) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT settings FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return json.loads(row["settings"]) if row else {}

    def update_profile_settings(self, profile_id: int, **updates: Any) -> None:
        settings = self.get_profile_settings(profile_id)
        settings.update(updates)
        self._conn.execute(
            "UPDATE profiles SET settings = ? WHERE id = ?",
            (json.dumps(settings), profile_id),
        )

    def upsert_item_state(
        self,
        profile_id: int,
        item_id: int,
        status: str,
        due_at: str | None,
        scheduler_state: dict[str, Any],
    ) -> None:
        self._conn.execute(
            "INSERT INTO item_state (profile_id, item_id, status, due_at, scheduler_state) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (profile_id, item_id) DO UPDATE SET "
            "status = excluded.status, due_at = excluded.due_at, "
            "scheduler_state = excluded.scheduler_state, updated_at = datetime('now')",
            (profile_id, item_id, status, due_at, json.dumps(scheduler_state)),
        )

    def log_review(
        self,
        profile_id: int,
        item_id: int,
        exercise: str,
        response: str | None,
        correct: bool,
        latency_ms: int | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO review_log (profile_id, item_id, exercise, response, correct, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, item_id, exercise, response, int(correct), latency_ms),
        )

    def items_for_review(self, profile_id: int, language: str) -> list[sqlite3.Row]:
        """All items of a language joined with this profile's state.

        The state columns (status, due_at, scheduler_state) are NULL for
        items the profile has never reviewed.
        """
        return self._conn.execute(
            "SELECT items.*, item_state.status, item_state.due_at, "
            "item_state.scheduler_state "
            "FROM items LEFT JOIN item_state "
            "ON item_state.item_id = items.id AND item_state.profile_id = ? "
            "WHERE items.language = ?",
            (profile_id, language),
        ).fetchall()

    # -- lifecycle --------------------------------------------------------

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self.close()
