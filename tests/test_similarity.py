import numpy as np
import pytest
import spacy

from prelexy.similarity import SpacyVectors

VECTORS = {
    "red": [1.0, 0.0, 0.0],
    "crimson": [0.95, 0.05, 0.0],
    "dog": [0.0, 1.0, 0.0],
    "the": [0.0, 0.0, 1.0],  # stopword WITH a vector, to prove filtering
}


@pytest.fixture(scope="module")
def provider():
    nlp = spacy.blank("en")
    for word, vector in VECTORS.items():
        nlp.vocab.set_vector(word, np.array(vector, dtype="float32"))
    return SpacyVectors(nlp)


def test_word_similarity(provider):
    assert provider.similarity("red", "crimson") > 0.9
    assert provider.similarity("red", "dog") < 0.1
    assert provider.similarity("red", "unknownword") is None


def test_text_similarity_compares_content_vectors(provider):
    close = provider.text_similarity("a red colour", "a crimson shade")
    far = provider.text_similarity("a red colour", "a dog barking")
    assert close > 0.9
    assert far < 0.1


def test_text_similarity_ignores_stopwords(provider):
    # "the" has a deliberately orthogonal vector; if it leaked into the
    # average, these two texts could not stay near-identical.
    assert provider.text_similarity("the the the red", "crimson") > 0.9


def test_text_similarity_none_without_content(provider):
    assert provider.text_similarity("xyzzy blorp", "a red colour") is None
    assert provider.text_similarity("", "red") is None
