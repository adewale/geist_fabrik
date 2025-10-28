"""Unit tests for vector search backends."""

from datetime import datetime

import numpy as np
import pytest

from geistfabrik.embeddings import Session
from geistfabrik.schema import init_db
from geistfabrik.vector_search import InMemoryVectorBackend, SqliteVecBackend


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    # init_db() creates and returns a connection when db_path is None
    conn = init_db(db_path=None)
    return conn


@pytest.fixture
def sample_embeddings(db):
    """Create sample embeddings for testing.

    Returns a dict mapping (session_date, note_path) to embedding.
    """
    session_date = "2025-01-15"
    now = datetime.now().isoformat()

    # Create notes first (required by foreign key constraint)
    note_paths = ["note1.md", "note2.md", "note3.md", "note4.md"]
    for path in note_paths:
        db.execute(
            """
            INSERT INTO notes (path, title, content, created, modified, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (path, path.replace(".md", ""), "Test content", now, now, 0.0),
        )

    # Create session
    db.execute(
        "INSERT INTO sessions (date, created_at) VALUES (?, ?)",
        (session_date, now),
    )
    session_id = db.execute(
        "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
    ).fetchone()[0]

    # Create sample embeddings (3-dimensional for testing)
    embeddings_data = {
        "note1.md": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "note2.md": np.array([0.8, 0.6, 0.0], dtype=np.float32),  # Similar to note1
        "note3.md": np.array([0.0, 1.0, 0.0], dtype=np.float32),  # Orthogonal to note1
        "note4.md": np.array([0.0, 0.0, 1.0], dtype=np.float32),  # Orthogonal to note1 & note3
    }

    # Insert embeddings
    for path, embedding in embeddings_data.items():
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, path, embedding.tobytes()),
        )

    db.commit()

    return {
        "session_date": session_date,
        "session_id": session_id,
        "embeddings": embeddings_data,
    }


class TestInMemoryVectorBackend:
    """Test suite for InMemoryVectorBackend."""

    def test_initialization(self, db):
        """Test backend initialization."""
        backend = InMemoryVectorBackend(db)
        assert backend.db == db
        assert backend.embeddings == {}
        assert backend.session_id == 0

    def test_load_embeddings(self, db, sample_embeddings):
        """Test loading embeddings into memory."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        assert len(backend.embeddings) == 4
        assert "note1.md" in backend.embeddings
        assert "note2.md" in backend.embeddings
        assert "note3.md" in backend.embeddings
        assert "note4.md" in backend.embeddings

    def test_load_embeddings_nonexistent_session(self, db):
        """Test loading embeddings for a session that doesn't exist."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings("2099-12-31")

        assert backend.embeddings == {}
        assert backend.session_id == 0

    def test_find_similar_returns_correct_count(self, db, sample_embeddings):
        """Test that find_similar returns the requested number of results."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=2)

        assert len(results) == 2

    def test_find_similar_sorted_descending(self, db, sample_embeddings):
        """Test that results are sorted by similarity (descending)."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=4)

        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_find_similar_correct_results(self, db, sample_embeddings):
        """Test that find_similar returns the most similar notes."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        # Query with [1, 0, 0] should be most similar to note1, then note2
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=2)

        assert results[0][0] == "note1.md"  # Most similar
        assert results[0][1] > 0.99  # Almost identical
        assert results[1][0] == "note2.md"  # Second most similar

    def test_get_similarity_symmetric(self, db, sample_embeddings):
        """Test that similarity(A, B) == similarity(B, A)."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim_ab = backend.get_similarity("note1.md", "note2.md")
        sim_ba = backend.get_similarity("note2.md", "note1.md")

        assert abs(sim_ab - sim_ba) < 1e-6

    def test_get_similarity_self_is_one(self, db, sample_embeddings):
        """Test that similarity(A, A) == 1.0."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim = backend.get_similarity("note1.md", "note1.md")

        assert abs(sim - 1.0) < 1e-6

    def test_get_similarity_orthogonal_is_zero(self, db, sample_embeddings):
        """Test that orthogonal vectors have similarity ~0."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim = backend.get_similarity("note1.md", "note3.md")

        assert abs(sim) < 1e-6

    def test_get_similarity_raises_keyerror_for_missing_note(self, db, sample_embeddings):
        """Test that get_similarity raises KeyError for missing notes."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        with pytest.raises(KeyError, match="Note not found: missing.md"):
            backend.get_similarity("note1.md", "missing.md")

    def test_get_embedding(self, db, sample_embeddings):
        """Test getting an embedding for a note."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        embedding = backend.get_embedding("note1.md")

        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 3
        assert np.allclose(embedding, [1.0, 0.0, 0.0])

    def test_get_embedding_raises_keyerror_for_missing_note(self, db, sample_embeddings):
        """Test that get_embedding raises KeyError for missing notes."""
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        with pytest.raises(KeyError, match="Note not found: missing.md"):
            backend.get_embedding("missing.md")

    def test_empty_vault(self, db):
        """Test backend behavior with empty vault."""
        backend = InMemoryVectorBackend(db)

        # Create empty session
        session_date = "2025-01-15"
        db.execute(
            "INSERT INTO sessions (date, created_at) VALUES (?, ?)",
            (session_date, datetime.now().isoformat()),
        )
        db.commit()

        backend.load_embeddings(session_date)

        assert backend.embeddings == {}

        # find_similar should return empty list
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=10)
        assert results == []


class TestSqliteVecBackend:
    """Test suite for SqliteVecBackend."""

    def test_initialization(self, db):
        """Test backend initialization."""
        # Skip if sqlite-vec not available
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        assert backend.db == db
        assert backend.session_id == 0
        assert backend._path_to_id == {}
        assert backend._id_to_path == {}

    def test_initialization_raises_without_sqlite_vec(self, db):
        """Test that initialization raises RuntimeError without sqlite-vec."""
        # Mock sqlite-vec not available by patching the version check
        # This test only makes sense if sqlite-vec is actually installed
        # So we skip it if sqlite-vec is not installed
        try:
            import sqlite_vec  # noqa: F401

            # sqlite-vec is installed, can't test this case
            pytest.skip("sqlite-vec is installed, can't test missing dependency")
        except ImportError:
            # sqlite-vec not installed, should raise RuntimeError
            with pytest.raises(RuntimeError, match="sqlite-vec extension not available"):
                SqliteVecBackend(db)

    def test_load_embeddings(self, db, sample_embeddings):
        """Test loading embeddings into vec_search table."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        # Check that path mappings were created
        assert len(backend._path_to_id) == 4
        assert "note1.md" in backend._path_to_id
        assert "note2.md" in backend._path_to_id

        # Check that embeddings were inserted into vec_search
        cursor = db.execute("SELECT COUNT(*) FROM vec_search")
        count = cursor.fetchone()[0]
        assert count == 4

    def test_load_embeddings_nonexistent_session(self, db):
        """Test loading embeddings for a session that doesn't exist."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings("2099-12-31")

        assert backend.session_id == 0
        assert backend._path_to_id == {}
        assert backend._id_to_path == {}

    def test_find_similar_returns_correct_count(self, db, sample_embeddings):
        """Test that find_similar returns the requested number of results."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=2)

        assert len(results) == 2

    def test_find_similar_sorted_ascending_distance(self, db, sample_embeddings):
        """Test that results are sorted by distance (ascending)."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=4)

        # Results should be sorted by similarity descending (distance ascending)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_find_similar_correct_results(self, db, sample_embeddings):
        """Test that find_similar returns the most similar notes."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        # Query with [1, 0, 0] should be most similar to note1, then note2
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=2)

        assert results[0][0] == "note1.md"  # Most similar
        assert results[0][1] > 0.99  # Almost identical
        assert results[1][0] == "note2.md"  # Second most similar

    def test_get_similarity_symmetric(self, db, sample_embeddings):
        """Test that similarity(A, B) == similarity(B, A)."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim_ab = backend.get_similarity("note1.md", "note2.md")
        sim_ba = backend.get_similarity("note2.md", "note1.md")

        assert abs(sim_ab - sim_ba) < 1e-6

    def test_get_similarity_self_is_one(self, db, sample_embeddings):
        """Test that similarity(A, A) == 1.0."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim = backend.get_similarity("note1.md", "note1.md")

        assert abs(sim - 1.0) < 1e-6

    def test_get_similarity_orthogonal_is_zero(self, db, sample_embeddings):
        """Test that orthogonal vectors have similarity ~0."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim = backend.get_similarity("note1.md", "note3.md")

        assert abs(sim) < 1e-6

    def test_get_similarity_raises_keyerror_for_missing_note(self, db, sample_embeddings):
        """Test that get_similarity raises KeyError for missing notes."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        with pytest.raises(KeyError, match="Note not found"):
            backend.get_similarity("note1.md", "missing.md")

    def test_get_embedding(self, db, sample_embeddings):
        """Test getting an embedding for a note."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        embedding = backend.get_embedding("note1.md")

        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 3
        assert np.allclose(embedding, [1.0, 0.0, 0.0])

    def test_get_embedding_raises_keyerror_for_missing_note(self, db, sample_embeddings):
        """Test that get_embedding raises KeyError for missing notes."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        with pytest.raises(KeyError, match="Note not found"):
            backend.get_embedding("missing.md")

    def test_path_mapping_caching(self, db, sample_embeddings):
        """Test that path mappings are cached properly."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)
        backend.load_embeddings(sample_embeddings["session_date"])

        # First access should populate cache
        vec_id1 = backend._get_or_create_vec_id("note1.md")
        assert "note1.md" in backend._path_to_id
        assert vec_id1 in backend._id_to_path

        # Second access should use cache (no DB query)
        vec_id2 = backend._get_or_create_vec_id("note1.md")
        assert vec_id1 == vec_id2

    def test_empty_vault(self, db):
        """Test backend behavior with empty vault."""
        pytest.importorskip("sqlite_vec")

        backend = SqliteVecBackend(db)

        # Create empty session
        session_date = "2025-01-15"
        db.execute(
            "INSERT INTO sessions (date, created_at) VALUES (?, ?)",
            (session_date, datetime.now().isoformat()),
        )
        db.commit()

        backend.load_embeddings(session_date)

        assert backend._path_to_id == {}
        assert backend._id_to_path == {}

        # find_similar should return empty list
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=10)
        assert results == []


class TestBackendParity:
    """Test parity between InMemory and SqliteVec backends.

    These tests ensure both backends return identical results.
    """

    def test_backends_return_same_similar_notes(self, db, sample_embeddings):
        """Test that both backends return the same similar notes."""
        pytest.importorskip("sqlite_vec")

        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db)

        in_memory.load_embeddings(sample_embeddings["session_date"])
        sqlite_vec.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.5, 0.0], dtype=np.float32)

        results_mem = in_memory.find_similar(query, k=3)
        results_vec = sqlite_vec.find_similar(query, k=3)

        # Should return same paths (order should be identical)
        paths_mem = [path for path, _ in results_mem]
        paths_vec = [path for path, _ in results_vec]
        assert paths_mem == paths_vec

        # Scores should be within epsilon
        for (_, score_m), (_, score_v) in zip(results_mem, results_vec):
            assert abs(score_m - score_v) < 1e-5

    def test_backends_return_same_similarity_scores(self, db, sample_embeddings):
        """Test that both backends return the same similarity scores."""
        pytest.importorskip("sqlite_vec")

        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db)

        in_memory.load_embeddings(sample_embeddings["session_date"])
        sqlite_vec.load_embeddings(sample_embeddings["session_date"])

        sim_mem = in_memory.get_similarity("note1.md", "note2.md")
        sim_vec = sqlite_vec.get_similarity("note1.md", "note2.md")

        assert abs(sim_mem - sim_vec) < 1e-5

    def test_backends_return_same_embeddings(self, db, sample_embeddings):
        """Test that both backends return the same embeddings."""
        pytest.importorskip("sqlite_vec")

        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db)

        in_memory.load_embeddings(sample_embeddings["session_date"])
        sqlite_vec.load_embeddings(sample_embeddings["session_date"])

        emb_mem = in_memory.get_embedding("note1.md")
        emb_vec = sqlite_vec.get_embedding("note1.md")

        assert np.allclose(emb_mem, emb_vec, atol=1e-6)


class TestSessionBackendIntegration:
    """Test integration of backends with Session class."""

    def test_session_creates_in_memory_backend_by_default(self, db):
        """Test that Session creates in-memory backend by default."""
        session = Session(datetime.now(), db)
        backend = session.get_backend()

        assert isinstance(backend, InMemoryVectorBackend)

    def test_session_creates_sqlite_vec_backend_when_configured(self, db):
        """Test that Session creates sqlite-vec backend when configured."""
        pytest.importorskip("sqlite_vec")

        session = Session(datetime.now(), db, backend="sqlite-vec")
        backend = session.get_backend()

        assert isinstance(backend, SqliteVecBackend)

    def test_session_backend_loads_embeddings_lazily(self, db, sample_embeddings):
        """Test that Session backend loads embeddings lazily."""
        session = Session(datetime.strptime(sample_embeddings["session_date"], "%Y-%m-%d"), db)

        # Backend should not be created yet
        assert session._backend is None

        # First access creates and loads backend
        backend = session.get_backend()
        assert session._backend is not None
        assert isinstance(backend, InMemoryVectorBackend)

        # Subsequent accesses return same backend
        backend2 = session.get_backend()
        assert backend is backend2

    def test_session_get_all_embeddings_still_works(self, db, sample_embeddings):
        """Test that deprecated get_all_embeddings() still works for backward compatibility."""
        session = Session(datetime.strptime(sample_embeddings["session_date"], "%Y-%m-%d"), db)
        # Embeddings already exist in the database from fixture

        embeddings = session.get_all_embeddings()

        assert isinstance(embeddings, dict)
        assert len(embeddings) == 4
        assert "note1.md" in embeddings
