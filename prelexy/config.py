"""User configuration file (docs/DESIGN.md).

Lives at `$XDG_CONFIG_HOME/prelexy/config.toml` (default
`~/.config/prelexy/config.toml`) and is created with commented defaults on
first use so it is discoverable. Precedence everywhere:
CLI flag > config file > built-in default.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast


class Config(TypedDict):
    """The settings file's shape. Keeping it typed means every reader gets a
    real type instead of `object` from a heterogeneous dict."""

    new_words: int
    seen_words: int
    similarity_floor: float
    similarity_ceiling: float
    default_profile: str
    default_language: str
    db_path: str
    tts_voice: str
    pool_size: int
    show_context: bool
    code_pool_own_language: bool


DEFAULTS: Config = {
    "new_words": 7,  # new words per session
    "seen_words": 3,  # previously seen words (due reviews) per session
    "similarity_floor": 0.45,  # distractor band, see docs/DESIGN.md
    "similarity_ceiling": 0.85,
    "default_profile": "",  # non-empty skips the who-is-playing menu
    "default_language": "en",
    "db_path": "",  # non-empty overrides the XDG default database location
    "tts_voice": "",  # non-empty overrides the speech engine's voice
    "pool_size": 10,  # distractors sampled from the N hardest candidates
    "show_context": True,  # show the source sentence after answering
    # code mode: restrict distractors to the item's own language instead of
    # all ingested code corpora (cross-corpus = harder, DECISIONS 024)
    "code_pool_own_language": False,
}

_TEMPLATE = """\
# PreLexy configuration. CLI flags override these per session
# (e.g. `prelexy play --new 12 --seen 8`).

# How many new words each practice session introduces.
new_words = 7

# How many previously seen words (due reviews) each session practices.
# When one kind runs out, the other fills the gap, so sessions stay
# new_words + seen_words long while there is anything to practice.
seen_words = 3

# Distractor similarity band (0.0-1.0), applied to the similarity between
# the correct definition and a candidate definition. Above the ceiling a
# candidate reads as a near-synonym and is excluded; the floor is a soft
# preference for plausible-but-wrong options. Watch real scores with
# `prelexy --debug play` before tuning.
similarity_floor = 0.45
similarity_ceiling = 0.85

# Profile used when `play` is started without --profile. Empty = ask.
default_profile = ""

# Language assumed when a command is run without --language.
default_language = "en"

# Database file. Empty = ~/.local/share/prelexy/prelexy.db (XDG). The
# PRELEXY_DB environment variable and --db both override this.
db_path = ""

# Voice passed to the speech engine for pronunciation (e.g. an espeak-ng
# voice like "en-gb", or a macOS `say` voice name). Empty = engine default.
tts_voice = ""

# Distractors are sampled from this many of the hardest candidates.
# Smaller = consistently harder options; larger = more variety.
pool_size = 10

# Show the source sentence after answering (true/false).
show_context = true

# Code mode: draw distractors only from the item's own language instead
# of all ingested code corpora (cross-corpus is harder; true = easier).
code_pool_own_language = false
"""


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return base / "prelexy" / "config.toml"


def load_config(path: Path | None = None) -> Config:
    """Defaults overlaid with the config file, creating the file on first use."""
    path = path or config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_TEMPLATE, encoding="utf-8")
    with path.open("rb") as fh:
        loaded = tomllib.load(fh)
    merged: dict[str, object] = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in loaded:
            merged[key] = loaded[key]
    _validate(merged)
    # _validate has just proven every key matches Config's declared types.
    return cast(Config, merged)


def _validate(config: Mapping[str, object]) -> None:
    """Check a freshly loaded settings mapping before it is trusted as Config."""
    for key in ("new_words", "seen_words"):
        value = config[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer, got {value!r}")
    bounds: dict[str, float] = {}
    for key in ("similarity_floor", "similarity_ceiling"):
        value = config[key]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError(f"{key} must be between 0.0 and 1.0, got {value!r}")
        bounds[key] = float(value)
    floor, ceiling = bounds["similarity_floor"], bounds["similarity_ceiling"]
    if floor >= ceiling:
        raise ValueError(f"similarity_floor ({floor}) must be below similarity_ceiling ({ceiling})")
    for key in ("default_profile", "default_language", "db_path", "tts_voice"):
        if not isinstance(config[key], str):
            raise ValueError(f"{key} must be a string, got {config[key]!r}")
    if not config["default_language"]:
        raise ValueError("default_language must not be empty")
    pool = config["pool_size"]
    if not isinstance(pool, int) or isinstance(pool, bool) or pool < 2:
        raise ValueError(f"pool_size must be an integer of at least 2, got {pool!r}")
    for key in ("show_context", "code_pool_own_language"):
        if not isinstance(config[key], bool):
            raise ValueError(f"{key} must be true or false, got {config[key]!r}")
