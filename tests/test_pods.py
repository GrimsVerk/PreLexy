import subprocess
from pathlib import Path
from typing import Any

import pytest

import prelexy.pods as pods


def test_fetch_returns_none_without_ytdlp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pods.shutil, "which", lambda name: None)
    assert pods.fetch_subtitles("https://youtube.com/x", "nl", tmp_path) is None


def test_fetch_invokes_ytdlp_and_reports_new_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pods.shutil, "which", lambda name: "/usr/bin/yt-dlp")
    (tmp_path / "Tweakers - Old.nl.vtt").write_text("old")  # pre-existing
    calls = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        (tmp_path / "Tweakers - Ep1.nl.vtt").write_text("WEBVTT\n")

    monkeypatch.setattr(pods.subprocess, "run", fake_run)
    archive = tmp_path / "archive.txt"
    new = pods.fetch_subtitles(
        "https://www.youtube.com/@tweakers/podcasts", "nl", tmp_path, archive=archive
    )
    assert new == [tmp_path / "Tweakers - Ep1.nl.vtt"]

    (command,) = calls
    assert command[0] == "yt-dlp"
    assert "--skip-download" in command
    assert command[command.index("--sub-langs") + 1] == "nl"
    assert command[command.index("--download-archive") + 1] == str(archive)
    assert command[-1] == "https://www.youtube.com/@tweakers/podcasts"


def test_fetch_creates_dest_and_handles_nothing_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pods.shutil, "which", lambda name: "/usr/bin/yt-dlp")
    monkeypatch.setattr(pods.subprocess, "run", lambda command, **kwargs: None)
    dest = tmp_path / "does" / "not" / "exist"
    assert pods.fetch_subtitles("https://youtube.com/x", "en", dest) == []
    assert dest.is_dir()
