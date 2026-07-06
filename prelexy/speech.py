"""Word pronunciation via the operating system's speech engine.

Free and offline: macOS ships `say`, Windows ships SAPI (reached through
PowerShell), Linux needs `espeak-ng` (or `espeak`) installed. Future
upgrade noted in docs/DESIGN.md: cached human recordings from Wiktionary.
"""

from __future__ import annotations

import platform
import shutil
import subprocess

_ESPEAK_VOICES = {"en": "en-us", "nl": "nl"}

INSTALL_HINT = (
    "No speech engine found. macOS and Windows ship with one built in; "
    "on Linux install espeak-ng (e.g. `sudo apt install espeak-ng`)."
)


def pronounce(word: str, language: str = "en") -> bool:
    """Speak a word aloud; False when no engine is available or it fails."""
    command = _command(word, language)
    if command is None:
        return False
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _command(word: str, language: str) -> list[str] | None:
    system = platform.system()
    if system == "Darwin" and shutil.which("say"):
        return ["say", word]
    if system == "Windows" and shutil.which("powershell"):
        safe_word = word.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
            f".Speak('{safe_word}')"
        )
        return ["powershell", "-NoProfile", "-Command", script]
    for engine in ("espeak-ng", "espeak"):
        if shutil.which(engine):
            return [engine, "-v", _ESPEAK_VOICES.get(language, "en-us"), word]
    return None
