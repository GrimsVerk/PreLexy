import subprocess

import prelexy.speech as speech


def test_linux_prefers_espeak_ng(monkeypatch):
    monkeypatch.setattr(speech.platform, "system", lambda: "Linux")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "espeak-ng")
    assert speech._command("gaunt", "en") == ["espeak-ng", "-v", "en-us", "gaunt"]
    assert speech._command("lopen", "nl")[2] == "nl"


def test_macos_uses_say(monkeypatch):
    monkeypatch.setattr(speech.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "say")
    assert speech._command("gaunt", "en") == ["say", "gaunt"]


def test_windows_escapes_quotes(monkeypatch):
    monkeypatch.setattr(speech.platform, "system", lambda: "Windows")
    monkeypatch.setattr(speech.shutil, "which", lambda name: name == "powershell")
    command = speech._command("o'clock", "en")
    assert command[0] == "powershell"
    assert "o''clock" in command[-1]


def test_no_engine_returns_false(monkeypatch):
    monkeypatch.setattr(speech.platform, "system", lambda: "Linux")
    monkeypatch.setattr(speech.shutil, "which", lambda name: False)
    assert speech.pronounce("gaunt") is False


def test_pronounce_runs_the_command_and_survives_failure(monkeypatch):
    monkeypatch.setattr(speech, "_command", lambda word, language: ["fake-tts", word])
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(speech.subprocess, "run", fake_run)
    assert speech.pronounce("gaunt") is True
    assert calls == [["fake-tts", "gaunt"]]

    def failing_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(speech.subprocess, "run", failing_run)
    assert speech.pronounce("gaunt") is False
