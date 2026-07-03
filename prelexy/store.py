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
from pathlib import Path
from typing import Iterable

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
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
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
        return cur.lastrowid

    def find_source_by_path(self, path: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM sources WHERE path = ?", (path,)
        ).fetchone()

    def get_or_create_item(
        self,
        language: str,
        form: str,
        lemma: str | None = None,
        pos: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        self._conn.execute(
            "INSERT OR IGNORE INTO items (language, form, lemma, pos, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (language, form, lemma, pos, json.dumps(metadata or {})),
        )
        row = self._conn.execute(
            "SELECT id FROM items WHERE language = ? AND form = ?", (language, form)
        ).fetchone()
        return row["id"]

    def add_occurrences(
        self, item_id: int, source_id: int, occurrences: Iterable[tuple[str, int | None]]
    ) -> None:
        self._conn.executemany(
            "INSERT INTO occurrences (item_id, source_id, context, position) "
            "VALUES (?, ?, ?, ?)",
            ((item_id, source_id, context, position) for context, position in occurrences),
        )

    def list_items(self, language: str) -> list[sqlite3.Row]:
        """All items for a language, each with its total occurrence count."""
        return self._conn.execute(
            "SELECT items.*, COUNT(occurrences.id) AS n_occurrences "
            "FROM items LEFT JOIN occurrences ON occurrences.item_id = items.id "
            "WHERE items.language = ? "
            "GROUP BY items.id",
            (language,),
        ).fetchall()

    # -- lifecycle --------------------------------------------------------

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self.close()
