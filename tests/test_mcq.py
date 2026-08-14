import random

import pytest

import prelexy.definitions as definitions
import prelexy.mcq as mcq
from prelexy.mcq import SIMILARITY_CEILING, SIMILARITY_FLOOR, build_question
from prelexy.store import Store

IN_BAND = (SIMILARITY_FLOOR + SIMILARITY_CEILING) / 2


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(
        definitions, "_fetch_api_json", lambda url: pytest.fail("unexpected API call")
    )


class FakeSimilarity:
    """Similarity by lookup table; None (= no usable vector) otherwise."""

    def __init__(self, table):
        self.table = table

    def similarity(self, a, b):
        return self.table.get(frozenset((a, b)))

    def text_similarity(self, a, b):
        return self.table.get(frozenset((a, b)))


def gloss_of(word):
    return definitions.wordnet_sense(word, "ADJ").gloss


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "test.db") as s:
        yield s


def add_target(store, form="sagacious", pos="ADJ", gloss="having keen judgement"):
    item_id = store.get_or_create_item("en", form, lemma=form, pos=pos, metadata={"zipf": 2.5})
    store.add_sense(item_id, gloss, "en", "wordnet")
    return store.find_item("en", form)


def use_candidates(monkeypatch, words):
    monkeypatch.setattr(mcq, "_wordnet_candidates", lambda pos, language, rng: list(words))


def test_question_built_from_real_wordnet_pool(store):
    """Integration: no patched pool, no provider — the WordNet fallback path."""
    item = add_target(store)
    question = build_question(store, item, rng=random.Random(42))
    assert question is not None
    assert len(question.options) == 4
    assert question.options[question.answer] == "having keen judgement"
    assert len(set(question.options)) == 4


def test_options_vary_between_sessions(store):
    item = add_target(store)
    first = build_question(store, item, rng=random.Random(1))
    second = build_question(store, item, rng=random.Random(2))
    assert set(first.options) != set(second.options)


def test_band_governs_selection_by_gloss_similarity(store, monkeypatch):
    correct = "having keen judgement"
    item = add_target(store, gloss=correct)
    use_candidates(monkeypatch, ["wise", "gaunt", "sallow", "listless", "crimson"])
    similarity = FakeSimilarity(
        {
            frozenset((correct, gloss_of("wise"))): SIMILARITY_CEILING + 0.05,  # near-synonym
            frozenset((correct, gloss_of("gaunt"))): IN_BAND,
            frozenset((correct, gloss_of("sallow"))): IN_BAND,
            frozenset((correct, gloss_of("listless"))): IN_BAND,
            frozenset((correct, gloss_of("crimson"))): SIMILARITY_FLOOR - 0.05,  # other domain
        }
    )
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    assert gloss_of("wise") not in question.options
    assert gloss_of("crimson") not in question.options
    assert len(question.options) == 4


def test_unscored_candidates_only_top_up(store, monkeypatch):
    correct = "having keen judgement"
    item = add_target(store, gloss=correct)
    # 'gaunt' has no score (no usable vector); the three in-band glosses win.
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless", "sombre"])
    similarity = FakeSimilarity(
        {
            frozenset((correct, gloss_of("sallow"))): IN_BAND,
            frozenset((correct, gloss_of("listless"))): IN_BAND,
            frozenset((correct, gloss_of("sombre"))): IN_BAND,
        }
    )
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    assert gloss_of("gaunt") not in question.options

    # with one in-band word missing, the unscored candidate fills the gap
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless"])
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    assert gloss_of("gaunt") in question.options


def test_pool_biases_toward_hardest_candidates(store, monkeypatch):
    import prelexy.mcq as mcq_module

    correct = "having keen judgement"
    item = add_target(store, gloss=correct)
    # 12 in-band candidates with ascending scores: the 2 weakest fall
    # outside the top-10 pool and must never be sampled.
    words = [
        "gaunt",
        "sallow",
        "listless",
        "sombre",
        "wan",
        "ashen",
        "haggard",
        "drawn",
        "pallid",
        "peaked",
        "sickly",
        "drab",
    ]
    table, glosses = {}, {}
    for rank, word in enumerate(words):
        gloss = f"gloss number {rank} for {word}"
        glosses[word] = gloss
        table[frozenset((correct, gloss))] = SIMILARITY_FLOOR + 0.01 * (rank + 1)
    monkeypatch.setattr(
        mcq_module,
        "wordnet_sense",
        lambda cand, pos, lang, **kwargs: (
            definitions.Sense(glosses[cand], "en", "wordnet") if cand in glosses else None
        ),
    )
    use_candidates(monkeypatch, words)

    seen = set()
    for seed in range(20):
        question = build_question(
            store, item, similarity=FakeSimilarity(table), rng=random.Random(seed)
        )
        seen.update(question.options)
    assert glosses["gaunt"] not in seen  # weakest two: outside the pool
    assert glosses["sallow"] not in seen
    assert glosses["drab"] in seen  # the hardest is reachable


