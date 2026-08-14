"""YouTube transcript fetching (docs/BACKLOG.md Stage 2b).

Subtitles come from yt-dlp — an external tool treated like espeak
(shutil.which check, install hint when absent): free, and the standard
way to get YouTube's (auto-generated) subtitles without an API key.
Fetched `.vtt` files are ordinary subtitle files for `prelexy ingest`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

INSTALL_HINT = (
    "yt-dlp not found — it does the actual YouTube fetching. Install it with: pip install yt-dlp"
)


def fetch_subtitles(
    url: str, language: str, dest: Path, archive: Path | None = None
) -> list[Path] | None:
    """Download (auto-)subtitles for a video/playlist/channel URL.

    Returns the list of newly created .vtt files (empty when nothing new,
    e.g. every episode is already in the archive), or None when yt-dlp is
    not installed. yt-dlp's own progress output goes to the terminal.
    """
    if shutil.which("yt-dlp") is None:
        return None
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    before = set(dest.rglob("*.vtt"))
    command = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        language,
        "--sub-format",
        "vtt",
        "--output",
        str(dest / "%(channel)s - %(title)s.%(ext)s"),
    ]
    if archive is not None:
        command += ["--download-archive", str(archive)]
    command.append(url)
    subprocess.run(command, check=False)
    return sorted(set(dest.rglob("*.vtt")) - before)
