"""Unit tests for vector search backends."""

import os
import sqlite3
from datetime import datetime

import numpy as np
import pytest

from geistfabrik.embeddings import Session
from geistfabrik.schema import init_db
from geistfabrik.vector_search import InMemoryVectorBackend, SqliteVecBackend

# Check if sqlite-vec is available AND loadable
SQLITE_VEC_AVAILABLE = False
SQLITE_VEC_LOADABLE = False

try:
    import sqlite_vec

    SQLITE_VEC_AVAILABLE = True

    # Check if SQLite supports extension loading
    test_conn = sqlite3.connect(":memory:")
    if hasattr(test_conn, "enable_load_extension"):
        try:
            test_conn.enable_load_extension(True)
            sqlite_vec.load(test_conn)
            test_conn.execute("SELECT vec_version()")
            SQLITE_VEC_LOADABLE = True
        except (sqlite3.OperationalError, AttributeError):
            pass
        finally:
            test_conn.close()
    else:
        test_conn.close()
except ImportError:
    pass

# In CI on Linux, we require sqlite-vec to be fully functional
# macOS runners may not support extension loading, so we allow it to be skipped there
if os.environ.get("CI") and not SQLITE_VEC_LOADABLE:
    import platform

    if platform.system() == "Linux":
        pytest.fail(
            "sqlite-vec is required in CI (Linux) but not loadable. "
            "Run: uv pip install -e '.[vector-search]'"
        )


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    # init_db() creates and returns a connection when db_path is None
    conn = init_db(db_path=None)

    # Load sqlite-vec extension if loadable (needed for SqliteVecBackend tests)
    if SQLITE_VEC_LOADABLE:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)

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


class TestExtensionLoading:
    """Test that sqlite-vec extension can be loaded correctly."""

    def test_sqlite_vec_extension_available(self):
        """Test that sqlite-vec extension is available and can be loaded."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not installed")

        # Create fresh database and test extension loading
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)

        # Load extension
        sqlite_vec.load(conn)

        # Verify extension is loaded by calling vec_version()
        result = conn.execute("SELECT vec_version()").fetchone()
        assert result is not None
        assert len(result[0]) > 0  # Version string should be non-empty

        conn.close()

    def test_sqlite_vec_extension_in_test_fixture(self, db):
        """Test that our db fixture correctly loads sqlite-vec."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not installed")

        # Should be able to call vec_version() on fixture db
        result = db.execute("SELECT vec_version()").fetchone()
        assert result is not None


