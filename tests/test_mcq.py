import random

import pytest

import prelexy.definitions as definitions
from prelexy.mcq import SIMILARITY_CEILING, build_question
from prelexy.store import Store


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(
        definitions, "_fetch_api_json", lambda url: pytest.fail("unexpected API call")
    )


class FakeSimilarity:
    def __init__(self, table):
        self.table = table

    def similarity(self, a, b):
        return self.table.get(frozenset((a, b)))


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "test.db") as s:
        yield s


def add_word(store, form, pos="ADJ", zipf=2.0, gloss=None, lemma=None):
    item_id = store.get_or_create_item(
        "en", form, lemma=lemma or form, pos=pos, metadata={"zipf": zipf}
    )
    if gloss:
        store.add_sense(item_id, gloss, "en", "wordnet")
    return item_id


def test_question_has_shuffled_options_and_correct_answer(store):
    target = add_word(store, "sagacious", zipf=2.5, gloss="having keen judgement")
    source = store.add_source("t", "en", "book", None)
    store.add_occurrences(target, source, [("A sagacious man.", 2)])
    for i in range(3):
        add_word(store, f"word{i}", zipf=2.5 + i / 10, gloss=f"gloss {i}")

    question = build_question(
        store, store.find_item("en", "sagacious"), rng=random.Random(42)
    )
    assert question is not None
    assert len(question.options) == 4
    assert question.options[question.answer] == "having keen judgement"
    assert question.context == "A sagacious man."
    assert {f"gloss {i}" for i in range(3)} < set(question.options)


def test_near_synonyms_are_excluded(store):
    add_word(store, "sagacious", zipf=2.5, gloss="having keen judgement")
    add_word(store, "wise", zipf=2.5, gloss="showing wisdom")  # near-synonym
    add_word(store, "vermilion", zipf=2.5, gloss="a vivid red")
    add_word(store, "crestfallen", zipf=2.5, gloss="sad and disappointed")
    add_word(store, "gaunt", zipf=2.5, gloss="very thin")

    similarity = FakeSimilarity({frozenset(("sagacious", "wise")): SIMILARITY_CEILING + 0.1})
    question = build_question(
        store,
        store.find_item("en", "sagacious"),
        similarity=similarity,
        rng=random.Random(0),
    )
    assert "showing wisdom" not in question.options
    assert len(question.options) == 4


def test_distractors_prefer_similar_rarity_and_same_pos(store):
    add_word(store, "sagacious", zipf=2.0, gloss="having keen judgement")
    add_word(store, "rare1", zipf=2.1, gloss="rare gloss 1")
    add_word(store, "rare2", zipf=2.2, gloss="rare gloss 2")
    add_word(store, "rare3", zipf=2.3, gloss="rare gloss 3")
    add_word(store, "common", zipf=6.0, gloss="a very common word")
    add_word(store, "verbword", pos="VERB", zipf=2.0, gloss="a verb gloss")

    question = build_question(
        store, store.find_item("en", "sagacious"), rng=random.Random(0)
    )
    assert "a very common word" not in question.options  # rarity-mismatched, crowded out
    assert "a verb gloss" not in question.options  # different POS
    assert set(question.options) == {
        "having keen judgement",
        "rare gloss 1",
        "rare gloss 2",
        "rare gloss 3",
    }


def test_same_lemma_and_duplicate_glosses_are_excluded(store):
    add_word(store, "run", lemma="run", zipf=5.0, gloss="move fast on foot")
    add_word(store, "runs", lemma="run", zipf=5.0, gloss="third-person of run")
    add_word(store, "walk", zipf=5.0, gloss="move fast on foot")  # duplicate gloss
    add_word(store, "jump", zipf=5.0, gloss="propel oneself upward")

    question = build_question(store, store.find_item("en", "run"), rng=random.Random(0))
    assert question.options.count("move fast on foot") == 1
    assert "third-person of run" not in question.options
    assert "propel oneself upward" in question.options


def test_small_store_yields_fewer_options(store):
    add_word(store, "sagacious", zipf=2.5, gloss="having keen judgement")
    add_word(store, "gaunt", zipf=2.5, gloss="very thin")

    question = build_question(
        store, store.find_item("en", "sagacious"), rng=random.Random(0)
    )
    assert sorted(question.options) == sorted(["having keen judgement", "very thin"])


def test_no_distractors_at_all_returns_none(store):
    add_word(store, "sagacious", zipf=2.5, gloss="having keen judgement")
    assert build_question(store, store.find_item("en", "sagacious")) is None


def test_unknown_definition_returns_none(store, monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: None)
    add_word(store, "xqzt")  # no cached gloss, not in WordNet, API finds nothing
    add_word(store, "gaunt", gloss="very thin")
    assert build_question(store, store.find_item("en", "xqzt")) is None


def test_missing_vectors_do_not_block_distractors(store):
    add_word(store, "sagacious", zipf=2.5, gloss="having keen judgement")
    add_word(store, "gaunt", zipf=2.5, gloss="very thin")

    question = build_question(
        store,
        store.find_item("en", "sagacious"),
        similarity=FakeSimilarity({}),  # similarity unknown for every pair
        rng=random.Random(0),
    )
    assert "very thin" in question.options