def test_below_floor_candidates_fill_when_band_is_empty(store, monkeypatch):
    correct = "having keen judgement"
    item = add_target(store, gloss=correct)
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless", "crimson"])
    similarity = FakeSimilarity(
        {
            frozenset((correct, gloss_of("gaunt"))): SIMILARITY_FLOOR - 0.20,
            frozenset((correct, gloss_of("sallow"))): SIMILARITY_FLOOR - 0.05,
            frozenset((correct, gloss_of("listless"))): SIMILARITY_FLOOR - 0.10,
            frozenset((correct, gloss_of("crimson"))): SIMILARITY_FLOOR - 0.15,
        }
    )
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    assert len(question.options) == 4  # most-similar-available, not none


def test_wordnet_synonyms_never_become_distractors(store, monkeypatch):
    item = add_target(store, form="joy", pos="NOUN", gloss="the emotion of great happiness")
    use_candidates(monkeypatch, ["delight", "brickfield", "scaup", "probity"])
    question = build_question(store, item, rng=random.Random(0))
    delight_gloss = definitions.wordnet_sense("delight", "NOUN").gloss
    assert delight_gloss not in question.options  # 'delight' is a synonym of 'joy'
    assert len(question.options) == 4


def test_length_mismatched_glosses_are_excluded(store, monkeypatch):
    from prelexy.mcq import _length_compatible

    short = "a vivid red"
    encyclopedic = (
        "an Argentine revolutionary leader who was a chief lieutenant in the"
        " Cuban revolution and was active in several other countries besides"
    )
    assert not _length_compatible(short, encyclopedic)
    assert _length_compatible(short, "a deep shade of blue")  # slack covers it
    assert _length_compatible(
        "the quality of being good looking and attractive",
        "small ornamental ladies' bag for small articles",
    )

    # end to end: the monster gloss never appears even when in band
    item = add_target(store, gloss=short)
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless", "crimson"])
    table = {
        frozenset((short, gloss_of(w))): IN_BAND for w in ("gaunt", "sallow", "listless", "crimson")
    }
    monkeypatch.setattr(
        "prelexy.mcq._length_compatible",
        lambda correct, cand: cand != gloss_of("crimson"),
    )
    question = build_question(store, item, similarity=FakeSimilarity(table), rng=random.Random(0))
    assert gloss_of("crimson") not in question.options
    assert len(question.options) == 4


def test_candidate_pool_follows_the_gloss_pos(store, monkeypatch):
    import prelexy.mcq as mcq_module

    asked = []
    real_candidates = mcq_module._wordnet_candidates

    def recording_candidates(pos, language, rng):
        asked.append(pos)
        return real_candidates(pos, language, rng)

    monkeypatch.setattr(mcq_module, "_wordnet_candidates", recording_candidates)

    # fresh lookup: 'gartered' stored as ADJ, glossed from the verb 'garter'
    store.get_or_create_item("en", "gartered", lemma="gartered", pos="ADJ", metadata={"zipf": 1.0})
    item = store.find_item("en", "gartered")
    question = build_question(store, item, rng=random.Random(0))
    assert question is not None
    assert asked == ["VERB"]

    # cached lookup (senses table stores no POS): re-derived, same answer
    asked.clear()
    question = build_question(store, item, rng=random.Random(1))
    assert question is not None
    assert asked == ["VERB"]


def add_code_item(store, form, gloss, language="python", kind="method", order=0):
    item_id = store.get_or_create_item(
        language,
        form,
        lemma=form,
        pos=kind,
        metadata={
            "kind": kind,
            "module": form.split(".")[0],
            "signature": f"{form}(...)",
            "order": order,
        },
    )
    store.add_sense(item_id, gloss, "en", "docs")
    return item_id


