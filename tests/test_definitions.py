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


def test_dutch_words_get_english_glosses_via_omw():
    sense = wordnet_sense("huis", "NOUN", "nl")
    assert sense is not None
    assert sense.gloss_language == "en"
    assert "roof" in sense.gloss or "structure" in sense.gloss
    # documented residual: OMW's Dutch adjectives are thin (DECISIONS 023)
    assert wordnet_sense("mooi", "ADJ", "nl") is None


def test_dutch_distractor_pool_exists():
    names = definitions.wordnet_lemma_names("NOUN", "nl")
    assert len(names) > 10_000
    assert "fiets" in names


def test_ensure_sense_falls_back_to_the_lemma_for_surface_forms(store):
    # L2 items keep the surface form ("liep"); OMW keys on lemmas ("lopen")
    item_id = store.get_or_create_item("nl", "liep", lemma="lopen", pos="VERB")
    sense = ensure_sense(store, store.find_item("nl", "liep"))
    assert sense is not None
    assert sense.gloss_language == "en"
    assert len(store.senses_for(item_id)) == 1


def test_dutch_synonym_conflict():
    assert definitions.synonym_conflict("huis", "woning", "NOUN", language="nl")
    assert not definitions.synonym_conflict("huis", "fiets", "NOUN", language="nl")


def test_synonym_conflict_catches_synonyms_and_direct_relatives():
    assert definitions.synonym_conflict("sagacious", "sapient", "ADJ")  # shared lemma
    assert definitions.synonym_conflict("joy", "delight", "NOUN")  # shared lemma
    assert definitions.synonym_conflict("dog", "puppy", "NOUN")  # direct hyponym
    # cousins and unrelated words stay fair
    assert not definitions.synonym_conflict("vermilion", "goethite", "NOUN")
    assert not definitions.synonym_conflict("joyousness", "gleefulness", "NOUN")


def test_wordnet_sense_finds_real_words_with_pos():
    sense = wordnet_sense("sagacious", "ADJ")
    assert sense is not None
    assert sense.provider == "wordnet"
    assert sense.gloss_language == "en"
    assert len(sense.gloss) > 5


def test_wordnet_sense_falls_back_across_pos():
    # "run" has no adjective synsets; the lookup should fall back to any POS.
    assert wordnet_sense("run", "ADJ") is not None


def test_wordnet_sense_reports_the_gloss_pos():
    assert wordnet_sense("carthorse", "NOUN").pos == "NOUN"
    # ADJ item whose only synsets are verbs: the fallback POS is reported
    assert wordnet_sense("gartered", "ADJ").pos == "VERB"
    # satellite adjectives count as ADJ
    assert wordnet_sense("unpictured", "ADJ").pos == "ADJ"


def test_wordnet_sense_unknown_word():
    assert wordnet_sense("xqzt", "NOUN") is None
    assert wordnet_sense("xqzt", "NOUN", language="nl") is None


def test_api_sense_prefers_matching_pos(monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: API_PAYLOAD)
    sense = api_sense("sagacious", "ADJ")
    assert sense == Sense("having keen judgement", "en", "api", pos="ADJ")


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
        mp.setattr(definitions, "wordnet_sense", lambda *a, **k: pytest.fail("cache missed"))
        cached = ensure_sense(store, item)
    assert (cached.gloss, cached.gloss_language, cached.provider) == (
        first.gloss,
        first.gloss_language,
        first.provider,
    )
    assert cached.pos is None  # by design: the senses table stores no POS
    assert len(store.senses_for(item_id)) == 1


def test_ensure_sense_falls_back_to_api_and_caches(store, monkeypatch):
    monkeypatch.setattr(definitions, "_fetch_api_json", lambda url: API_PAYLOAD)
    item_id = store.get_or_create_item("en", "xqzt", pos="ADJ")
    item = store.find_item("en", "xqzt")

    sense = ensure_sense(store, item)
    assert sense.provider == "api"
    cached = store.senses_for(item_id)
    assert len(cached) == 1 and cached[0]["provider"] == "api"


KAIKKI_SAMPLE = "\n".join(
    [
        '{"word": "mooi", "pos": "noun", "lang_code": "nl", "senses": [{"glosses": ["a beauty (wrong POS)"]}]}',  # noqa: E501
        '{"word": "mooi", "pos": "adj", "lang_code": "nl", "senses": [{"glosses": ["beautiful, handsome"]}]}',  # noqa: E501
        '{"word": "gezellig", "pos": "adj", "lang_code": "nl", "senses": [{"glosses": ["cozy, convivial"]}]}',  # noqa: E501
        '{"word": "gezellig", "pos": "adj", "lang_code": "de", "senses": [{"glosses": ["WRONG LANGUAGE"]}]}',  # noqa: E501
        '{"word": "liep", "pos": "verb", "lang_code": "nl", "senses": [{"glosses": ["should not be used"]}]}',  # noqa: E501
        "not json at all",
        '{"word": "onbekend", "pos": "adj", "lang_code": "nl", "senses": []}',
    ]
)


