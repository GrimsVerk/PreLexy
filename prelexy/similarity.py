"""Word-similarity providers (docs/DESIGN.md, "SimilarityProvider interface").

The MCQ generator depends only on the protocol below. Today's implementation
reads spaCy word vectors; the future code-docs mode plugs in custom-trained
embeddings here without touching anything downstream.
"""

from __future__ import annotations

from typing import Protocol


class SimilarityProvider(Protocol):
    def similarity(self, a: str, b: str) -> float | None:
        """Cosine similarity in [-1, 1], or None when either word is unknown."""


class SpacyVectors:
    """Similarity from a spaCy pipeline's word vectors (needs the md model)."""

    def __init__(self, nlp):
        self._vocab = nlp.vocab

    def similarity(self, a: str, b: str) -> float | None:
        lex_a, lex_b = self._vocab[a], self._vocab[b]
        if not lex_a.has_vector or not lex_b.has_vector:
            return None
        return float(lex_a.similarity(lex_b))