def test_code_question_uses_corpus_pool(store, monkeypatch):
    add_code_item(store, "list.pop", "Remove and return the item at the given position.")
    add_code_item(store, "list.append", "Add an item to the end of the list.")
    add_code_item(store, "dict.get", "Return the value for a key if present.")
    add_code_item(store, "set.add", "Add an element to the set.")
    add_code_item(store, "list.index", "Return the index of the first matching item.")
    item = store.find_item("python", "list.pop")

    question = build_question(store, item, rng=random.Random(3))
    assert question is not None
    assert len(question.options) == 4
    assert question.options[question.answer].startswith("Remove and return")
    assert len(set(question.options)) == 4


def test_code_pool_spans_languages_unless_restricted(store, monkeypatch):
    from prelexy.languages import LANGUAGES, Language

    monkeypatch.setitem(LANGUAGES, "java", Language(code="java", kind="code"))
    add_code_item(store, "list.pop", "Remove and return the item at the given position.")
    java_gloss = "Return the element at the head of this java deque."
    add_code_item(store, "Deque.poll", java_gloss, language="java")
    add_code_item(store, "list.append", "Add an item to the end of the list.")
    add_code_item(store, "dict.get", "Return the value for a key if present.")
    item = store.find_item("python", "list.pop")

    question = build_question(store, item, rng=random.Random(0), code_own_pool=False)
    assert java_gloss in question.options  # cross-corpus by default

    seen = set()
    for seed in range(10):
        question = build_question(store, item, rng=random.Random(seed), code_own_pool=True)
        seen.update(question.options)
    assert java_gloss not in seen  # restricted to python


def test_dutch_question_end_to_end_offline(store):
    """A Dutch item gets an English-glossed MCQ with Dutch-pool distractors."""
    store.get_or_create_item("nl", "fiets", lemma="fiets", pos="NOUN", metadata={"zipf": 4.0})
    item = store.find_item("nl", "fiets")
    question = build_question(store, item, rng=random.Random(7))
    assert question is not None
    assert len(question.options) == 4
    assert "wheel" in question.options[question.answer]  # English gloss
    assert len(set(question.options)) == 4


def test_named_entities_never_become_distractors(store, monkeypatch):
    item = add_target(
        store, form="carthorse", pos="NOUN", gloss="draft horse kept for pulling carts"
    )
    use_candidates(monkeypatch, ["guevara", "jacksonville", "scaup", "denizen", "probity"])
    question = build_question(store, item, rng=random.Random(0))
    joined = " ".join(question.options)
    assert "Argentine" not in joined
    assert "Florida" not in joined
    assert len(question.options) == 4  # the ordinary words still fill the set


def test_gloss_naming_the_target_is_excluded(store, monkeypatch):
    # "sagacious" defines itself as "acutely insightful and wise" — for the
    # target "wise" that option would give the game away.
    item = add_target(store, form="wise", gloss="having or prompted by wisdom")
    use_candidates(monkeypatch, ["sagacious", "gaunt", "sallow", "listless"])
    question = build_question(store, item, rng=random.Random(0))
    assert gloss_of("sagacious") not in question.options
    assert len(question.options) == 4


def test_target_lemma_never_a_distractor(store, monkeypatch):
    item = add_target(store)
    use_candidates(monkeypatch, ["sagacious", "gaunt", "sallow", "listless"])
    question = build_question(store, item, rng=random.Random(0))
    assert question.options.count("having keen judgement") == 1
    assert len(question.options) == 4


def test_exhausted_pool_yields_fewer_options(store, monkeypatch):
    item = add_target(store)
    use_candidates(monkeypatch, ["gaunt"])
    question = build_question(store, item, rng=random.Random(0))
    assert len(question.options) == 2

    use_candidates(monkeypatch, [])
    assert build_question(store, item, rng=random.Random(0)) is None


def test_unknown_definition_returns_none(store, monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: None)
    store.get_or_create_item("en", "xqzt", lemma="xqzt", pos="ADJ")
    item = store.find_item("en", "xqzt")
    assert build_question(store, item) is None


def test_all_vectors_missing_falls_back_entirely(store, monkeypatch):
    item = add_target(store)
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless"])
    question = build_question(store, item, similarity=FakeSimilarity({}), rng=random.Random(0))
    assert len(question.options) == 4
