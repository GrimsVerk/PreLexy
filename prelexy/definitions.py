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

from prelexy.languages import get_language
from prelexy.textproc import get_wordnet

# Glosses are shown in the learner's strong language. English for now —
# when profiles carry a strong_language setting this becomes per-profile.
STRONG_LANGUAGE = "en"

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/{language}/{word}"
API_TIMEOUT_SECONDS = 10
_API_LANGUAGES = {"en"}

_WORDNET_POS = {"NOUN": "n", "VERB": "v", "ADJ": "a", "ADV": "r"}
_WORDNET_POS_TO_UPOS = {"n": "NOUN", "v": "VERB", "a": "ADJ", "s": "ADJ", "r": "ADV"}
_API_POS = {"NOUN": "noun", "VERB": "verb", "ADJ": "adjective", "ADV": "adverb"}
_API_POS_TO_UPOS = {api: upos for upos, api in _API_POS.items()}


@dataclass
class Sense:
    gloss: str
    gloss_language: str
    provider: str
    # UPOS the gloss actually came from — may differ from the item's POS
    # when the lookup fell back across POS ("gartered" ADJ → verb gloss).
    # None for cache reads (the senses table stores no POS).
    pos: str | None = None


def ensure_sense(store, item, allow_api: bool = True) -> Sense | None:
    """Return a definition for an item row, caching whatever the chain finds.

    `allow_api=False` restricts the chain to offline sources — used for
    distractor pools, where firing one HTTP request per candidate word would
    be wasteful.

    Surface forms fall back to their lemma: L2 items keep the exact form
    from the source ("liep"), but dictionaries key on lemmas ("lopen") —
    you learn the surface form, defined through its lemma's meaning.
    """
    cached = store.senses_for(item["id"])
    if cached:
        top = cached[0]
        # re-clean on read so glosses cached before the sanitizer existed heal
        return Sense(clean_gloss(top["gloss"]), top["gloss_language"], top["provider"])
    sense = wordnet_sense(item["form"], item["pos"], item["language"])
    if sense is None and item["lemma"] and item["lemma"] != item["form"]:
        sense = wordnet_sense(item["lemma"], item["pos"], item["language"])
    if sense is None and allow_api:
        sense = api_sense(item["form"], item["pos"], item["language"])
    if sense is not None:
        store.add_sense(item["id"], sense.gloss, sense.gloss_language, sense.provider)
    return sense


@lru_cache(maxsize=None)
def wordnet_lemma_names(pos: str | None, language: str = "en") -> tuple[str, ...]:
    """All single-word WordNet lemma names for a POS tag (e.g. "ADJ").

    The distractor pool. English: ~20k adjectives / ~100k nouns. Other
    languages come from the Open Multilingual Wordnet (Dutch: ~37k nouns,
    ~5.6k verbs, ~1.1k adjectives — thin for adjectives, DECISIONS 023).
    """
    wordnet = get_wordnet()
    wn_lang = get_language(language).wordnet_lang
    return tuple(
        name
        for name in wordnet.all_lemma_names(_WORDNET_POS.get(pos), lang=wn_lang)
        if name.isalpha()
    )


def wordnet_sense(
    form: str,
    pos: str | None,
    language: str = "en",
    include_instances: bool = True,
) -> Sense | None:
    """Top WordNet gloss, preferring synsets that match the item's POS.

    Non-English words go through the Open Multilingual Wordnet: the synsets
    are the same language-independent objects, so `.definition()` is the
    English gloss — exactly the strong-language definition an L2 learner
    needs (DECISIONS 023).

    Instance synsets (named entities: people, cities, brands) are always
    dispreferred — for a word like "china" the porcelain sense beats the
    country. With `include_instances=False` a word whose synsets are all
    instances yields None; the distractor pool uses this, since
    "an Argentine revolutionary leader" is an absurd option (BACKLOG
    Stage 1.1, playtest 2026-07-06).
    """
    wordnet = get_wordnet()
    wn_lang = get_language(language).wordnet_lang
    synsets = wordnet.synsets(
        form, pos=_WORDNET_POS.get(pos), lang=wn_lang
    ) or wordnet.synsets(form, lang=wn_lang)
    non_instance = [s for s in synsets if not s.instance_hypernyms()]
    candidates = non_instance or (synsets if include_instances else [])
    if not candidates:
        return None
    gloss = clean_gloss(candidates[0].definition())
    if not gloss:
        return None
    return Sense(
        gloss=gloss,
        gloss_language=STRONG_LANGUAGE,
        provider="wordnet",
        pos=_WORDNET_POS_TO_UPOS.get(candidates[0].pos()),
    )


