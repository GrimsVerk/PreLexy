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
def provider() -> SpacyVectors:
    nlp = spacy.blank("en")
    for word, vector in VECTORS.items():
        nlp.vocab.set_vector(word, np.array(vector, dtype="float32"))  # type: ignore[arg-type]
    return SpacyVectors(nlp)


def score(value: float | None) -> float:
    """A similarity the test requires to exist."""
    assert value is not None
    return value


def test_word_similarity(provider: SpacyVectors) -> None:
    assert score(provider.similarity("red", "crimson")) > 0.9
    assert score(provider.similarity("red", "dog")) < 0.1
    assert provider.similarity("red", "unknownword") is None


def test_text_similarity_compares_content_vectors(provider: SpacyVectors) -> None:
    close = provider.text_similarity("a red colour", "a crimson shade")
    far = provider.text_similarity("a red colour", "a dog barking")
    assert score(close) > 0.9
    assert score(far) < 0.1


def test_text_similarity_ignores_stopwords(provider: SpacyVectors) -> None:
    # "the" has a deliberately orthogonal vector; if it leaked into the
    # average, these two texts could not stay near-identical.
    assert score(provider.text_similarity("the the the red", "crimson")) > 0.9


def test_text_similarity_none_without_content(provider: SpacyVectors) -> None:
    assert provider.text_similarity("xyzzy blorp", "a red colour") is None
    assert provider.text_similarity("", "red") is None
