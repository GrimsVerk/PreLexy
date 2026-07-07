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
from prelexy.config import DEFAULTS
from prelexy.definitions import (
    ensure_sense,
    synonym_conflict,
    wordnet_lemma_names,
    wordnet_sense,
)
from prelexy.languages import code_language_codes, get_language

# The distractor band, applied to definition-text similarity: above the
# ceiling the two definitions nearly coincide (near-synonym — ambiguous,
# unfair); the floor is a soft preference for plausible-but-wrong options.
# PROVISIONAL values — calibrate against real scores from
# `prelexy --debug question <word>`. Configurable via config.toml; these
# module constants are the single built-in default (from config.DEFAULTS).
SIMILARITY_FLOOR = DEFAULTS["similarity_floor"]
SIMILARITY_CEILING = DEFAULTS["similarity_ceiling"]

N_OPTIONS = 4

# Candidates examined per question.
_SCAN_LIMIT = 500

# Length compatibility between the correct gloss and a candidate gloss: a
# crisp answer among sprawling encyclopedic options (or vice versa) is a
# tell. Loose on purpose — candidates pass when within the ratio OR within
# the absolute slack, so short glosses aren't starved of company.
_LENGTH_RATIO = 2.5
_LENGTH_SLACK = 40  # characters

# Distractors are sampled from the pool_size highest-scoring candidates of
# the whole scan (owner request): options stay varied between sessions while
# biasing toward the hardest available. Configurable via config.toml.
_POOL_SIZE = DEFAULTS["pool_size"]


@dataclass
class Question:
    item_id: int
    form: str
    context: str | None  # example sentence from the source text
    options: list[str]  # glosses, shuffled
    answer: int  # index into options of the correct gloss


def build_question(
    store,
    item,
    similarity=None,
    rng=None,
    band=None,
    pool_size=None,
    code_own_pool=None,
) -> Question | None:
    """Build an MCQ for an item row.

    `band`, `pool_size`, and `code_own_pool` override the module defaults,
    e.g. from the config file. Returns None when no definition can be found
    for the item, or when no usable distractor exists at all.
    """
    rng = rng or random.Random()
    sense = ensure_sense(store, item)
    if sense is None:
        return None
    if get_language(item["language"]).kind == "code":
        distractors = _code_distractors(
            store, item, sense.gloss, similarity, rng, band, pool_size, code_own_pool
        )
    else:
        distractors = _distractors(item, sense, similarity, rng, band, pool_size)
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


def _distractors(
    item, correct_sense, similarity, rng, band=None, pool_size=None
) -> list[str]:
    """Up to N_OPTIONS-1 distractor glosses, sampled from the hardest available.

    Every scanned candidate below the near-synonym ceiling is scored against
    the correct gloss, and distractors are drawn at random from the
    _POOL_SIZE highest-scoring ones. Candidates inside the band are
    preferred; when the floor leaves fewer than needed, the most similar
    available fill the pool anyway — maximum difficulty, kept random.
    Unscored candidates (no provider, or gloss without usable vectors) are
    only a top-up of last resort.

    The candidate pool follows the POS the *correct gloss* came from, not
    the item's stored POS: "gartered" is stored as an adjective but only
    has a verb gloss, and a verb-phrased answer among adjective-phrased
    options fingerprints itself (2026-07-06 playtest; BACKLOG Stage 1.2).
    """
    floor, ceiling = band or (SIMILARITY_FLOOR, SIMILARITY_CEILING)
    pool_size = pool_size or _POOL_SIZE
    correct_gloss = correct_sense.gloss
    pool_pos = _pool_pos(item, correct_sense)
    if pool_pos != item["pos"]:
        debug.log(
            "mcq",
            f"{item['form']!r}: gloss is {pool_pos}-sourced (item is {item['pos']}); "
            f"drawing candidates from {pool_pos}",
        )
    target_lemma = (item["lemma"] or item["form"]).lower()
    needed = N_OPTIONS - 1
    scored: list[tuple[float, str, str]] = []  # (score, word, gloss)
    unscored: list[tuple[str, str]] = []  # (word, gloss)
    seen_glosses = {correct_gloss}
    scanned = 0

    def fair(word: str) -> bool:
        if not synonym_conflict(item["form"], word, pool_pos, item["language"]):
            return True
        debug.log("mcq", f"{item['form']!r} ✗ {word!r} (WordNet synonym/relative)")
        return False
    for candidate in _wordnet_candidates(pool_pos, item["language"], rng):
        scanned += 1
        if candidate == target_lemma:
            continue
        sense = wordnet_sense(
            candidate, pool_pos, item["language"], include_instances=False
        )
        if sense is None or sense.gloss in seen_glosses:
            continue
        if target_lemma in sense.gloss.lower().split():
            continue  # a gloss that names the target gives the game away
        if not _length_compatible(correct_gloss, sense.gloss):
            continue
        seen_glosses.add(sense.gloss)
        score = (
            similarity.text_similarity(correct_gloss, sense.gloss)
            if similarity
            else None
        )
        if score is None:
            # without a provider the scan stops at `needed`, so the
            # fairness guard must apply before counting, not after
            if similarity is not None or fair(candidate):
                unscored.append((candidate, sense.gloss))
            if similarity is None and len(unscored) == needed:
                break
            continue
        if score >= ceiling:
            debug.log(
                "mcq", f"{item['form']!r} ✗ {candidate!r} score {score:.3f} (near-synonym)"
            )
            continue
        scored.append((score, candidate, sense.gloss))

    if not scored:
        picked = [gloss for word, gloss in unscored if fair(word)][:needed]
        debug.log(
            "mcq",
            f"{item['form']!r}: scanned {scanned}, nothing scored → {len(picked)} fallback",
        )
        return picked

    scored.sort(reverse=True)  # hardest first
    in_band = [entry for entry in scored if entry[0] > floor]
    ranked = in_band if len(in_band) >= needed else scored
    pool = []
    for entry in ranked:
        if len(pool) == pool_size:
            break
        if fair(entry[1]):
            pool.append(entry)
    sampled = rng.sample(pool, min(needed, len(pool)))
    for score, candidate, _ in sampled:
        marker = "" if score > floor else " (below floor)"
        debug.log("mcq", f"{item['form']!r} ← {candidate!r} score {score:.3f}{marker}")
    debug.log(
        "mcq",
        f"{item['form']!r}: scanned {scanned}, scored {len(scored)}, "
        f"in band {len(in_band)}, pool {len(pool)} → sampled {len(sampled)}",
    )
    glosses = [gloss for _, _, gloss in sampled]
    if len(glosses) < needed:
        glosses += [
            gloss
            for word, gloss in unscored
            if gloss not in glosses and fair(word)
        ][: needed - len(glosses)]
    return glosses


