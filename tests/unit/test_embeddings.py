"""Tests for embeddings module."""

from datetime import datetime, timedelta

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


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def shared_session_with_embeddings(sample_notes):
    """Pre-computed embeddings shared across all tests in module.

    This fixture computes embeddings ONCE for the entire test module,
    then reuses them across all tests that only need to read/query embeddings.
    This dramatically reduces process spawning and test execution time.
    """
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

    # Create session and compute embeddings ONCE for entire module
    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings(sample_notes)

    yield session

    db.close()


@pytest.fixture
def isolated_session(sample_notes):
    """Isolated session for tests that need to test computation behavior.

    Use this fixture for tests that specifically test:
    - Session creation
    - Embedding computation process
    - Vault state hashing
    - Session reuse logic
    """
    db = init_db()

    # Insert notes into database
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


def test_embedding_computer_initialization():
    """Test EmbeddingComputer initialization."""
    computer = EmbeddingComputer()
    assert computer.model_name == "all-MiniLM-L6-v2"
    assert computer._model is None  # Lazy loading


def test_compute_semantic_embedding():
    """Test semantic embedding computation."""
    computer = EmbeddingComputer()
    text = "This is a test sentence."

    embedding = computer.compute_semantic(text)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (384,)  # all-MiniLM-L6-v2 produces 384-dim embeddings


def test_compute_temporal_features(sample_notes):
    """Test temporal features computation."""
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


def test_compute_temporal_embedding(sample_notes):
    """Test combined temporal embedding computation."""
    computer = EmbeddingComputer()
    note = sample_notes[0]
    session_date = datetime(2023, 6, 15)

    embedding = computer.compute_temporal_embedding(note, session_date)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (387,)  # 384 semantic + 3 temporal


def test_session_creation(isolated_session):
    """Test session creation and retrieval."""
    db = isolated_session
    date = datetime(2023, 6, 15)

    session = Session(date, db)

    assert session.date == date
    assert session.session_id > 0
    assert session.db is db

    # Verify session was stored in database
    cursor = db.execute("SELECT date FROM sessions WHERE session_id = ?", (session.session_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "2023-06-15"


def test_session_reuse(isolated_session):
    """Test that sessions with same date are reused."""
    db = isolated_session
    date = datetime(2023, 6, 15)

    session1 = Session(date, db)
    session2 = Session(date, db)

    assert session1.session_id == session2.session_id


def test_compute_vault_state_hash(isolated_session, sample_notes):
    """Test vault state hash computation."""
    db = isolated_session
    session = Session(datetime(2023, 6, 15), db)

    hash1 = session.compute_vault_state_hash(sample_notes)
    hash2 = session.compute_vault_state_hash(sample_notes)

    # Same notes should produce same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64 hex characters

    # Different notes should produce different hash
    modified_notes = sample_notes[:2]
    hash3 = session.compute_vault_state_hash(modified_notes)
    assert hash1 != hash3


def test_compute_embeddings(isolated_session, sample_notes):
    """Test embedding computation for all notes."""
    db = isolated_session

    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings(sample_notes)

    # Verify embeddings were stored
    cursor = db.execute(
        "SELECT COUNT(*) FROM session_embeddings WHERE session_id = ?",
        (session.session_id,),
    )
    count = cursor.fetchone()[0]
    assert count == len(sample_notes)

    # Verify we can retrieve embeddings
    for note in sample_notes:
        embedding = session.get_embedding(note.path)
        assert embedding is not None
        assert embedding.shape == (387,)


def test_get_all_embeddings(shared_session_with_embeddings, sample_notes):
    """Test retrieving all embeddings for a session."""
    embeddings = shared_session_with_embeddings.get_all_embeddings()

    assert len(embeddings) == len(sample_notes)
    for note in sample_notes:
        assert note.path in embeddings
        assert embeddings[note.path].shape == (387,)


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


def test_find_similar_notes():
    """Test finding similar notes."""
    embeddings = {
        "note1.md": np.array([1.0, 0.0, 0.0]),
        "note2.md": np.array([0.9, 0.1, 0.0]),
        "note3.md": np.array([0.0, 1.0, 0.0]),
        "note4.md": np.array([0.0, 0.0, 1.0]),
    }

    query = np.array([1.0, 0.0, 0.0])

    # Find 2 most similar notes
    results = find_similar_notes(query, embeddings, k=2)

    assert len(results) == 2
    assert results[0][0] == "note1.md"  # Exact match
    assert results[1][0] == "note2.md"  # Close match

    # Test with exclusion
    results = find_similar_notes(query, embeddings, k=2, exclude_paths={"note1.md"})

    assert len(results) == 2
    assert results[0][0] == "note2.md"
    assert "note1.md" not in [r[0] for r in results]


def test_semantic_similarity(shared_session_with_embeddings):
    """Test that semantically similar notes have similar embeddings."""
    embeddings = shared_session_with_embeddings.get_all_embeddings()

    # AI notes (note1 and note2) should be more similar to each other
    # than to the cooking note (note3)
    sim_ai = cosine_similarity(embeddings["note1.md"], embeddings["note2.md"])
    sim_cooking = cosine_similarity(embeddings["note1.md"], embeddings["note3.md"])

    assert sim_ai > sim_cooking


def test_embed_very_long_note(isolated_session) -> None:
    """Test handling of very long notes (AC-2.7)."""
    db = isolated_session

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

    # Should not crash, might truncate
    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings([note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)


def test_empty_embedding_handling(isolated_session) -> None:
    """Test handling of notes with minimal/empty content (AC-2.14)."""
    db = isolated_session

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

    # Should handle gracefully (might use title or create zero vector)
    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings([note])

    embedding = session.get_embedding(note.path)
    assert embedding is not None
    assert embedding.shape == (387,)


def test_embedding_persistence(isolated_session) -> None:
    """Test that embeddings persist across session reloads (AC-2.15)."""
    db = isolated_session

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

    # Compute embeddings
    session1 = Session(datetime(2023, 6, 15), db)
    session1.compute_embeddings([note])
    embedding1 = session1.get_embedding(note.path)

    # Create new session object (simulates reload)
    session2 = Session(datetime(2023, 6, 15), db)
    embedding2 = session2.get_embedding(note.path)

    # Embeddings should be identical
    assert embedding2 is not None
    assert embedding1 is not None
    assert np.array_equal(embedding1, embedding2)
