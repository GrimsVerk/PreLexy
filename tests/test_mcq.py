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
    item_id = store.get_or_create_item(
        "en", form, lemma=form, pos=pos, metadata={"zipf": 2.5}
    )
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
    item_id = store.get_or_create_item("en", "xqzt", lemma="xqzt", pos="ADJ")
    item = store.find_item("en", "xqzt")
    assert build_question(store, item) is None


def test_all_vectors_missing_falls_back_entirely(store, monkeypatch):
    item = add_target(store)
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless"])
    question = build_question(
        store, item, similarity=FakeSimilarity({}), rng=random.Random(0)
    )
    assert len(question.options) == 4