def _length_compatible(correct_gloss: str, candidate_gloss: str) -> bool:
    shorter, longer = sorted((len(correct_gloss), len(candidate_gloss)))
    return longer - shorter <= _LENGTH_SLACK or longer <= shorter * _LENGTH_RATIO


def _code_distractors(
    store, item, correct_gloss, similarity, rng, band=None, pool_size=None, own_pool=None
) -> list[str]:
    """Distractors for code items: same-kind glosses from ingested corpora.

    Spans all code languages by default — practicing Python and Java
    together maximizes difficulty (DECISIONS 024); `own_pool=True`
    restricts to the target's own language. Same hardest-pool sampling as
    natural mode; no WordNet guards (the corpora are already curated).
    """
    floor, ceiling = band or (SIMILARITY_FLOOR, SIMILARITY_CEILING)
    pool_size = pool_size or _POOL_SIZE
    if own_pool is None:
        own_pool = DEFAULTS["code_pool_own_language"]
    languages = [item["language"]] if own_pool else code_language_codes()
    needed = N_OPTIONS - 1
    rows = store.code_pool(item["pos"], languages, item["id"])
    rng.shuffle(rows)
    scored: list[tuple[float, str, str]] = []
    unscored: list[str] = []
    seen_glosses = {correct_gloss}
    scanned = 0
    for form, gloss in rows:
        scanned += 1
        if scanned > _SCAN_LIMIT:
            break
        if gloss in seen_glosses or not _length_compatible(correct_gloss, gloss):
            continue
        seen_glosses.add(gloss)
        score = similarity.text_similarity(correct_gloss, gloss) if similarity else None
        if score is None:
            unscored.append(gloss)
            if similarity is None and len(unscored) == needed:
                break
            continue
        if score >= ceiling:
            debug.log("mcq", f"{item['form']!r} ✗ {form!r} score {score:.3f} (near-duplicate)")
            continue
        scored.append((score, form, gloss))

    if not scored:
        picked = unscored[:needed]
        debug.log(
            "mcq",
            f"{item['form']!r}: code pool scanned {scanned} → {len(picked)} fallback",
        )
        return picked
    scored.sort(reverse=True)
    in_band = [entry for entry in scored if entry[0] > floor]
    pool = (in_band if len(in_band) >= needed else scored)[:pool_size]
    sampled = rng.sample(pool, min(needed, len(pool)))
    for score, form, _ in sampled:
        marker = "" if score > floor else " (below floor)"
        debug.log("mcq", f"{item['form']!r} ← {form!r} score {score:.3f}{marker}")
    debug.log(
        "mcq",
        f"{item['form']!r}: code pool {len(rows)}, scored {len(scored)}, "
        f"in band {len(in_band)}, pool {len(pool)} → sampled {len(sampled)}",
    )
    glosses = [gloss for _, _, gloss in sampled]
    if len(glosses) < needed:
        glosses += [g for g in unscored if g not in glosses][: needed - len(glosses)]
    return glosses


def _pool_pos(item, correct_sense) -> str | None:
    """The POS the correct gloss was sourced from.

    Cache reads carry no POS (the senses table stores none), so re-derive
    by asking WordNet afresh and checking it yields the same gloss.
    """
    if correct_sense.pos:
        return correct_sense.pos
    fresh = wordnet_sense(item["form"], item["pos"], item["language"])
    if fresh is not None and fresh.gloss == correct_sense.gloss and fresh.pos:
        return fresh.pos
    return item["pos"]


def _wordnet_candidates(pos, language, rng) -> list[str]:
    """A fresh random sample of same-POS WordNet lemmas for one question."""
    names = wordnet_lemma_names(pos, language)
    return rng.sample(names, min(len(names), _SCAN_LIMIT))
