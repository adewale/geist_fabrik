"""Deterministic external-library stubs shared by the test suite."""

import hashlib
import re
from pathlib import Path
from typing import Any

import numpy as np

from geistfabrik.config import SEMANTIC_DIM


class SentenceTransformerStub:
    """Small constructor-compatible stand-in for ``SentenceTransformer``."""

    def __init__(
        self,
        model_name_or_path: str | Path,
        device: str | None = "cpu",
        local_files_only: bool = False,
        **kwargs: Any,
    ) -> None:
        self.model_name_or_path = str(model_name_or_path)
        self.device = device
        self.local_files_only = local_files_only
        self.constructor_kwargs = kwargs

    def encode(
        self,
        sentences: str | list[str],
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        batch_size: int = 32,
        **kwargs: Any,
    ) -> np.ndarray:
        """Generate deterministic, normalized 384-dimensional embeddings."""
        del convert_to_numpy, show_progress_bar, batch_size, kwargs
        is_single = isinstance(sentences, str)
        texts = [sentences] if is_single else sentences
        result = np.array([lexical_embedding(text) for text in texts], dtype=np.float32)
        return result[0] if is_single else result


_STOPWORDS = frozenset(
    "the a an and or of to in on for is are was were be been it its this that "
    "with as at by from not but have has had".split()
)


def lexical_embedding(text: str) -> np.ndarray:
    """Bag-of-words embedding: notes that share words are similar.

    Each content word adds +/-1 to a hashed dimension, so cosine similarity
    tracks vocabulary overlap: identical text gives 1.0, disjoint vocabulary
    gives roughly 0, and fixtures can make two *different* notes similar by
    giving them shared words. Text with no content words falls back to a
    SHA256-derived vector so every input still gets a distinct unit vector.
    """
    vector = np.zeros(SEMANTIC_DIM, dtype=np.float32)
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        digest = hashlib.sha256(word.encode()).digest()
        index = int.from_bytes(digest[:4], "little") % SEMANTIC_DIM
        vector[index] += 1.0 if digest[4] & 1 else -1.0

    if not vector.any():
        text_hash = hashlib.sha256(text.encode()).digest()
        repeats = (SEMANTIC_DIM + len(text_hash) - 1) // len(text_hash)
        extended = (text_hash * repeats)[:SEMANTIC_DIM]
        vector = np.array([byte / 128.0 - 1.0 for byte in extended], dtype=np.float32)

    return vector / np.linalg.norm(vector)