def test_import_kaikki_glosses_fills_gaps_with_pos_preference(store, tmp_path):
    mooi = store.get_or_create_item("nl", "mooi", lemma="mooi", pos="ADJ")
    store.get_or_create_item("nl", "gezellig", lemma="gezellig", pos="ADJ")
    already = store.get_or_create_item("nl", "liep", lemma="lopen", pos="VERB")
    store.add_sense(already, "existing gloss", "en", "wordnet")

    extract = tmp_path / "kaikki-nl.jsonl"
    extract.write_text(KAIKKI_SAMPLE)
    filled, missing = definitions.import_kaikki_glosses(store, extract, "nl")
    assert (filled, missing) == (2, 2)

    sense = ensure_sense(store, store.find_item("nl", "mooi"))
    assert sense.gloss == "beautiful, handsome"  # POS-matched entry won
    assert sense.provider == "wiktionary"
    assert ensure_sense(store, store.find_item("nl", "gezellig")).gloss == "cozy, convivial"
    assert ensure_sense(store, store.find_item("nl", "liep")).gloss == "existing gloss"
    assert store.senses_for(mooi)[0]["gloss_language"] == "en"


def test_import_kaikki_unsuspends_newly_glossed_items(store, tmp_path):
    profile = store.get_or_create_profile("p")
    gezellig = store.get_or_create_item("nl", "gezellig", lemma="gezellig", pos="ADJ")
    unglossed = store.get_or_create_item("nl", "onbekend", lemma="onbekend", pos="ADJ")
    store.upsert_item_state(profile, gezellig, "suspended", None, {})
    store.upsert_item_state(profile, unglossed, "suspended", None, {})
    extract = tmp_path / "kaikki.jsonl"
    extract.write_text(KAIKKI_SAMPLE)

    definitions.import_kaikki_glosses(store, extract, "nl")
    states = {
        row["item_id"]: row["status"]
        for row in store._conn.execute("SELECT * FROM item_state").fetchall()
    }
    assert gezellig not in states  # freed: it got a gloss
    assert states[unglossed] == "suspended"  # still unglossed, stays parked


def test_import_kaikki_streams_gzip_and_filters_language(store, tmp_path):
    import gzip

    store.get_or_create_item("nl", "gezellig", lemma="gezellig", pos="ADJ")
    extract = tmp_path / "raw-wiktextract-data.jsonl.gz"
    with gzip.open(extract, "wt", encoding="utf-8") as fh:
        fh.write(KAIKKI_SAMPLE)
    filled, missing = definitions.import_kaikki_glosses(store, extract, "nl")
    assert (filled, missing) == (1, 1)
    sense = ensure_sense(store, store.find_item("nl", "gezellig"))
    assert sense.gloss == "cozy, convivial"  # the de entry was skipped


def test_import_kaikki_prefers_real_glosses_over_form_of(store, tmp_path):
    # "abonneert" (surface) only has a form-of entry; its lemma "abonneren"
    # has the real gloss — the real gloss must win (2026-07-07 playtest).
    store.get_or_create_item("nl", "abonneert", lemma="abonneren", pos="VERB")
    store.get_or_create_item("nl", "graatje", lemma="graatje", pos="NOUN")
    extract = tmp_path / "kaikki.jsonl"
    extract.write_text(
        "\n".join(
            [
                '{"word": "abonneert", "pos": "verb", "lang_code": "nl",'
                ' "senses": [{"form_of": [{"word": "abonneren"}],'
                ' "glosses": ["inflection of abonneren:"]}]}',
                '{"word": "abonneren", "pos": "verb", "lang_code": "nl",'
                ' "senses": [{"glosses": ["to subscribe"]}]}',
                # graatje only exists as a form-of entry: used, minus the colon
                '{"word": "graatje", "pos": "noun", "lang_code": "nl",'
                ' "senses": [{"tags": ["form-of"], "glosses": ["diminutive of graat:"]}]}',
            ]
        )
    )
    filled, missing = definitions.import_kaikki_glosses(store, extract, "nl")
    assert (filled, missing) == (2, 2)
    assert ensure_sense(store, store.find_item("nl", "abonneert")).gloss == "to subscribe"
    assert ensure_sense(store, store.find_item("nl", "graatje")).gloss == "diminutive of graat"


def test_ensure_sense_offline_only_skips_api(store):
    store.get_or_create_item("en", "xqzt", pos="ADJ")
    item = store.find_item("en", "xqzt")
    # The autouse no_network fixture fails the test if the API is touched.
    assert ensure_sense(store, item, allow_api=False) is None
    assert store.senses_for(item["id"]) == []
