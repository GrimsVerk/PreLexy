"""Word- and text-similarity providers (docs/DESIGN.md, "SimilarityProvider").

The MCQ generator depends only on the protocol below. Today's implementation
reads spaCy word vectors; the future code-docs mode plugs in custom-trained
embeddings here without touching anything downstream.

`text_similarity` is what distractor selection uses: it compares definition
texts, not the words themselves. Rare literary words are usually missing
from the model's pruned vector table (playtest: 5 of 6 sampled targets had
no vector), but their definitions are ordinary prose — so gloss-vs-gloss
similarity has near-total coverage and directly measures what the player
experiences: how confusable two definitions are.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np


class SimilarityProvider(Protocol):
    def similarity(self, a: str, b: str) -> float | None:
        """Word-level cosine in [-1, 1]; None when either word is unknown."""

    def text_similarity(self, a: str, b: str) -> float | None:
        """Cosine between two texts; None when either has no usable content."""


class SpacyVectors:
    """Similarity from a spaCy pipeline's word vectors (needs the md model)."""

    def __init__(self, nlp: Any) -> None:
        self._nlp = nlp
        self._vocab = nlp.vocab
        # distractor scans compare one correct gloss against hundreds of
        # candidates; caching text vectors makes that target-side free
        self._text_vectors: dict[str, np.ndarray[Any, np.dtype[Any]] | None] = {}

    def similarity(self, a: str, b: str) -> float | None:
        lex_a, lex_b = self._vocab[a], self._vocab[b]
        if not lex_a.has_vector or not lex_b.has_vector:
            return None
        return float(lex_a.similarity(lex_b))

    def text_similarity(self, a: str, b: str) -> float | None:
        vec_a, vec_b = self._text_vector(a), self._text_vector(b)
        if vec_a is None or vec_b is None:
            return None
        return float(np.dot(vec_a, vec_b))

    def _text_vector(self, text: str) -> np.ndarray[Any, np.dtype[Any]] | None:
        """Unit vector of the averaged content-token vectors (cached).

        Stopwords and punctuation are excluded: averaging them in inflates
        the similarity of any two English sentences.
        """
        if text in self._text_vectors:
            return self._text_vectors[text]
        doc = self._nlp.make_doc(text)  # tokenizer only — no pipeline needed
        vectors = [
            token.vector
            for token in doc
            if token.has_vector and not token.is_stop and not token.is_punct
        ]
        result = None
        if vectors:
            mean = np.mean(vectors, axis=0)
            norm = np.linalg.norm(mean)
            if norm > 0:
                result = mean / norm
        self._text_vectors[text] = result
        return result
