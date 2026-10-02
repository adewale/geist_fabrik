"""Integration tests for embeddings module (real models).

These tests use the actual SentenceTransformer model and are slower.
They cover what only real weights can show: a semantic known answer, and
end-to-end session storage, empty and over-length inputs through the real
tokenizer. Model-independent behaviour (temporal composition, semantic cache)
is owned by tests/unit/test_embeddings.py with the stub.

Run separately with: pytest -v tests/integration/test_embeddings_integration.py
The required package-smoke CI job also verifies real offline inference from an installed wheel.
"""

from datetime import datetime, timedelta

import numpy as np
import pytest

from geistfabrik.config import SEMANTIC_DIM, TOTAL_DIM
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
    pytest.mark.production_model,
    pytest.mark.timeout(60),  # 60 second timeout for model loading + computation
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


def test_real_session_embeddings(db_with_notes, sample_notes):
    """Test end-to-end session embedding computation with real model."""
    session = Session(datetime(2023, 6, 15), db_with_notes)

    # Compute embeddings for all notes
    session.compute_embeddings(sample_notes)

    # Verify all embeddings were stored through the public vector backend.
    backend = session.get_backend()
    embeddings = {note.path: backend.get_embedding(note.path) for note in sample_notes}
    assert len(embeddings) == len(sample_notes)

    # The backend serves the meaning vector it compares (the 384 semantic
    # dims); storage keeps the 3 calendar features too.
    for path, embedding in embeddings.items():
        assert embedding.shape == (SEMANTIC_DIM,)
        assert np.any(embedding != 0), f"Embedding for {path} should be non-zero"
    stored = db_with_notes.execute("SELECT embedding FROM session_embeddings").fetchall()
    assert len(stored) == len(sample_notes)
    assert {len(blob) for (blob,) in stored} == {TOTAL_DIM * 4}  # float32


def test_real_empty_content_handling(db_with_notes, sample_notes):
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
    session.compute_embeddings([*sample_notes, note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)


def test_real_very_long_content(db_with_notes, sample_notes):
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
    session.compute_embeddings([*sample_notes, note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)