class TestKnownAnswerCosineDistance:
    """Test backends produce correct cosine similarity values for known cases.

    These tests verify that both backends correctly implement cosine distance,
    catching bugs like using L2 distance instead of cosine distance.
    """

    def test_inmemory_orthogonal_vectors_zero_similarity(self, db):
        """Test that orthogonal vectors have zero cosine similarity (InMemory)."""
        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create notes
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("a.md", "a", "test", now, now, 0.0),
        )
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("b.md", "b", "test", now, now, 0.0),
        )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create orthogonal vectors [1,0,0] and [0,1,0]
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "a.md", vec_a.tobytes()),
        )
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "b.md", vec_b.tobytes()),
        )
        db.commit()

        # Load and test
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(session_date)

        similarity = backend.get_similarity("a.md", "b.md")
        assert abs(similarity - 0.0) < 1e-6, f"Expected 0.0, got {similarity}"

    def test_inmemory_identical_vectors_one_similarity(self, db):
        """Test that identical vectors have cosine similarity of 1.0 (InMemory)."""
        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create notes
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("a.md", "a", "test", now, now, 0.0),
        )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create identical vector
        vec_a = np.array([0.6, 0.8, 0.0], dtype=np.float32)

        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "a.md", vec_a.tobytes()),
        )
        db.commit()

        # Load and test
        backend = InMemoryVectorBackend(db)
        backend.load_embeddings(session_date)

        similarity = backend.get_similarity("a.md", "a.md")
        assert abs(similarity - 1.0) < 1e-6, f"Expected 1.0, got {similarity}"

    def test_sqlitevec_orthogonal_vectors_zero_similarity(self, db):
        """Test that orthogonal vectors have zero cosine similarity (SqliteVec)."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not installed")

        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create notes
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("a.md", "a", "test", now, now, 0.0),
        )
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("b.md", "b", "test", now, now, 0.0),
        )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create orthogonal vectors [1,0,0] and [0,1,0]
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "a.md", vec_a.tobytes()),
        )
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "b.md", vec_b.tobytes()),
        )
        db.commit()

        # Load and test
        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(session_date)

        similarity = backend.get_similarity("a.md", "b.md")
        assert abs(similarity - 0.0) < 1e-6, f"Expected 0.0, got {similarity}"

    def test_sqlitevec_identical_vectors_one_similarity(self, db):
        """Test that identical vectors have cosine similarity of 1.0 (SqliteVec)."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not installed")

        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create notes
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("a.md", "a", "test", now, now, 0.0),
        )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create identical vector
        vec_a = np.array([0.6, 0.8, 0.0], dtype=np.float32)

        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "a.md", vec_a.tobytes()),
        )
        db.commit()

        # Load and test
        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(session_date)

        similarity = backend.get_similarity("a.md", "a.md")
        assert abs(similarity - 1.0) < 1e-6, f"Expected 1.0, got {similarity}"

    def test_sqlitevec_opposite_vectors_negative_one_similarity(self, db):
        """Test that opposite vectors have cosine similarity of -1.0 (SqliteVec)."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not installed")

        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create notes
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("a.md", "a", "test", now, now, 0.0),
        )
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("b.md", "b", "test", now, now, 0.0),
        )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create opposite vectors [1,0,0] and [-1,0,0]
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([-1.0, 0.0, 0.0], dtype=np.float32)

        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "a.md", vec_a.tobytes()),
        )
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "b.md", vec_b.tobytes()),
        )
        db.commit()

        # Load and test
        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(session_date)

        similarity = backend.get_similarity("a.md", "b.md")
        assert abs(similarity - (-1.0)) < 1e-6, f"Expected -1.0, got {similarity}"


class TestInMemoryVectorBackend:
    """Test suite for InMemoryVectorBackend."""

    def test_initialization(self, db):
        """Test backend initialisation."""
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
        """Test backend behaviour with empty vault."""
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
        """Test backend initialisation."""
        # Skip if sqlite-vec not available
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        assert backend.db == db
        assert backend.session_id == 0
        assert backend._path_to_id == {}
        assert backend._id_to_path == {}

    def test_initialization_raises_without_sqlite_vec(self, db):
        """Test that initialisation raises RuntimeError without sqlite-vec."""
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
                SqliteVecBackend(db, dim=3)

    def test_load_embeddings(self, db, sample_embeddings):
        """Test loading embeddings into vec_search table."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
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
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings("2099-12-31")

        assert backend.session_id == 0
        assert backend._path_to_id == {}
        assert backend._id_to_path == {}

    def test_find_similar_returns_correct_count(self, db, sample_embeddings):
        """Test that find_similar returns the requested number of results."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=2)

        assert len(results) == 2

    def test_find_similar_sorted_ascending_distance(self, db, sample_embeddings):
        """Test that results are sorted by distance (ascending)."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=4)

        # Results should be sorted by similarity descending (distance ascending)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_find_similar_correct_results(self, db, sample_embeddings):
        """Test that find_similar returns the most similar notes."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        # Query with [1, 0, 0] should be most similar to note1, then note2
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = backend.find_similar(query, k=2)

        assert results[0][0] == "note1.md"  # Most similar
        assert results[0][1] > 0.99  # Almost identical
        assert results[1][0] == "note2.md"  # Second most similar

    def test_get_similarity_symmetric(self, db, sample_embeddings):
        """Test that similarity(A, B) == similarity(B, A)."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim_ab = backend.get_similarity("note1.md", "note2.md")
        sim_ba = backend.get_similarity("note2.md", "note1.md")

        assert abs(sim_ab - sim_ba) < 1e-6

    def test_get_similarity_self_is_one(self, db, sample_embeddings):
        """Test that similarity(A, A) == 1.0."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim = backend.get_similarity("note1.md", "note1.md")

        assert abs(sim - 1.0) < 1e-6

    def test_get_similarity_orthogonal_is_zero(self, db, sample_embeddings):
        """Test that orthogonal vectors have similarity ~0."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        sim = backend.get_similarity("note1.md", "note3.md")

        assert abs(sim) < 1e-6

    def test_get_similarity_raises_keyerror_for_missing_note(self, db, sample_embeddings):
        """Test that get_similarity raises KeyError for missing notes."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        with pytest.raises(KeyError, match="Note not found"):
            backend.get_similarity("note1.md", "missing.md")

    def test_get_embedding(self, db, sample_embeddings):
        """Test getting an embedding for a note."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        embedding = backend.get_embedding("note1.md")

        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 3
        assert np.allclose(embedding, [1.0, 0.0, 0.0])

    def test_get_embedding_raises_keyerror_for_missing_note(self, db, sample_embeddings):
        """Test that get_embedding raises KeyError for missing notes."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        with pytest.raises(KeyError, match="Note not found"):
            backend.get_embedding("missing.md")

    def test_path_mapping_caching(self, db, sample_embeddings):
        """Test that path mappings are cached properly."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)
        backend.load_embeddings(sample_embeddings["session_date"])

        # First access should populate cache
        vec_id1 = backend._get_or_create_vec_id("note1.md")
        assert "note1.md" in backend._path_to_id
        assert vec_id1 in backend._id_to_path

        # Second access should use cache (no DB query)
        vec_id2 = backend._get_or_create_vec_id("note1.md")
        assert vec_id1 == vec_id2

    def test_empty_vault(self, db):
        """Test backend behaviour with empty vault."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        backend = SqliteVecBackend(db, dim=3)

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
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db, dim=3)

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
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db, dim=3)

        in_memory.load_embeddings(sample_embeddings["session_date"])
        sqlite_vec.load_embeddings(sample_embeddings["session_date"])

        sim_mem = in_memory.get_similarity("note1.md", "note2.md")
        sim_vec = sqlite_vec.get_similarity("note1.md", "note2.md")

        assert abs(sim_mem - sim_vec) < 1e-5

    def test_backends_return_same_embeddings(self, db, sample_embeddings):
        """Test that both backends return the same embeddings."""
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db, dim=3)

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
        if not SQLITE_VEC_LOADABLE:
            pytest.skip("sqlite-vec not loadable")

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


class TestBackendIntegration:
    """Integration tests that use both backends in realistic scenarios.

    These tests always run (never skip) and verify that both backends work
    correctly in the context of typical vault operations.
    """

    def test_both_backends_can_load_and_query_basic_vault(self, db):
        """Test that both backends work with a basic vault setup."""
        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create a small realistic vault
        notes = [
            ("Projects/AI Research.md", "AI Research", "Research on embeddings and vector search"),
            (
                "Notes/Machine Learning.md",
                "Machine Learning",
                "ML is about training models on data",
            ),
            ("Ideas/New Project.md", "New Project", "Ideas for combining AI with writing"),
            ("Daily/2025-01-15.md", "2025-01-15", "Today I learned about vector databases"),
        ]

        for path, title, content in notes:
            db.execute(
                "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (path, title, content, now, now, 0.0),
            )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create embeddings (synthetic but realistic dimensions)
        embeddings = {
            "Projects/AI Research.md": np.random.randn(387).astype(np.float32),
            "Notes/Machine Learning.md": np.random.randn(387).astype(np.float32),
            "Ideas/New Project.md": np.random.randn(387).astype(np.float32),
            "Daily/2025-01-15.md": np.random.randn(387).astype(np.float32),
        }

        # Normalise embeddings
        for path in embeddings:
            embeddings[path] = embeddings[path] / np.linalg.norm(embeddings[path])

        for path, embedding in embeddings.items():
            db.execute(
                "INSERT INTO session_embeddings (session_id, note_path, embedding) "
                "VALUES (?, ?, ?)",
                (session_id, path, embedding.tobytes()),
            )
        db.commit()

        # Test InMemoryVectorBackend
        backend_mem = InMemoryVectorBackend(db)
        backend_mem.load_embeddings(session_date)

        # Should have loaded all 4 embeddings
        assert len(backend_mem.embeddings) == 4

        # Should be able to find similar notes
        query = embeddings["Projects/AI Research.md"]
        results = backend_mem.find_similar(query, k=3)
        assert len(results) == 3
        # First result should be the query itself
        assert results[0][0] == "Projects/AI Research.md"
        assert results[0][1] > 0.99  # Very high similarity to itself

        # Test SqliteVecBackend (if available)
        if SQLITE_VEC_LOADABLE:
            backend_vec = SqliteVecBackend(db, dim=387)
            backend_vec.load_embeddings(session_date)

            # Should have loaded all 4 embeddings into vec_search
            count = db.execute("SELECT COUNT(*) FROM vec_search").fetchone()[0]
            assert count == 4

            # Should get same results as InMemory
            results_vec = backend_vec.find_similar(query, k=3)
            assert len(results_vec) == 3
            # First result should be the query itself
            assert results_vec[0][0] == "Projects/AI Research.md"
            # Similarity should be very close to InMemory result
            assert abs(results_vec[0][1] - results[0][1]) < 0.01

    def test_backend_similarity_on_real_semantic_relationships(self, db):
        """Test that backends correctly compute similarities for semantically related notes."""
        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create notes with clear semantic relationships
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("python.md", "Python", "test", now, now, 0.0),
        )
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("javascript.md", "JavaScript", "test", now, now, 0.0),
        )
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("cooking.md", "Cooking", "test", now, now, 0.0),
        )

        # Create session
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        session_id = db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
        ).fetchone()[0]

        # Create embeddings where Python/JS are similar, Cooking is different
        # (simulating real semantic embeddings)
        vec_python = np.array([1.0, 0.5, 0.0], dtype=np.float32)
        vec_js = np.array([0.9, 0.4, 0.1], dtype=np.float32)  # Similar to Python
        vec_cooking = np.array([0.0, 0.1, 1.0], dtype=np.float32)  # Different

        # Normalise
        vec_python = vec_python / np.linalg.norm(vec_python)
        vec_js = vec_js / np.linalg.norm(vec_js)
        vec_cooking = vec_cooking / np.linalg.norm(vec_cooking)

        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "python.md", vec_python.tobytes()),
        )
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "javascript.md", vec_js.tobytes()),
        )
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, "cooking.md", vec_cooking.tobytes()),
        )
        db.commit()

        # Test with InMemoryVectorBackend
        backend_mem = InMemoryVectorBackend(db)
        backend_mem.load_embeddings(session_date)

        # Python should be more similar to JS than to Cooking
        sim_python_js = backend_mem.get_similarity("python.md", "javascript.md")
        sim_python_cooking = backend_mem.get_similarity("python.md", "cooking.md")
        assert sim_python_js > sim_python_cooking
        assert sim_python_js > 0.8  # High similarity

        # Test with SqliteVecBackend (if available)
        if SQLITE_VEC_LOADABLE:
            backend_vec = SqliteVecBackend(db, dim=3)
            backend_vec.load_embeddings(session_date)

            # Should get same relative ordering
            sim_python_js_vec = backend_vec.get_similarity("python.md", "javascript.md")
            sim_python_cooking_vec = backend_vec.get_similarity("python.md", "cooking.md")

            assert sim_python_js_vec > sim_python_cooking_vec
            # Should match InMemory results closely
            assert abs(sim_python_js_vec - sim_python_js) < 0.01
            assert abs(sim_python_cooking_vec - sim_python_cooking) < 0.01

    def test_backends_handle_empty_results_identically(self, db):
        """Test that both backends handle queries with no results the same way."""
        session_date = "2025-01-15"
        now = datetime.now().isoformat()

        # Create empty session (no embeddings)
        db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, now))
        db.commit()

        # Test InMemoryVectorBackend
        backend_mem = InMemoryVectorBackend(db)
        backend_mem.load_embeddings(session_date)

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results_mem = backend_mem.find_similar(query, k=10)
        assert results_mem == []

        # Test SqliteVecBackend (if available)
        if SQLITE_VEC_LOADABLE:
            backend_vec = SqliteVecBackend(db, dim=3)
            backend_vec.load_embeddings(session_date)

            results_vec = backend_vec.find_similar(query, k=10)
            assert results_vec == []
