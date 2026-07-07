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
    code: str  # PreLexy namespace; also the spaCy/wordfreq code when natural
    kind: str = "natural"  # "natural" (spaCy/OMW/TTS) or "code" (docs-driven)
    spacy_models: tuple[str, ...] = ()  # preferred first; natural only
    wordnet_lang: str | None = None  # OMW code for glosses/pools; natural only
    espeak_voice: str | None = None  # natural only


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
    # code languages need none of the natural-language stack — their items,
    # glosses, and pools come from ingested documentation (DECISIONS 024)
    "python": Language(code="python", kind="code"),
}


def code_language_codes() -> list[str]:
    """All registered code languages — the default cross-corpus pool."""
    return [lang.code for lang in LANGUAGES.values() if lang.kind == "code"]


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
