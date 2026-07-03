"""Definition lookup: offline-first, everything cached.

Chain (docs/DESIGN.md, "Definitions"): the senses cache is consulted first,
then WordNet (offline), then the free dictionaryapi.dev API as a last resort.
Every hit is written back to the cache, so a word is looked up online at most
once and offline coverage improves with use.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from prelexy.textproc import get_wordnet

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/{language}/{word}"
API_TIMEOUT_SECONDS = 10
_API_LANGUAGES = {"en"}

_WORDNET_POS = {"NOUN": "n", "VERB": "v", "ADJ": "a", "ADV": "r"}
_API_POS = {"NOUN": "noun", "VERB": "verb", "ADJ": "adjective", "ADV": "adverb"}


@dataclass
class Sense:
    gloss: str
    gloss_language: str
    provider: str


def ensure_sense(store, item, allow_api: bool = True) -> Sense | None:
    """Return a definition for an item row, caching whatever the chain finds.

    `allow_api=False` restricts the chain to offline sources — used for
    distractor pools, where firing one HTTP request per candidate word would
    be wasteful.
    """
    cached = store.senses_for(item["id"])
    if cached:
        top = cached[0]
        return Sense(top["gloss"], top["gloss_language"], top["provider"])
    sense = wordnet_sense(item["form"], item["pos"], item["language"])
    if sense is None and allow_api:
        sense = api_sense(item["form"], item["pos"], item["language"])
    if sense is not None:
        store.add_sense(item["id"], sense.gloss, sense.gloss_language, sense.provider)
    return sense


def wordnet_sense(form: str, pos: str | None, language: str = "en") -> Sense | None:
    """Top WordNet gloss, preferring synsets that match the item's POS."""
    if language != "en":
        return None
    wordnet = get_wordnet()
    synsets = wordnet.synsets(form, pos=_WORDNET_POS.get(pos)) or wordnet.synsets(form)
    if not synsets:
        return None
    return Sense(gloss=synsets[0].definition(), gloss_language="en", provider="wordnet")


def api_sense(form: str, pos: str | None, language: str = "en") -> Sense | None:
    """Top gloss from dictionaryapi.dev, preferring the item's POS.

    Returns None on any failure — unknown word, offline, blocked network —
    so the chain degrades to "no definition" instead of crashing.
    """
    if language not in _API_LANGUAGES:
        return None
    url = API_URL.format(language=language, word=urllib.parse.quote(form))
    payload = _fetch_api_json(url)
    if not isinstance(payload, list):
        return None
    wanted = _API_POS.get(pos)
    fallback = None
    for entry in payload:
        for meaning in entry.get("meanings", []):
            definitions = meaning.get("definitions") or []
            gloss = definitions[0].get("definition") if definitions else None
            if not gloss:
                continue
            sense = Sense(gloss=gloss, gloss_language=language, provider="api")
            if meaning.get("partOfSpeech") == wanted:
                return sense
            fallback = fallback or sense
    return fallback


def _fetch_api_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=API_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
