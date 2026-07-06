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
    "session_length": 10,  # words per session (reviews + new)
    "new_ratio": 0.3,  # fraction of each session reserved for new words
}

_TEMPLATE = """\
# PreLexy configuration. CLI flags override these per session
# (e.g. `prelexy play --length 20 --new-ratio 0.5`).

# Words per practice session (due reviews + new words).
session_length = 10

# Fraction of each session reserved for new words, 0.0-1.0. This takes
# precedence over the review backlog: with 0.3 and a length of 10, at
# least 3 slots go to new words whenever any exist. When there are no
# new (or no due) words left, the remainder fills from the other kind.
new_ratio = 0.3
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
    length = config["session_length"]
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        raise ValueError(f"session_length must be a positive integer, got {length!r}")
    ratio = config["new_ratio"]
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not 0.0 <= ratio <= 1.0:
        raise ValueError(f"new_ratio must be between 0.0 and 1.0, got {ratio!r}")
