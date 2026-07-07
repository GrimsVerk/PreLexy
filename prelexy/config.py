"""User configuration file (docs/DESIGN.md).

Lives at `$XDG_CONFIG_HOME/prelexy/config.toml` (default
`~/.config/prelexy/config.toml`) and is created with commented defaults on
first use so it is discoverable. Precedence everywhere:
CLI flag > config file > built-in default.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULTS = {
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
"""


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return base / "prelexy" / "config.toml"


def load_config(path: Path | None = None) -> dict:
    """Defaults overlaid with the config file, creating the file on first use."""
    path = path or config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_TEMPLATE, encoding="utf-8")
    with path.open("rb") as fh:
        loaded = tomllib.load(fh)
    config = dict(DEFAULTS)
    config.update((key, loaded[key]) for key in DEFAULTS if key in loaded)
    _validate(config)
    return config


def _validate(config: dict) -> None:
    for key in ("new_words", "seen_words"):
        value = config[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer, got {value!r}")
    floor, ceiling = config["similarity_floor"], config["similarity_ceiling"]
    for key, value in (("similarity_floor", floor), ("similarity_ceiling", ceiling)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{key} must be between 0.0 and 1.0, got {value!r}")
    if floor >= ceiling:
        raise ValueError(
            f"similarity_floor ({floor}) must be below similarity_ceiling ({ceiling})"
        )
    for key in ("default_profile", "default_language", "db_path", "tts_voice"):
        if not isinstance(config[key], str):
            raise ValueError(f"{key} must be a string, got {config[key]!r}")
    if not config["default_language"]:
        raise ValueError("default_language must not be empty")
    pool = config["pool_size"]
    if not isinstance(pool, int) or isinstance(pool, bool) or pool < 2:
        raise ValueError(f"pool_size must be an integer of at least 2, got {pool!r}")
    if not isinstance(config["show_context"], bool):
        raise ValueError(f"show_context must be true or false, got {config['show_context']!r}")
