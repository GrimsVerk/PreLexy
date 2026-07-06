"""Multiple-choice question generation (docs/DESIGN.md, "MCQ exercise").

The question is "pick the correct definition". Distractors are real WordNet
definitions of other same-POS words drawn from all of WordNet — never from
the words currently being studied — and are picked purely by embedding
similarity: inside the (floor, ceiling) band, close enough to be plausible
but not a near-synonym. Rarity plays no part: the player only ever sees the
gloss, never the distractor word itself, so the hidden word's rarity cannot
make an option more or less tempting.

When similarity is unavailable (no vector model loaded, or no vector for a
word), candidates fall back to random same-POS picks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from prelexy.definitions import ensure_sense, wordnet_lemma_names, wordnet_sense

# The distractor similarity band. Above the ceiling a candidate is a
# near-synonym of the target (an ambiguous option is unfair); below the
# floor its gloss is from another domain entirely (too obviously wrong).
# Tune empirically as playtesting data accumulates.
SIMILARITY_FLOOR = 0.35
SIMILARITY_CEILING = 0.7

N_OPTIONS = 4

# Candidates examined per question before settling for what was found.
_SCAN_LIMIT = 500


@dataclass
class Question:
    item_id: int
    form: str
    context: str | None  # example sentence from the source text
    options: list[str]  # glosses, shuffled
    answer: int  # index into options of the correct gloss


def build_question(store, item, similarity=None, rng=None) -> Question | None:
    """Build an MCQ for an item row.

    Returns None when no definition can be found for the item, or when no
    usable distractor exists at all.
    """
    rng = rng or random.Random()
    sense = ensure_sense(store, item)
    if sense is None:
        return None
    distractors = _distractors(item, sense.gloss, similarity, rng)
    if not distractors:
        return None
    options = [sense.gloss, *distractors]
    rng.shuffle(options)
    return Question(
        item_id=item["id"],
        form=item["form"],
        context=store.example_for(item["id"]),
        options=options,
        answer=options.index(sense.gloss),
    )


def _distractors(item, correct_gloss, similarity, rng) -> list[str]:
    """Up to N_OPTIONS-1 distractor glosses, in-band candidates preferred.

    Candidates without a similarity score (no provider, or no vector for
    the pair) accumulate as a fallback used only to top up.
    """
    target_lemma = (item["lemma"] or item["form"]).lower()
    needed = N_OPTIONS - 1
    banded: list[str] = []
    unscored: list[str] = []
    for scanned, candidate in enumerate(_wordnet_candidates(item["pos"], item["language"], rng)):
        if len(banded) == needed or scanned == _SCAN_LIMIT:
            break
        if candidate == target_lemma:
            continue
        score = similarity.similarity(item["form"], candidate) if similarity else None
        if score is not None and not (SIMILARITY_FLOOR < score < SIMILARITY_CEILING):
            continue
        sense = wordnet_sense(candidate, item["pos"], item["language"])
        if sense is None or sense.gloss == correct_gloss:
            continue
        if sense.gloss not in banded and sense.gloss not in unscored:
            (banded if score is not None else unscored).append(sense.gloss)
        if similarity is None and len(unscored) == needed:
            break
    return (banded + unscored)[:needed]


def _wordnet_candidates(pos, language, rng) -> list[str]:
    """A fresh random sample of same-POS WordNet lemmas for one question."""
    names = wordnet_lemma_names(pos, language)
    return rng.sample(names, min(len(names), _SCAN_LIMIT))
