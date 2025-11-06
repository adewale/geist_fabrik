"""Unit tests for embeddings module (mocked models)."""

from datetime import datetime

import numpy as np
import pytest

from geistfabrik.embeddings import (
    EmbeddingComputer,
    Session,
    cosine_similarity,
    find_similar_notes,
)
from geistfabrik.models import Note
from geistfabrik.schema import init_db

# Add 5 second timeout to ALL tests to prevent hangs
pytestmark = pytest.mark.timeout(5)


@pytest.fixture
def db_with_notes(sample_notes):
    """Database with sample notes inserted."""
    db = init_db()

    # Insert notes into database (required for foreign key constraints)
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


@pytest.fixture
def mocked_session(db_with_notes, mock_embedding_computer):
    """Session with mocked embedding computer for fast unit testing."""
    session = Session(datetime(2023, 6, 15), db_with_notes, computer=mock_embedding_computer)
    return session


def test_embedding_computer_initialization():
    """Test EmbeddingComputer initialization."""
    computer = EmbeddingComputer()
    assert computer.model_name == "all-MiniLM-L6-v2"
    assert computer._model is None  # Lazy loading


def test_embedding_computer_with_injected_model(mock_sentence_transformer):
    """Test EmbeddingComputer with pre-injected model (for testing)."""
    computer = EmbeddingComputer(model=mock_sentence_transformer)
    assert computer._model is mock_sentence_transformer
    assert computer._model is not None  # Model already injected


def test_compute_semantic_embedding_mock(mock_embedding_computer):
    """Test semantic embedding computation with mocked model."""
    text = "This is a test sentence."

    embedding = mock_embedding_computer.compute_semantic(text)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (384,)  # all-MiniLM-L6-v2 produces 384-dim embeddings

    # Verify deterministic behavior - same text produces same embedding
    embedding2 = mock_embedding_computer.compute_semantic(text)
    assert np.array_equal(embedding, embedding2)


def test_compute_temporal_features(sample_notes):
    """Test temporal features computation (doesn't require model)."""
    computer = EmbeddingComputer()
    note = sample_notes[0]
    session_date = datetime(2023, 6, 15)

    features = computer.compute_temporal_features(note, session_date)

    assert isinstance(features, np.ndarray)
    assert features.shape == (3,)

    # Note age should be positive
    assert features[0] > 0

    # Creation season and session season should be in [-1, 1] (sine values)
    assert -1 <= features[1] <= 1
    assert -1 <= features[2] <= 1


def test_compute_temporal_embedding_mock(sample_notes, mock_embedding_computer):
    """Test combined temporal embedding computation with mocked model."""
    note = sample_notes[0]
    session_date = datetime(2023, 6, 15)

    embedding = mock_embedding_computer.compute_temporal_embedding(note, session_date)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (387,)  # 384 semantic + 3 temporal


