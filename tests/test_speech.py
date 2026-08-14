import subprocess
from typing import Any

import pytest

import prelexy.speech as speech


def test_linux_prefers_espeak_ng(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech.platform, "system", lambda: "Linux")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "espeak-ng")
    assert speech._command("gaunt", "en") == ["espeak-ng", "-v", "en-us", "gaunt"]
    assert speech._command("lopen", "nl")[2] == "nl"


def test_macos_uses_say(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "say")
    assert speech._command("gaunt", "en") == ["say", "gaunt"]


def test_voice_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech.platform, "system", lambda: "Linux")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "espeak-ng")
    assert speech._command("gaunt", "en", voice="en-gb")[2] == "en-gb"
    monkeypatch.setattr(speech.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "say")
    assert speech._command("gaunt", "en", voice="Moira") == ["say", "-v", "Moira", "gaunt"]


def test_windows_escapes_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech.platform, "system", lambda: "Windows")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "powershell")
    command = speech._command("o'clock", "en")
    assert command[0] == "powershell"
    assert "o''clock" in command[-1]


def test_no_engine_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech.platform, "system", lambda: "Linux")
    monkeypatch.setattr(speech.shutil, "which", lambda name: False)
    assert speech.pronounce("gaunt") is False


def test_pronounce_runs_the_command_and_survives_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech, "_command", lambda word, language, voice=None: ["fake-tts", word])
    calls = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(speech.subprocess, "run", fake_run)
    assert speech.pronounce("gaunt") is True
    assert calls == [["fake-tts", "gaunt"]]

    def failing_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(speech.subprocess, "run", failing_run)
    assert speech.pronounce("gaunt") is False
