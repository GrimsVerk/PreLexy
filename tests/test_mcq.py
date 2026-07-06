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
    """Similarity by lookup table; None (= no vector) for unknown pairs."""

    def __init__(self, table):
        self.table = table

    def similarity(self, a, b):
        return self.table.get(frozenset((a, b)))


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


def test_band_governs_selection(store, monkeypatch):
    item = add_target(store)
    use_candidates(monkeypatch, ["wise", "gaunt", "sallow", "listless", "crimson"])
    similarity = FakeSimilarity(
        {
            frozenset(("sagacious", "wise")): SIMILARITY_CEILING + 0.1,  # near-synonym
            frozenset(("sagacious", "gaunt")): IN_BAND,
            frozenset(("sagacious", "sallow")): IN_BAND,
            frozenset(("sagacious", "listless")): IN_BAND,
            frozenset(("sagacious", "crimson")): SIMILARITY_FLOOR - 0.1,  # other domain
        }
    )
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    wise_gloss = definitions.wordnet_sense("wise", "ADJ").gloss
    crimson_gloss = definitions.wordnet_sense("crimson", "ADJ").gloss
    assert wise_gloss not in question.options
    assert crimson_gloss not in question.options
    assert len(question.options) == 4


def test_unscored_candidates_only_top_up(store, monkeypatch):
    item = add_target(store)
    # 'gaunt' has no vector (None); the three scored in-band words must win.
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless", "sombre"])
    similarity = FakeSimilarity(
        {
            frozenset(("sagacious", "sallow")): IN_BAND,
            frozenset(("sagacious", "listless")): IN_BAND,
            frozenset(("sagacious", "sombre")): IN_BAND,
        }
    )
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    gaunt_gloss = definitions.wordnet_sense("gaunt", "ADJ").gloss
    assert gaunt_gloss not in question.options

    # with one in-band word missing, the unscored candidate fills the gap
    use_candidates(monkeypatch, ["gaunt", "sallow", "listless"])
    question = build_question(store, item, similarity=similarity, rng=random.Random(0))
    assert gaunt_gloss in question.options


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
