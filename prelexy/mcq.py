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

# Candidates examined per question.
_SCAN_LIMIT = 500

# Distractors are sampled from the _POOL_SIZE highest-scoring candidates of
# the whole scan (owner request): options stay varied between sessions while
# biasing toward the hardest available.
_POOL_SIZE = 10


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
    """Up to N_OPTIONS-1 distractor glosses, sampled from the hardest available.

    Every scanned candidate below the near-synonym ceiling is scored against
    the correct gloss, and distractors are drawn at random from the
    _POOL_SIZE highest-scoring ones. Candidates inside the band are
    preferred; when the floor leaves fewer than needed, the most similar
    available fill the pool anyway — maximum difficulty, kept random.
    Unscored candidates (no provider, or gloss without usable vectors) are
    only a top-up of last resort.
    """
    target_lemma = (item["lemma"] or item["form"]).lower()
    needed = N_OPTIONS - 1
    scored: list[tuple[float, str, str]] = []  # (score, word, gloss)
    unscored: list[str] = []
    seen_glosses = {correct_gloss}
    scanned = 0
    for candidate in _wordnet_candidates(item["pos"], item["language"], rng):
        scanned += 1
        if candidate == target_lemma:
            continue
        sense = wordnet_sense(candidate, item["pos"], item["language"])
        if sense is None or sense.gloss in seen_glosses:
            continue
        if target_lemma in sense.gloss.lower().split():
            continue  # a gloss that names the target gives the game away
        seen_glosses.add(sense.gloss)
        score = (
            similarity.text_similarity(correct_gloss, sense.gloss)
            if similarity
            else None
        )
        if score is None:
            unscored.append(sense.gloss)
            if similarity is None and len(unscored) == needed:
                break
            continue
        if score >= SIMILARITY_CEILING:
            debug.log(
                "mcq", f"{item['form']!r} ✗ {candidate!r} score {score:.3f} (near-synonym)"
            )
            continue
        scored.append((score, candidate, sense.gloss))

    if not scored:
        picked = unscored[:needed]
        debug.log(
            "mcq",
            f"{item['form']!r}: scanned {scanned}, nothing scored → {len(picked)} fallback",
        )
        return picked

    scored.sort(reverse=True)  # hardest first
    in_band = [entry for entry in scored if entry[0] > SIMILARITY_FLOOR]
    pool = (in_band if len(in_band) >= needed else scored)[:_POOL_SIZE]
    sampled = rng.sample(pool, min(needed, len(pool)))
    for score, candidate, _ in sampled:
        marker = "" if score > SIMILARITY_FLOOR else " (below floor)"
        debug.log("mcq", f"{item['form']!r} ← {candidate!r} score {score:.3f}{marker}")
    debug.log(
        "mcq",
        f"{item['form']!r}: scanned {scanned}, scored {len(scored)}, "
        f"in band {len(in_band)}, pool {len(pool)} → sampled {len(sampled)}",
    )
    glosses = [gloss for _, _, gloss in sampled]
    if len(glosses) < needed:
        glosses += [g for g in unscored if g not in glosses][: needed - len(glosses)]
    return glosses


def _wordnet_candidates(pos, language, rng) -> list[str]:
    """A fresh random sample of same-POS WordNet lemmas for one question."""
    names = wordnet_lemma_names(pos, language)
    return rng.sample(names, min(len(names), _SCAN_LIMIT))
