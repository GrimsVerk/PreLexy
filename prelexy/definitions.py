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
from functools import lru_cache

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
        # re-clean on read so glosses cached before the sanitizer existed heal
        return Sense(clean_gloss(top["gloss"]), top["gloss_language"], top["provider"])
    sense = wordnet_sense(item["form"], item["pos"], item["language"])
    if sense is None and allow_api:
        sense = api_sense(item["form"], item["pos"], item["language"])
    if sense is not None:
        store.add_sense(item["id"], sense.gloss, sense.gloss_language, sense.provider)
    return sense


@lru_cache(maxsize=None)
def wordnet_lemma_names(pos: str | None, language: str = "en") -> tuple[str, ...]:
    """All single-word WordNet lemma names for a POS tag (e.g. "ADJ").

    The distractor pool: ~20k adjectives / ~100k nouns, so options never
    have to come from the words currently being studied.
    """
    if language != "en":
        return ()
    wordnet = get_wordnet()
    return tuple(
        name
        for name in wordnet.all_lemma_names(_WORDNET_POS.get(pos))
        if name.isalpha()
    )


def wordnet_sense(
    form: str,
    pos: str | None,
    language: str = "en",
    include_instances: bool = True,
) -> Sense | None:
    """Top WordNet gloss, preferring synsets that match the item's POS.

    Instance synsets (named entities: people, cities, brands) are always
    dispreferred — for a word like "china" the porcelain sense beats the
    country. With `include_instances=False` a word whose synsets are all
    instances yields None; the distractor pool uses this, since
    "an Argentine revolutionary leader" is an absurd option (BACKLOG
    Stage 1.1, playtest 2026-07-06).
    """
    if language != "en":
        return None
    wordnet = get_wordnet()
    synsets = wordnet.synsets(form, pos=_WORDNET_POS.get(pos)) or wordnet.synsets(form)
    non_instance = [s for s in synsets if not s.instance_hypernyms()]
    candidates = non_instance or (synsets if include_instances else [])
    if not candidates:
        return None
    gloss = clean_gloss(candidates[0].definition())
    if not gloss:
        return None
    return Sense(gloss=gloss, gloss_language="en", provider="wordnet")


def clean_gloss(gloss: str) -> str:
    """Strip WordNet gloss residue.

    Raw WordNet glosses embed quoted usage examples with author
    attributions; nltk moves the quotes into .examples() but can leave the
    empty separators and the attribution behind, e.g.
    "lean and wrinkled by shrinkage as from age or illness; ; ; ; -W.F.Starkie".
    Real multi-part definitions ("a; b") are preserved.
    """
    parts = [part.strip() for part in gloss.split(";")]
    return "; ".join(part for part in parts if part and not part.startswith("-"))


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