def synonym_conflict(
    target_form: str, candidate_form: str, pos: str | None, language: str = "en"
) -> bool:
    """True when the candidate is a WordNet synonym or direct relative.

    Catches true synonyms (shared lemma in any synset: sagacious/sapient,
    joy/delight, huis/woning) and direct hypernym/hyponym pairs (dog/puppy)
    — both make unfair distractors even when their gloss wording differs.
    Deliberately tight: cousin terms (joyousness/gleefulness) are NOT
    caught, because a shared-ancestor check would also exclude fair hard
    distractors across whole semantic fields (see DECISIONS 022).
    """
    wordnet = get_wordnet()
    wn_lang = get_language(language).wordnet_lang
    target_synsets = wordnet.synsets(target_form, lang=wn_lang)
    if not target_synsets:
        return False
    target_lemmas = {
        lemma
        for synset in target_synsets
        for lemma in synset.lemma_names(wn_lang)
    }
    candidate_synsets = wordnet.synsets(
        candidate_form, pos=_WORDNET_POS.get(pos), lang=wn_lang
    ) or wordnet.synsets(candidate_form, lang=wn_lang)
    for candidate_synset in candidate_synsets:
        if set(candidate_synset.lemma_names(wn_lang)) & target_lemmas:
            return True
        for target_synset in target_synsets:
            if (
                candidate_synset in target_synset.hypernyms()
                or candidate_synset in target_synset.hyponyms()
            ):
                return True
    return False


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
            sense = Sense(
                gloss=gloss,
                gloss_language=language,
                provider="api",
                pos=_API_POS_TO_UPOS.get(meaning.get("partOfSpeech")),
            )
            if meaning.get("partOfSpeech") == wanted:
                return sense
            fallback = fallback or sense
    return fallback


_KAIKKI_POS = {"noun": "NOUN", "verb": "VERB", "adj": "ADJ", "adv": "ADV"}


def import_kaikki_glosses(store, path, language: str) -> tuple[int, int]:
    """Fill missing definitions from a kaikki.org Wiktionary dump (JSONL).

    Works with both the deprecated per-language extracts and the
    future-proof raw wiktextract dump (kaikki.org/dictionary/rawdata.html):
    `.gz` files are streamed directly (no 20 GB decompress to disk), and
    entries are filtered by `lang_code` since the raw dump mixes all
    languages. Fills only items that have no cached sense; entry
    preference: real gloss + POS match > real gloss > form-of gloss (an
    item's lemma entry usually supplies the real gloss — see
    2026-07-07 playtest, "inflection of abonneren"). Returns
    (filled, missing_before).
    """
    missing = store.items_missing_senses(language)
    by_word: dict[str, list] = {}
    for item in missing:
        by_word.setdefault(item["form"], []).append(item)
        if item["lemma"] and item["lemma"] != item["form"]:
            by_word.setdefault(item["lemma"], []).append(item)

    # item id → ((real gloss, pos matched), gloss); higher tuple wins
    best: dict[int, tuple[tuple[bool, bool], str]] = {}
    with _open_extract(path) as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry_lang = entry.get("lang_code")
            if entry_lang is not None and entry_lang != language:
                continue
            word = entry.get("word")
            if word not in by_word:
                continue
            gloss, is_form_of = _kaikki_gloss(entry)
            if not gloss:
                continue
            entry_pos = _KAIKKI_POS.get(entry.get("pos"))
            for item in by_word[word]:
                rank = (not is_form_of, bool(entry_pos and entry_pos == item["pos"]))
                current = best.get(item["id"])
                if current is None or rank > current[0]:
                    best[item["id"]] = (rank, gloss)

    for item_id, (_, gloss) in best.items():
        store.add_sense(item_id, gloss, STRONG_LANGUAGE, "wiktionary")
    return len(best), len(missing)


def _open_extract(path):
    """Open a kaikki extract for text reading, gz or plain, by magic bytes."""
    import gzip

    with open(path, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _kaikki_gloss(entry) -> tuple[str | None, bool]:
    """Best gloss in an entry and whether it is only a form-of reference."""
    form_of_gloss = None
    for sense in entry.get("senses") or []:
        glosses = sense.get("glosses") or []
        gloss = glosses[0].strip() if glosses and isinstance(glosses[0], str) else ""
        if not gloss:
            continue
        if sense.get("form_of") or "form-of" in (sense.get("tags") or []):
            form_of_gloss = form_of_gloss or gloss.rstrip(":")
            continue
        return gloss, False
    return form_of_gloss, True


def _fetch_api_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=API_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
