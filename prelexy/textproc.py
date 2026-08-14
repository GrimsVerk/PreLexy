"""Text processing: turn raw text into ranked, learnable candidate items.

Pipeline (docs/DESIGN.md, "Extraction pipeline"):

    text → paragraphs → spaCy (tokenize, tag, lemmatize, sentence-split)
         → extraction policy (what counts as an item, per language)
         → filters (stopwords, proper nouns, dictionary membership)
         → rarity ranking (wordfreq Zipf scale, rarest first)
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from wordfreq import zipf_frequency

from prelexy.languages import get_language

# Never learnable vocabulary: proper nouns (character names would flood the
# candidate list), numbers, symbols, junk, punctuation, whitespace.
_SKIP_POS = {"PROPN", "NUM", "SYM", "X", "PUNCT", "SPACE"}

_MIN_LENGTH = 2


@dataclass
class Candidate:
    """A learnable item found in a text, with every place it occurred."""

    form: str  # the string as practiced (lemma for English; see item_form)
    lemma: str
    pos: str
    zipf: float  # wordfreq Zipf scale: ~7 = very common, <3 = rare, 0 = unknown
    occurrences: list[tuple[str, int]] = field(default_factory=list)  # (sentence, char offset)


def load_nlp(language: str = "en") -> Any:
    """Load the spaCy pipeline for a language (NER disabled; not needed).

    The model names come from the language registry (prelexy/languages.py);
    an unsupported language raises UnsupportedLanguageError there.
    """
    import spacy

    registered = get_language(language)
    if registered.kind != "natural":
        raise ValueError(
            f"{language!r} is a code language — its items come from documentation; "
            "use `prelexy ingest-docs` instead of text extraction."
        )
    names = registered.spacy_models
    for name in names:
        try:
            return spacy.load(name, disable=["ner"])
        except OSError:
            continue
    raise OSError(
        f"No spaCy model installed for language {language!r}. "
        f"Run: python -m spacy download {names[0]}"
    )


def item_form(token: Any, language: str) -> str:
    """Extraction policy: which string is practiced for this token.

    English (fluent-reader mode) uses lemmas; other languages default to the
    exact surface form (L2 mode: learn "was" only if the source says "was").
    See docs/DESIGN.md, "The item abstraction".
    """
    if language == "en":
        return str(token.lemma_).lower()
    return str(token.text).lower()


@cache
def in_dictionary(form: str, language: str = "en") -> bool:
    """Membership gate: only words the dictionary knows are learnable.

    Doubles as the OCR/transcription-noise filter (garbage tokens have no
    dictionary entry). English uses WordNet; other languages use wordfreq
    membership (zipf > 0) — OMW coverage is too thin to gate on for them
    (DECISIONS 023).
    """
    if language == "en":
        return bool(get_wordnet().synsets(form))
    if get_language(language).kind != "natural":
        return True  # code items come from doc inventories, already curated
    return zipf_frequency(form, language) > 0


def get_wordnet() -> Any:
    """Return the WordNet corpus, downloading its data on first use."""
    import nltk
    from nltk.corpus import wordnet

    try:
        wordnet.ensure_loaded()
    except LookupError:
        nltk.download("wordnet", quiet=True)
        nltk.download("omw-2.0", quiet=True)
    return wordnet


def extract_candidates(text: str, language: str = "en", nlp: Any = None) -> list[Candidate]:
    """Extract ranked candidate items from raw text, rarest first."""
    nlp = nlp or load_nlp(language)
    docs = nlp.pipe(_paragraphs(text), as_tuples=True)
    return collect_candidates(docs, language)


def collect_candidates(docs: Iterable[tuple[Any, int]], language: str) -> list[Candidate]:
    """Aggregate (doc, char_offset) pairs into ranked candidates."""
    found: dict[str, Candidate] = {}
    for doc, offset in docs:
        for token in doc:
            if not _learnable(token):
                continue
            form = item_form(token, language)
            if len(form) < _MIN_LENGTH or not in_dictionary(form, language):
                continue
            candidate = found.get(form)
            if candidate is None:
                candidate = found[form] = Candidate(
                    form=form,
                    lemma=token.lemma_.lower(),
                    pos=token.pos_,
                    zipf=zipf_frequency(form, language),
                )
            sentence = " ".join(token.sent.text.split())
            candidate.occurrences.append((sentence, offset + token.idx))
    return sorted(found.values(), key=lambda c: (c.zipf, c.form))


def _learnable(token: Any) -> bool:
    return token.is_alpha and not token.is_stop and token.pos_ not in _SKIP_POS


def _paragraphs(text: str) -> Iterator[tuple[str, int]]:
    """Yield (paragraph, char_offset) pairs, splitting on blank lines.

    Paragraph-sized chunks keep spaCy's memory use flat on book-length texts.
    """
    offset = 0
    for block in text.split("\n\n"):
        if block.strip():
            yield block, offset
        offset += len(block) + 2