def test_session_creation(db_with_notes):
    """Test session creation and retrieval."""
    date = datetime(2023, 6, 15)

    session = Session(date, db_with_notes)

    assert session.date == date
    assert session.session_id > 0
    assert session.db is db_with_notes

    # Verify session was stored in database
    cursor = db_with_notes.execute(
        "SELECT date FROM sessions WHERE session_id = ?", (session.session_id,)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "2023-06-15"


def test_session_reuse(db_with_notes):
    """Test that sessions with same date are reused."""
    date = datetime(2023, 6, 15)

    session1 = Session(date, db_with_notes)
    session2 = Session(date, db_with_notes)

    assert session1.session_id == session2.session_id


def test_compute_vault_state_hash(mocked_session, sample_notes):
    """Test vault state hash computation."""
    hash1 = mocked_session.compute_vault_state_hash(sample_notes)
    hash2 = mocked_session.compute_vault_state_hash(sample_notes)

    # Same notes should produce same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64 hex characters

    # Different notes should produce different hash
    modified_notes = sample_notes[:2]
    hash3 = mocked_session.compute_vault_state_hash(modified_notes)
    assert hash1 != hash3


def test_compute_embeddings_mock(mocked_session, sample_notes):
    """Test embedding computation with mocked model."""
    mocked_session.compute_embeddings(sample_notes)

    # Verify embeddings were stored
    cursor = mocked_session.db.execute(
        "SELECT COUNT(*) FROM session_embeddings WHERE session_id = ?",
        (mocked_session.session_id,),
    )
    count = cursor.fetchone()[0]
    assert count == len(sample_notes)

    # Verify we can retrieve embeddings
    for note in sample_notes:
        embedding = mocked_session.get_embedding(note.path)
        assert embedding is not None
        assert embedding.shape == (387,)


def test_cosine_similarity():
    """Test cosine similarity computation."""
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    c = np.array([0.0, 1.0, 0.0])

    # Identical vectors should have similarity 1.0
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-6

    # Orthogonal vectors should have similarity 0.0
    assert abs(cosine_similarity(a, c)) < 1e-6

    # Zero vector should have similarity 0.0
    zero = np.array([0.0, 0.0, 0.0])
    assert cosine_similarity(a, zero) == 0.0


def test_find_similar_notes(fixed_embeddings):
    """Test finding similar notes with fixed embeddings."""
    query = np.array([1.0, 0.0, 0.0])

    # Find 2 most similar notes
    results = find_similar_notes(query, fixed_embeddings, k=2)

    assert len(results) == 2
    assert results[0][0] == "note1.md"  # Exact match
    assert results[1][0] == "note2.md"  # Close match

    # Test with exclusion
    results = find_similar_notes(query, fixed_embeddings, k=2, exclude_paths={"note1.md"})

    assert len(results) == 2
    assert results[0][0] == "note2.md"
    assert "note1.md" not in [r[0] for r in results]


def test_embed_very_long_note_mock(db_with_notes, mock_embedding_computer):
    """Test handling of very long notes with mocked model (AC-2.7)."""
    # Create a note with very long content (>10000 words)
    long_content = " ".join(["word" for _ in range(15000)])
    note = Note(
        path="long.md",
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

    # Should not crash, might truncate
    session = Session(datetime(2023, 6, 15), db_with_notes, computer=mock_embedding_computer)
    session.compute_embeddings([note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)


def test_empty_embedding_handling_mock(db_with_notes, mock_embedding_computer):
    """Test handling of notes with minimal/empty content (AC-2.14)."""
    # Create a note with only frontmatter/whitespace
    note = Note(
        path="empty.md",
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

    # Should handle gracefully (might use title or create zero vector)
    session = Session(datetime(2023, 6, 15), db_with_notes, computer=mock_embedding_computer)
    session.compute_embeddings([note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)


def test_embedding_persistence_mock(db_with_notes, mock_embedding_computer):
    """Test that embeddings persist across session reloads (AC-2.15)."""
    note = Note(
        path="persist.md",
        title="Persistence Test",
        content="Testing embedding persistence across sessions.",
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

    # Compute embeddings
    session1 = Session(datetime(2023, 6, 15), db_with_notes, computer=mock_embedding_computer)
    session1.compute_embeddings([note])
    embedding1 = session1.get_embedding(note.path)

    # Create new session object (simulates reload)
    session2 = Session(datetime(2023, 6, 15), db_with_notes, computer=mock_embedding_computer)
    embedding2 = session2.get_embedding(note.path)

    # Embeddings should be identical
    assert embedding2 is not None
    assert embedding1 is not None
    assert np.array_equal(embedding1, embedding2)


def test_semantic_cache_hit(db_with_notes, mock_embedding_computer):
    """Test that semantic embeddings are cached and reused."""
    note = Note(
        path="cache_test.md",
        title="Cache Test",
        content="Testing semantic embedding caching.",
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

    # First computation - cache miss
    session1 = Session(datetime(2023, 6, 15), db_with_notes, computer=mock_embedding_computer)
    session1.compute_embeddings([note])

    # Verify cache entry exists
    cursor = db_with_notes.execute(
        "SELECT COUNT(*) FROM embeddings WHERE note_path = ?", (note.path,)
    )
    count = cursor.fetchone()[0]
    assert count == 1

    # Second computation with same note - should use cache
    session2 = Session(datetime(2023, 6, 16), db_with_notes, computer=mock_embedding_computer)
    cached_embedding = session2._get_cached_semantic_embedding(note)
    assert cached_embedding is not None
    assert cached_embedding.shape == (384,)
