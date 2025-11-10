"""Shared test fixtures for unit tests."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import numpy as np
import pytest

from geistfabrik.models import Note


@pytest.fixture
def sample_notes():
    """Create sample notes for testing."""
    base_date = datetime(2023, 1, 1)
    return [
        Note(
            path="note1.md",
            title="First Note",
            content="This is about machine learning and AI.",
            links=[],
            tags=["ai"],
            created=base_date,
            modified=base_date,
        ),
        Note(
            path="note2.md",
            title="Second Note",
            content="This discusses neural networks and deep learning.",
            links=[],
            tags=["ai", "ml"],
            created=base_date + timedelta(days=30),
            modified=base_date + timedelta(days=30),
        ),
        Note(
            path="note3.md",
            title="Third Note",
            content="This is about cooking recipes and food preparation.",
            links=[],
            tags=["cooking"],
            created=base_date + timedelta(days=60),
            modified=base_date + timedelta(days=60),
        ),
    ]


@pytest.fixture
def mock_sentence_transformer():
    """Create a mock SentenceTransformer for unit testing.

    Returns embeddings that are deterministic based on text content,
    allowing tests to verify logic without requiring the real model.
    """
    mock = Mock()

    def mock_encode(text_or_texts, convert_to_numpy=True, show_progress_bar=False, batch_size=8):
        """Mock encode that returns deterministic embeddings based on text hash."""
        # Handle both single text and batch
        is_batch = isinstance(text_or_texts, list)
        texts = text_or_texts if is_batch else [text_or_texts]

        embeddings = []
        for text in texts:
            # Create deterministic embedding based on text content
            # Use hash of text to seed random generator for reproducibility
            seed = hash(text) % (2**32)
            rng = np.random.RandomState(seed)
            embedding = rng.randn(384).astype(np.float32)
            # Normalise to unit vector (like real sentence-transformers)
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)

        if convert_to_numpy:
            result = np.array(embeddings, dtype=np.float32)
            return result if is_batch else result[0]
        else:
            return embeddings if is_batch else embeddings[0]

    mock.encode = mock_encode
    return mock


@pytest.fixture
def mock_embedding_computer(mock_sentence_transformer):
    """Create a mocked EmbeddingComputer for unit testing.

    This avoids model downloads and allows fast, deterministic testing.
    """
    from geistfabrik.embeddings import EmbeddingComputer

    computer = EmbeddingComputer()
    computer._model = mock_sentence_transformer
    return computer


@pytest.fixture
def fixed_embeddings():
    """Pre-computed fixed embeddings for testing similarity calculations.

    These are simple, interpretable vectors for testing cosine similarity
    and similar_notes logic without requiring model computation.
    """
    return {
        "note1.md": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "note2.md": np.array([0.9, 0.1, 0.0], dtype=np.float32),
        "note3.md": np.array([0.0, 1.0, 0.0], dtype=np.float32),
        "note4.md": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    }
