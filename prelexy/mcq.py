"""Multiple-choice question generation (docs/DESIGN.md, "MCQ exercise").

The question is "pick the correct definition". Distractors are real WordNet
definitions of other same-POS words drawn from all of WordNet — never from
the words currently being studied — picked purely by embedding similarity
**between the definitions themselves**: the correct gloss versus each
candidate's gloss. Comparing definitions rather than words matters twice
over: rare literary words are usually missing from the vector table (so
word-level similarity was silently falling back to random), and the gloss
is the thing the player actually reads — its confusability IS the
difficulty. Rarity plays no part.

When similarity is unavailable entirely (no vector model loaded), candidates
fall back to random same-POS picks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from prelexy import debug
from prelexy.definitions import ensure_sense, wordnet_lemma_names, wordnet_sense

# The distractor band, applied to definition-text similarity: above the
# ceiling the two definitions nearly coincide (near-synonym — ambiguous,
# unfair); below the floor the candidate gloss is from another domain
# entirely (too obviously wrong). PROVISIONAL values — averaged-vector text
# similarities run higher than word similarities; calibrate against real
# scores from `prelexy --debug question <word>`.
SIMILARITY_FLOOR = 0.45
SIMILARITY_CEILING = 0.85

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
    """Up to N_OPTIONS-1 distractor glosses, band-scored candidates preferred.

    Each candidate's gloss is scored against the correct gloss. Candidates
    without a score (no provider, or no usable content vector) accumulate
    as a fallback used only to top up.
    """
    target_lemma = (item["lemma"] or item["form"]).lower()
    needed = N_OPTIONS - 1
    banded: list[str] = []
    unscored: list[str] = []
    scanned = 0
    for scanned, candidate in enumerate(
        _wordnet_candidates(item["pos"], item["language"], rng), start=1
    ):
        if len(banded) == needed or scanned > _SCAN_LIMIT:
            break
        if candidate == target_lemma:
            continue
        sense = wordnet_sense(candidate, item["pos"], item["language"])
        if sense is None or sense.gloss == correct_gloss:
            continue
        if target_lemma in sense.gloss.lower().split():
            continue  # a gloss that names the target gives the game away
        score = (
            similarity.text_similarity(correct_gloss, sense.gloss)
            if similarity
            else None
        )
        if score is not None and not (SIMILARITY_FLOOR < score < SIMILARITY_CEILING):
            continue
        if sense.gloss not in banded and sense.gloss not in unscored:
            (banded if score is not None else unscored).append(sense.gloss)
            debug.log(
                "mcq",
                f"{item['form']!r} ← {candidate!r} "
                + (f"score {score:.3f} (in band)" if score is not None else "unscored (fallback pool)"),
            )
        if similarity is None and len(unscored) == needed:
            break
    debug.log(
        "mcq",
        f"{item['form']!r}: scanned {scanned}, {len(banded)} in band, "
        f"{len(unscored)} fallback → using {min(needed, len(banded) + len(unscored))}",
    )
    return (banded + unscored)[:needed]


def _wordnet_candidates(pos, language, rng) -> list[str]:
    """A fresh random sample of same-POS WordNet lemmas for one question."""
    names = wordnet_lemma_names(pos, language)
    return rng.sample(names, min(len(names), _SCAN_LIMIT))
