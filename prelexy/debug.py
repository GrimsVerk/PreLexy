"""Opt-in diagnostics.

Enable with the top-level CLI flag (`prelexy --debug <command>`) or by
setting PRELEXY_DEBUG=1. Output goes to stderr, dimmed, so it never mixes
with game output or breaks piping.

Extending: any module may call `log(channel, message)` unconditionally —
nothing is printed unless debugging is on, so calls cost next to nothing.
Pick a short channel name per subsystem ("mcq", "scheduler", ...); no
registration is needed, and grep-ability by channel is the point.
"""

from __future__ import annotations

import os

import click

_enabled = False


def enable(on: bool = True) -> None:
    global _enabled
    _enabled = on


def enabled() -> bool:
    return _enabled or os.environ.get("PRELEXY_DEBUG", "") not in ("", "0")


def log(channel: str, message: str) -> None:
    if enabled():
        click.secho(f"[{channel}] {message}", dim=True, err=True)
