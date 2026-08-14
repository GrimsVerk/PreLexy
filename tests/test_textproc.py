import pytest
import spacy
from spacy.tokens import Doc

from prelexy.textproc import (
    Candidate,
    _paragraphs,
    collect_candidates,
    extract_candidates,
    in_dictionary,
    item_form,
    load_nlp,
)

VOCAB = spacy.blank("en").vocab


def make_doc(words, lemmas, pos, sent_starts=None):
    """Build a fully annotated Doc by hand, so no statistical model is needed."""
    if sent_starts is None:
        sent_starts = [i == 0 for i in range(len(words))]
    return Doc(VOCAB, words=words, lemmas=lemmas, pos=pos, sent_starts=sent_starts)


def test_paragraphs_yields_blocks_with_offsets():
    text = "First block.\n\nSecond\nblock.\n\n\n\nThird."
    blocks = list(_paragraphs(text))
    assert [b for b, _ in blocks] == ["First block.", "Second\nblock.", "Third."]
    for block, offset in blocks:
        assert text[offset : offset + len(block)] == block


def test_in_dictionary_accepts_real_words_and_rejects_ocr_garbage():
    assert in_dictionary("sagacious")
    assert in_dictionary("run")
    assert not in_dictionary("xqzt")
    assert not in_dictionary("wia")  # actual OCR junk from the Dorian Gray scan


def test_collect_filters_stopwords_propn_and_garbage():
    doc = make_doc(
        words=["The", "sagacious", "professor", "saw", "London", "and", "xqzt", "."],
        lemmas=["the", "sagacious", "professor", "see", "London", "and", "xqzt", "."],
        pos=["DET", "ADJ", "NOUN", "VERB", "PROPN", "CCONJ", "NOUN", "PUNCT"],
    )
    forms = {c.form for c in collect_candidates([(doc, 0)], "en")}
    assert forms == {"sagacious", "professor", "see"}


def test_collect_merges_inflections_into_one_lemma_item():
    doc_a = make_doc(
        words=["He", "ran", "far", "."],
        lemmas=["he", "run", "far", "."],
        pos=["PRON", "VERB", "ADV", "PUNCT"],
    )
    doc_b = make_doc(
        words=["She", "is", "running", "."],
        lemmas=["she", "be", "run", "."],
        pos=["PRON", "AUX", "VERB", "PUNCT"],
    )
    candidates = collect_candidates([(doc_a, 0), (doc_b, 100)], "en")
    runs = [c for c in candidates if c.form == "run"]
    assert len(runs) == 1
    assert len(runs[0].occurrences) == 2


def test_collect_records_sentence_context_and_absolute_offset():
    doc = make_doc(
        words=["He", "perambulated", "slowly", "."],
        lemmas=["he", "perambulate", "slowly", "."],
        pos=["PRON", "VERB", "ADV", "PUNCT"],
    )
    (candidate,) = [c for c in collect_candidates([(doc, 500)], "en") if c.form == "perambulate"]
    (context, position) = candidate.occurrences[0]
    assert context == "He perambulated slowly ."
    assert position == 500 + doc[1].idx


def test_collect_ranks_rarest_first():
    doc = make_doc(
        words=["professor", "perambulated", "sagacious"],
        lemmas=["professor", "perambulate", "sagacious"],
        pos=["NOUN", "VERB", "ADJ"],
    )
    candidates = collect_candidates([(doc, 0)], "en")
    zipfs = [c.zipf for c in candidates]
    assert zipfs == sorted(zipfs)
    assert candidates[-1].form == "professor"  # by far the most common of the three


def test_item_form_policy_lemma_for_english_surface_otherwise():
    doc = make_doc(words=["running"], lemmas=["run"], pos=["VERB"])
    assert item_form(doc[0], "en") == "run"
    assert item_form(doc[0], "nl") == "running"


try:
    _NLP = load_nlp("en")
except (OSError, ValueError):
    _NLP = None


@pytest.mark.skipif(_NLP is None, reason="no spaCy English model installed")
def test_extract_candidates_end_to_end_with_real_model():
    text = (
        "The sagacious old man perambulated through London.\n\n"
        "He was perambulating again when Dorian saw him."
    )
    candidates = extract_candidates(text, "en", nlp=_NLP)
    by_form = {c.form: c for c in candidates}
    assert "perambulate" in by_form
    assert len(by_form["perambulate"].occurrences) == 2
    assert "london" not in by_form and "dorian" not in by_form
    assert "the" not in by_form
    assert all(isinstance(c, Candidate) for c in candidates)
