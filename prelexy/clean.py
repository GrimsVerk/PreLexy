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

_PIPE_AS_I = re.compile(r"(?<!\w)\|(?!\w)")
# "- word", "-\nword", and "- \nword" (hyphen, trailing space, newline) are
# all hyphenation splits; a blank line after the hyphen is a paragraph
# boundary and is left alone.
_BROKEN_HYPHEN = re.compile(r"(\w)-(?:[ \t]*\n[ \t]*|[ \t]+)(\w)")
_HAS_LETTER = re.compile(r"[^\W\d_]")  # any unicode letter
_BLANK_RUNS = re.compile(r"\n{3,}")


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
