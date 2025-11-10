"""Integration tests for embeddings module (real models).

These tests use the actual SentenceTransformer model and are slower.
They verify end-to-end behaviour with real embeddings.

Run separately with: pytest -v tests/integration/test_embeddings_integration.py
Mark as slow: pytest -m "not slow" to skip these in CI
"""

from datetime import datetime, timedelta

import numpy as np
import pytest

from geistfabrik.embeddings import (
    EmbeddingComputer,
    Session,
    cosine_similarity,
)
from geistfabrik.models import Note
from geistfabrik.schema import init_db

# Mark all tests as slow and integration
pytestmark = [
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.timeout(60),  # 60 second timeout for model download + computation
]


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
def db_with_notes(sample_notes):
    """Database with sample notes inserted."""
    db = init_db()

    for note in sample_notes:
        db.execute(
            """
            INSERT INTO notes (path, title, content, created, modified, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                note.path,
                note.title,
                note.content,
                note.created.isoformat(),
                note.modified.isoformat(),
                note.modified.timestamp(),
            ),
        )
    db.commit()

    yield db
    db.close()


def test_real_model_loading():
    """Test that the real SentenceTransformer model loads successfully.

    This test verifies:
    - Model can be downloaded/loaded from cache
    - Model produces embeddings of correct shape
    - Model loading doesn't hang indefinitely
    """
    computer = EmbeddingComputer()

    # Trigger lazy loading
    text = "Test sentence for model loading."
    embedding = computer.compute_semantic(text)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (384,)
    assert computer._model is not None


def test_real_semantic_embeddings(sample_notes):
    """Test that real model produces semantically meaningful embeddings.

    Verifies that:
    - AI-related notes are more similar to each other
    - Unrelated notes (AI vs cooking) have lower similarity
    """
    computer = EmbeddingComputer()

    # Compute embeddings for all notes
    note1_embedding = computer.compute_semantic(sample_notes[0].content)  # AI
    note2_embedding = computer.compute_semantic(sample_notes[1].content)  # Neural networks
    note3_embedding = computer.compute_semantic(sample_notes[2].content)  # Cooking

    # AI notes should be more similar to each other than to cooking note
    sim_ai = cosine_similarity(note1_embedding, note2_embedding)
    sim_cooking_1 = cosine_similarity(note1_embedding, note3_embedding)
    sim_cooking_2 = cosine_similarity(note2_embedding, note3_embedding)

    # These assertions verify the model understands semantic similarity
    assert sim_ai > 0.5, "AI-related notes should have high similarity"
    assert sim_ai > sim_cooking_1, "AI notes should be more similar to each other than to cooking"
    assert sim_ai > sim_cooking_2, "AI notes should be more similar to each other than to cooking"


def test_real_temporal_embeddings(sample_notes):
    """Test that temporal embeddings combine semantic and temporal correctly."""
    computer = EmbeddingComputer()
    session_date = datetime(2023, 6, 15)

    embedding = computer.compute_temporal_embedding(sample_notes[0], session_date)

    # Verify shape
    assert embedding.shape == (387,)

    # Verify semantic portion is non-zero (first 384 dims)
    semantic_portion = embedding[:384]
    assert np.any(semantic_portion != 0), "Semantic portion should be non-zero"

    # Verify temporal portion is non-zero (last 3 dims)
    temporal_portion = embedding[384:]
    assert np.any(temporal_portion != 0), "Temporal portion should be non-zero"


def test_real_session_embeddings(db_with_notes, sample_notes):
    """Test end-to-end session embedding computation with real model."""
    session = Session(datetime(2023, 6, 15), db_with_notes)

    # Compute embeddings for all notes
    session.compute_embeddings(sample_notes)

    # Verify all embeddings were stored
    embeddings = session.get_all_embeddings()
    assert len(embeddings) == len(sample_notes)

    # Verify embedding quality
    for path, embedding in embeddings.items():
        assert embedding.shape == (387,)
        assert np.any(embedding != 0), f"Embedding for {path} should be non-zero"


def test_real_semantic_cache(db_with_notes, sample_notes):
    """Test that semantic embeddings are cached correctly with real model."""
    # First session computes embeddings
    session1 = Session(datetime(2023, 6, 15), db_with_notes)
    session1.compute_embeddings(sample_notes)

    # Get embedding for note1
    embedding1 = session1.get_embedding(sample_notes[0].path)

    # Second session on different date should reuse cached semantic embeddings
    session2 = Session(datetime(2023, 6, 16), db_with_notes)

    # Check cache before computing
    cached_semantic = session2._get_cached_semantic_embedding(sample_notes[0])
    assert cached_semantic is not None, "Semantic embedding should be cached"

    # Compute embeddings for session 2
    session2.compute_embeddings(sample_notes)

    # Get embedding for note1 in session 2
    embedding2 = session2.get_embedding(sample_notes[0].path)

    # Temporal embeddings will differ (different session dates)
    # but they should both be valid
    assert embedding1 is not None
    assert embedding2 is not None
    assert embedding1.shape == embedding2.shape


def test_real_batch_computation(db_with_notes):
    """Test batch embedding computation with real model."""
    # Create multiple notes
    notes = []
    for i in range(10):
        note = Note(
            path=f"batch_{i}.md",
            title=f"Batch Note {i}",
            content=f"This is test content for batch note number {i}.",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )
        notes.append(note)

        # Insert into database
        db_with_notes.execute(
            """
            INSERT INTO notes (path, title, content, created, modified, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                note.path,
                note.title,
                note.content,
                note.created.isoformat(),
                note.modified.isoformat(),
                note.modified.timestamp(),
            ),
        )
    db_with_notes.commit()

    # Compute embeddings in batch
    session = Session(datetime(2023, 6, 15), db_with_notes)
    session.compute_embeddings(notes)

    # Verify all embeddings were computed
    embeddings = session.get_all_embeddings()
    assert len(embeddings) == len(notes)

    for note in notes:
        embedding = session.get_embedding(note.path)
        assert embedding is not None
        assert embedding.shape == (387,)


