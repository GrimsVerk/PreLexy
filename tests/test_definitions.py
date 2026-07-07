import pytest

import prelexy.definitions as definitions
from prelexy.definitions import Sense, api_sense, ensure_sense, wordnet_sense
from prelexy.store import Store


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may hit the real dictionary API."""
    monkeypatch.setattr(
        definitions, "_fetch_api_json", lambda url: pytest.fail("unexpected API call")
    )


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "test.db") as s:
        yield s


API_PAYLOAD = [
    {
        "word": "sagacious",
        "meanings": [
            {
                "partOfSpeech": "noun",
                "definitions": [{"definition": "a wise-noun gloss"}],
            },
            {
                "partOfSpeech": "adjective",
                "definitions": [{"definition": "having keen judgement"}],
            },
        ],
    }
]


@pytest.mark.parametrize(
    ("dirty", "clean"),
    [
        (
            "lean and wrinkled by shrinkage as from age or illness; ; ; ; -W.F.Starkie",
            "lean and wrinkled by shrinkage as from age or illness",
        ),
        ("deserving or inciting pity; ; ; - Galsworthy", "deserving or inciting pity"),
        ("suitable to your needs; ; - T.L.Peacock", "suitable to your needs"),
        ("a choice or delicious dish", "a choice or delicious dish"),
        (
            "of grass or vegetation; not cut down",  # real multi-part defs survive
            "of grass or vegetation; not cut down",
        ),
    ],
)
def test_clean_gloss(dirty, clean):
    assert definitions.clean_gloss(dirty) == clean


def test_wordnet_sense_glosses_are_clean():
    sense = wordnet_sense("wizened", "ADJ")
    assert sense.gloss == "lean and wrinkled by shrinkage as from age or illness"


def test_ensure_sense_cleans_previously_cached_glosses(store):
    item_id = store.get_or_create_item("en", "pitiable", pos="ADJ")
    store.add_sense(item_id, "deserving or inciting pity; ; ; - Galsworthy", "en", "wordnet")
    sense = ensure_sense(store, store.find_item("en", "pitiable"))
    assert sense.gloss == "deserving or inciting pity"


def test_wordnet_sense_prefers_non_instance_synsets():
    # "china": first synset is the country (an instance); the porcelain
    # sense must win for vocabulary purposes.
    sense = wordnet_sense("china", "NOUN")
    assert "porcelain" in sense.gloss


def test_wordnet_sense_instance_only_words():
    # pure named entities still gloss for targets, but are excludable
    assert wordnet_sense("guevara", "NOUN") is not None
    assert wordnet_sense("guevara", "NOUN", include_instances=False) is None
    assert wordnet_sense("jacksonville", "NOUN", include_instances=False) is None
    # ordinary words are unaffected by the strict mode
    assert wordnet_sense("carthorse", "NOUN", include_instances=False) is not None


def test_wordnet_sense_finds_real_words_with_pos():
    sense = wordnet_sense("sagacious", "ADJ")
    assert sense is not None
    assert sense.provider == "wordnet"
    assert sense.gloss_language == "en"
    assert len(sense.gloss) > 5


def test_wordnet_sense_falls_back_across_pos():
    # "run" has no adjective synsets; the lookup should fall back to any POS.
    assert wordnet_sense("run", "ADJ") is not None


def test_wordnet_sense_unknown_word_and_language():
    assert wordnet_sense("xqzt", "NOUN") is None
    assert wordnet_sense("lopen", "VERB", language="nl") is None


def test_api_sense_prefers_matching_pos(monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: API_PAYLOAD)
    sense = api_sense("sagacious", "ADJ")
    assert sense == Sense("having keen judgement", "en", "api")


def test_api_sense_falls_back_to_first_gloss(monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: API_PAYLOAD)
    sense = api_sense("sagacious", "VERB")
    assert sense.gloss == "a wise-noun gloss"


def test_api_sense_handles_failure_and_unsupported_language(monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: None)
    assert api_sense("sagacious", "ADJ") is None
    assert api_sense("lopen", "VERB", language="nl") is None


def test_ensure_sense_caches_wordnet_hit(store):
    item_id = store.get_or_create_item("en", "sagacious", pos="ADJ")
    item = store.find_item("en", "sagacious")

    first = ensure_sense(store, item)
    assert first.provider == "wordnet"
    assert len(store.senses_for(item_id)) == 1

    # Second call must be served from the cache, not WordNet.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            definitions, "wordnet_sense", lambda *a, **k: pytest.fail("cache missed")
        )
        assert ensure_sense(store, item) == first
    assert len(store.senses_for(item_id)) == 1


def test_ensure_sense_falls_back_to_api_and_caches(store, monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: API_PAYLOAD)
    item_id = store.get_or_create_item("en", "xqzt", pos="ADJ")
    item = store.find_item("en", "xqzt")

    sense = ensure_sense(store, item)
    assert sense.provider == "api"
    cached = store.senses_for(item_id)
    assert len(cached) == 1 and cached[0]["provider"] == "api"


def test_ensure_sense_offline_only_skips_api(store):
    store.get_or_create_item("en", "xqzt", pos="ADJ")
    item = store.find_item("en", "xqzt")
    # The autouse no_network fixture fails the test if the API is touched.
    assert ensure_sense(store, item, allow_api=False) is None
    assert store.senses_for(item["id"]) == []
