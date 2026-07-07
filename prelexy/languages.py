"""Language support registry (docs/DESIGN.md; ROADMAP v2).

A language is supported when the whole stack supports it: a spaCy pipeline,
wordfreq data, a gloss source, and a TTS voice. Requests for anything else
raise UnsupportedLanguageError with the missing pieces spelled out — such
languages belong in BACKLOG "Deferred" with that note, never half-built.
"""

from __future__ import annotations

from dataclasses import dataclass


class UnsupportedLanguageError(ValueError):
    pass


@dataclass(frozen=True)
class Language:
    code: str  # PreLexy namespace; also the spaCy/wordfreq code
    spacy_models: tuple[str, ...]  # preferred first
    wordnet_lang: str  # OMW language code for glosses and candidate pools
    espeak_voice: str


LANGUAGES = {
    "en": Language(
        code="en",
        spacy_models=("en_core_web_md", "en_core_web_sm"),
        wordnet_lang="eng",
        espeak_voice="en-us",
    ),
    "nl": Language(
        code="nl",
        spacy_models=("nl_core_news_md", "nl_core_news_sm"),
        wordnet_lang="nld",  # Open Dutch WordNet via OMW; see DECISIONS 023
        espeak_voice="nl",
    ),
}


def get_language(code: str) -> Language:
    try:
        return LANGUAGES[code]
    except KeyError:
        supported = ", ".join(sorted(LANGUAGES))
        raise UnsupportedLanguageError(
            f"Language {code!r} is not supported yet (supported: {supported}). "
            "Adding one needs a spaCy pipeline, wordfreq data, a gloss source, "
            "and a TTS voice — see docs/BACKLOG.md 'Deferred' for the waiting list."
        ) from None
