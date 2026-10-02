"""Meaning dimensions of stored session embeddings.

A stored session embedding is the sentence-transformer vector (SEMANTIC_DIM
dimensions) followed by TEMPORAL_DIM calendar features (note age, creation
season, session season). Similarity, neighbours, clustering, surprisal and
drift are claims about what notes *mean*, so they use the semantic part
only: with the calendar features included, notes of similar age looked
more alike, and "similar" counts shifted between sessions on unchanged text.
"""

import numpy as np

from .config import SEMANTIC_DIM, TOTAL_DIM

#: Bytes of the semantic prefix of a float32 session embedding blob.
SEMANTIC_BYTES = SEMANTIC_DIM * np.dtype(np.float32).itemsize


def meaning_vector(embedding: np.ndarray) -> np.ndarray:
    """Return the semantic dimensions of a session embedding.

    Vectors of any other size (injected or test embeddings) pass through
    unchanged.
    """
    vector = np.asarray(embedding)
    if vector.size == TOTAL_DIM:
        return vector[:SEMANTIC_DIM]
    return vector


def decode_meaning_vector(blob: bytes) -> np.ndarray:
    """Decode a stored float32 embedding blob to its semantic dimensions."""
    return meaning_vector(np.frombuffer(blob, dtype=np.float32))


def meaning_blob(blob: bytes) -> bytes:
    """The semantic prefix of a stored embedding blob (for sqlite-vec)."""
    if len(blob) == TOTAL_DIM * np.dtype(np.float32).itemsize:
        return blob[:SEMANTIC_BYTES]
    return blob