def test_real_empty_content_handling(db_with_notes):
    """Test that real model handles empty/whitespace content gracefully."""
    note = Note(
        path="empty_real.md",
        title="Empty Note",
        content="   \n\n   ",
        links=[],
        tags=[],
        created=datetime(2023, 1, 1),
        modified=datetime(2023, 1, 1),
    )

    # Insert note
    db_with_notes.execute(
        """
        INSERT INTO notes (path, title, content, created, modified, file_mtime)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            note.path,
            note.title,
            note.content,
            note.created.isoformat(),
            note.modified.isoformat(),
            note.modified.timestamp(),
        ),
    )
    db_with_notes.commit()

    # Should handle gracefully
    session = Session(datetime(2023, 6, 15), db_with_notes)
    session.compute_embeddings([note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)


def test_real_very_long_content(db_with_notes):
    """Test that real model handles very long content.

    Most sentence-transformers models have a token limit (~512 tokens).
    This test verifies graceful handling of longer content.
    """
    # Create note with ~15000 words (much longer than model's token limit)
    long_content = " ".join([f"word{i}" for i in range(15000)])
    note = Note(
        path="long_real.md",
        title="Very Long Note",
        content=long_content,
        links=[],
        tags=[],
        created=datetime(2023, 1, 1),
        modified=datetime(2023, 1, 1),
    )

    # Insert note
    db_with_notes.execute(
        """
        INSERT INTO notes (path, title, content, created, modified, file_mtime)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            note.path,
            note.title,
            note.content,
            note.created.isoformat(),
            note.modified.isoformat(),
            note.modified.timestamp(),
        ),
    )
    db_with_notes.commit()

    # Should not crash (model will truncate)
    session = Session(datetime(2023, 6, 15), db_with_notes)
    session.compute_embeddings([note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)
