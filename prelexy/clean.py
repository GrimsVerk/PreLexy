"""Input-text cleanup for OCR-damaged sources.

Deliberately conservative, source-agnostic rules — deep OCR repair stays
out of scope (docs/DECISIONS.md 008); this fixes the systematic artifacts
that poison extraction and context sentences, of the kind found in the
Dorian Gray scan:

- a standalone pipe is OCR for the pronoun "I" ("| dare say")
- "word- word" or a hyphen at line end is a hyphenation split
  ("moss- coloured", "moss-\\ncoloured"); the hyphen is kept, since
  telling "moss-coloured" from a split "won-derful" apart needs a
  dictionary — the extraction filter quarantines the rare misjoins
- lines with no letters at all are page furniture ("= ", page numbers)
- runs of blank lines collapse to one paragraph break
"""

from __future__ import annotations

import re

SUBTITLE_SUFFIXES = {".srt", ".vtt"}

_TIMESTAMP = re.compile(r"-->")
_CUE_NUMBER = re.compile(r"^\d+$")
_INLINE_TAG = re.compile(r"<[^>]+>")
_SENTENCE_END = re.compile(r"(?<=[.!?…]) ")
_PARAGRAPH_TARGET = 1500  # characters; keeps spaCy chunking bounded

_PIPE_AS_I = re.compile(r"(?<!\w)\|(?!\w)")
# "- word", "-\nword", and "- \nword" (hyphen, trailing space, newline) are
# all hyphenation splits; a blank line after the hyphen is a paragraph
# boundary and is left alone.
_BROKEN_HYPHEN = re.compile(r"(\w)-(?:[ \t]*\n[ \t]*|[ \t]+)(\w)")
_HAS_LETTER = re.compile(r"[^\W\d_]")  # any unicode letter
_BLANK_RUNS = re.compile(r"\n{3,}")


def strip_subtitles(text: str) -> str:
    """Turn an .srt/.vtt subtitle file into plain prose.

    Drops cue numbers, timestamps, the WEBVTT header, NOTE/STYLE blocks,
    and inline tags. Cue texts are joined with spaces (sentences routinely
    span cue boundaries), then re-paragraphed at sentence ends so the
    extraction pipeline's paragraph chunking stays bounded.
    """
    lines = []
    skipping_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if skipping_block:
            if not line:
                skipping_block = False
            continue
        if line.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            skipping_block = True
            continue
        if not line or _CUE_NUMBER.match(line) or _TIMESTAMP.search(line):
            continue
        lines.append(line)

    flat = _INLINE_TAG.sub("", " ".join(lines))
    flat = " ".join(flat.split())
    paragraphs, current, length = [], [], 0
    for piece in _SENTENCE_END.split(flat):
        current.append(piece)
        length += len(piece)
        if length > _PARAGRAPH_TARGET:
            paragraphs.append(" ".join(current))
            current, length = [], 0
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def clean_text(text: str) -> tuple[str, dict[str, int]]:
    """Return (cleaned text, counts of what each rule changed)."""
    counts: dict[str, int] = {}
    text, counts["pipe-as-I"] = _PIPE_AS_I.subn("I", text)
    text, counts["broken-hyphen"] = _BROKEN_HYPHEN.subn(r"\1-\2", text)

    kept_lines = []
    dropped = 0
    for line in text.split("\n"):
        line = line.rstrip()
        if line and not _HAS_LETTER.search(line):
            dropped += 1
            continue
        kept_lines.append(line)
    counts["letterless-line"] = dropped
    text = "\n".join(kept_lines)

    text, counts["blank-run"] = _BLANK_RUNS.subn("\n\n", text)
    return text, counts
