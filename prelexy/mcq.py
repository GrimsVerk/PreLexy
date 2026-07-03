"""Multiple-choice question generation (docs/DESIGN.md, "MCQ exercise").

The question is "pick the correct definition". Distractors are real
definitions of other stored items that share the target's part of speech and
are similarly rare; anything above the similarity ceiling is excluded as a
near-synonym (an ambiguous option is unfair). Distractor glosses come from
offline sources only. When the store is still small, a question may carry
fewer than the usual four options — a leaner question beats none.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from prelexy.definitions import ensure_sense

# Above this cosine similarity a pool word counts as a near-synonym of the
# target and is excluded. Plausibility comes from matching POS and rarity;
# tune empirically in phase 5.
SIMILARITY_CEILING = 0.7

N_OPTIONS = 4


@dataclass
class Question:
    item_id: int
    form: str
    context: str | None  # example sentence from the source text
    options: list[str]  # glosses, shuffled
    answer: int  # index into options of the correct gloss


def build_question(store, item, similarity=None, rng=None) -> Question | None:
    """Build an MCQ for an item row.

    Returns None when no definition can be found for the item, or when the
    store has no usable distractor at all.
    """
    rng = rng or random.Random()
    sense = ensure_sense(store, item)
    if sense is None:
        return None
    distractors = _distractors(store, item, sense.gloss, similarity)
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


def _distractors(store, item, correct_gloss, similarity) -> list[str]:
    """Up to N_OPTIONS-1 distractor glosses, closest in rarity first."""
    target_zipf = _zipf(item)
    target_lemma = item["lemma"] or item["form"]
    pool = [
        row
        for row in store.list_items(item["language"])
        if row["id"] != item["id"]
        and row["pos"] == item["pos"]
        and (row["lemma"] or row["form"]) != target_lemma
    ]
    pool.sort(key=lambda row: abs(_zipf(row) - target_zipf))

    glosses: list[str] = []
    for row in pool:
        if len(glosses) == N_OPTIONS - 1:
            break
        if similarity is not None:
            score = similarity.similarity(item["form"], row["form"])
            if score is not None and score > SIMILARITY_CEILING:
                continue  # near-synonym: would make the question ambiguous
        sense = ensure_sense(store, row, allow_api=False)
        if sense is None or sense.gloss == correct_gloss or sense.gloss in glosses:
            continue
        glosses.append(sense.gloss)
    return glosses


def _zipf(row) -> float:
    return json.loads(row["metadata"]).get("zipf", 0.0)
