"""Documentation processing for code languages (docs/DESIGN.md, v3).

Turns a locally downloaded Sphinx HTML documentation tree (CPython and
most Python-ecosystem docs) into learnable items: `objects.inv` — the
intersphinx inventory shipped at the docs root — lists every documented
object with its role and page anchor; the page HTML supplies each
object's signature and the first sentence of its description, which is
the gloss (docs are their own dictionary). Stdlib only: zlib for the
inventory, html.parser for the pages.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

# Inventory roles worth memorizing. Attributes/constants/modules are
# skipped in v3.0 — callables and classes are the API surface one drills.
LEARNABLE_ROLES = {
    "function",
    "method",
    "class",
    "classmethod",
    "staticmethod",
    "exception",
    "decorator",
}

_INVENTORY_LINE = re.compile(
    r"(?P<name>\S+)\s+(?P<domain>[^\s:]+):(?P<role>\S+)\s+"
    r"(?P<priority>-?\d+)\s+(?P<uri>\S+)\s+(?P<dispname>.*)"
)
_FIRST_SENTENCE = re.compile(r"(?<=[.!?])\s")


@dataclass(frozen=True)
class DocEntry:
    name: str  # qualified: itertools.chain
    role: str  # function / method / class / ...
    page: str  # library/itertools.html (relative to the docs root)
    anchor: str  # itertools.chain

    @property
    def module(self) -> str:
        return self.name.rsplit(".", 1)[0] if "." in self.name else self.name


def parse_inventory(path: Path) -> list[DocEntry]:
    """Read a Sphinx objects.inv (version 2) into learnable entries."""
    raw = Path(path).read_bytes()
    if not raw.startswith(b"# Sphinx inventory version 2"):
        raise ValueError(f"{path} is not a Sphinx inventory version 2 file")
    # four comment header lines, then zlib-compressed payload
    payload = raw.split(b"\n", 4)[4]
    entries = []
    for line in zlib.decompress(payload).decode("utf-8").splitlines():
        match = _INVENTORY_LINE.match(line)
        if not match:
            continue
        if match["domain"] != "py" or match["role"] not in LEARNABLE_ROLES:
            continue
        name = match["name"]
        uri = match["uri"]
        # a trailing "$" abbreviates "anchor equals the entry name"
        if uri.endswith("$"):
            uri = uri[:-1] + name
        page, _, anchor = uri.partition("#")
        entries.append(DocEntry(name=name, role=match["role"], page=page, anchor=anchor))
    return entries


class _SphinxGlossParser(HTMLParser):
    """Pull (signature, first description paragraph) per dt-id from a page.

    Sphinx renders each object as `<dt id="qualified.name">signature</dt>`
    followed by a `<dd>` whose first `<p>` is the description.
    """

    def __init__(self, wanted_ids: set[str]):
        super().__init__(convert_charrefs=True)
        self.wanted = wanted_ids
        self.results: dict[str, tuple[str, str]] = {}  # id → (signature, para)
        self._current: str | None = None
        self._sig_parts: list[str] = []
        self._awaiting_dd: str | None = None
        self._sig_of: dict[str, str] = {}
        self._para_parts: list[str] = []
        self._in_para = False
        self._dd_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "dt" and attrs.get("id") in self.wanted:
            self._current = attrs["id"]
            self._sig_parts = []
        elif tag == "dd" and self._awaiting_dd and not self._dd_depth:
            self._dd_depth = 1
        elif tag == "p" and self._dd_depth and not self._in_para:
            self._in_para = True
            self._para_parts = []

    def handle_endtag(self, tag):
        if tag == "dt" and self._current:
            signature = " ".join("".join(self._sig_parts).split()).rstrip("¶")
            self._sig_of[self._current] = signature.strip()
            self._awaiting_dd = self._current
            self._current = None
        elif tag == "p" and self._in_para:
            paragraph = " ".join("".join(self._para_parts).split())
            entry_id = self._awaiting_dd
            if entry_id and paragraph:
                self.results[entry_id] = (self._sig_of.get(entry_id, ""), paragraph)
            self._awaiting_dd = None
            self._in_para = False
            self._dd_depth = 0

    def handle_data(self, data):
        if self._current is not None:
            self._sig_parts.append(data)
        elif self._in_para:
            self._para_parts.append(data)


def extract_glosses(html_text: str, wanted_ids: set[str]) -> dict[str, tuple[str, str]]:
    """{anchor: (signature, first sentence of the description)} for a page."""
    parser = _SphinxGlossParser(wanted_ids)
    parser.feed(html_text)
    return {
        anchor: (signature, _FIRST_SENTENCE.split(paragraph, 1)[0].strip())
        for anchor, (signature, paragraph) in parser.results.items()
    }
