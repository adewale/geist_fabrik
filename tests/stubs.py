"""Deterministic external-library stubs shared by the test suite."""

import hashlib
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

        embeddings: list[np.ndarray] = []
        for text in texts:
            text_hash = hashlib.sha256(text.encode()).digest()
            repeats = (SEMANTIC_DIM + len(text_hash) - 1) // len(text_hash)
            extended = (text_hash * repeats)[:SEMANTIC_DIM]
            embedding = np.array([byte / 128.0 - 1.0 for byte in extended], dtype=np.float32)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            embeddings.append(embedding)

        result = np.array(embeddings, dtype=np.float32)
        return result[0] if is_single else result
