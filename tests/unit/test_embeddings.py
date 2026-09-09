"""Unit tests for embeddings module (mocked models)."""

from datetime import datetime

import numpy as np
import pytest

from geistfabrik.embeddings import (
    EmbeddingComputer,
    Session,
    _bundled_model_path,
    cosine_similarity,
    find_similar_notes,
)
from geistfabrik.models import Note
from geistfabrik.schema import init_db
from tests.stubs import SentenceTransformerStub

# Add 5 second timeout to ALL tests to prevent hangs
pytestmark = pytest.mark.timeout(5)


@pytest.fixture(scope="module")
def module_scoped_default_model() -> object:
    """Exercise fast-model stubbing before module-scoped fixtures initialize."""
    return EmbeddingComputer().model


def test_fast_model_stub_applies_to_module_scoped_fixtures(
    module_scoped_default_model: object,
) -> None:
    assert isinstance(module_scoped_default_model, SentenceTransformerStub)


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
    """Test EmbeddingComputer initialisation."""
    computer = EmbeddingComputer()
    assert computer.model_name == "all-MiniLM-L6-v2"
    assert computer._model is None  # Lazy loading


def test_embedding_computer_with_injected_model(mock_sentence_transformer):
    """Test EmbeddingComputer with pre-injected model (for testing)."""
    computer = EmbeddingComputer(model=mock_sentence_transformer)
    assert computer._model is mock_sentence_transformer
    assert computer._model is not None  # Model already injected


def test_sentence_transformer_stub_matches_production_calls(tmp_path):
    """The test double accepts the constructor and encode arguments production uses."""
    model = SentenceTransformerStub(tmp_path, device="cpu", local_files_only=True)
    single = model.encode("one", convert_to_numpy=True)
    batch = model.encode(
        ["one", "two"], convert_to_numpy=True, show_progress_bar=False, batch_size=2
    )

    assert model.local_files_only is True
    assert single.shape == (384,)
    assert batch.shape == (2, 384)


def _write_test_model(model_path, *, lfs_pointer=False):
    """Create the minimal runtime files expected by the bundled-model resolver."""
    required = [
        "config.json",
        "config_sentence_transformers.json",
        "model.safetensors",
        "modules.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.txt",
        "1_Pooling/config.json",
    ]
    for relative_path in required:
        target = model_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
    weights = model_path / "model.safetensors"
    if lfs_pointer:
        weights.write_text("version https://git-lfs.github.com/spec/v1\n")
    else:
        weights.write_bytes(b"weights" * 200)


def test_bundled_model_resolves_importlib_resource(
    tmp_path, monkeypatch, preserve_model_path_validation
):
    """Installed-package resources take precedence over repository layout."""
    model_name = "test-resource-model"
    model_path = tmp_path / model_name
    _write_test_model(model_path)
    monkeypatch.setattr("geistfabrik.embeddings.resources.files", lambda package: tmp_path)

    assert _bundled_model_path(model_name) == model_path


def test_bundled_model_rejects_lfs_pointer(tmp_path, monkeypatch, preserve_model_path_validation):
    """A source distribution containing only an LFS pointer is not loadable."""
    model_name = "test-lfs-pointer-model"
    model_path = tmp_path / model_name
    _write_test_model(model_path, lfs_pointer=True)
    monkeypatch.setattr("geistfabrik.embeddings.resources.files", lambda package: tmp_path)

    assert _bundled_model_path(model_name) is None


def test_offline_missing_model_fails_without_constructor(
    tmp_path, monkeypatch, preserve_model_path_validation
):
    """Offline mode never falls through to a HuggingFace identifier."""
    monkeypatch.setattr("geistfabrik.embeddings.resources.files", lambda package: tmp_path)
    monkeypatch.setenv("GEISTFABRIK_OFFLINE", "1")
    computer = EmbeddingComputer(model_name="definitely-missing-test-model")

    with pytest.raises(RuntimeError, match="no usable bundled model resource"):
        _ = computer.model


def test_online_missing_model_uses_huggingface_fallback(
    tmp_path, monkeypatch, preserve_model_path_validation
):
    """Online mode preserves the established model-name fallback."""
    monkeypatch.setattr("geistfabrik.embeddings.resources.files", lambda package: tmp_path)
    monkeypatch.delenv("GEISTFABRIK_OFFLINE", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    computer = EmbeddingComputer(model_name="remote-test-model")

    model = computer.model

    assert isinstance(model, SentenceTransformerStub)
    assert model.model_name_or_path == "remote-test-model"
    assert model.local_files_only is False


def test_fast_constructor_stub_does_not_require_materialized_weights(tmp_path, monkeypatch):
    """Fast CI injection reaches the stub without reading an LFS model file."""
    unresolved = tmp_path / "unmaterialized-model"
    monkeypatch.setattr("geistfabrik.embeddings._bundled_model_path", lambda _name: unresolved)
    computer = EmbeddingComputer()
    assert isinstance(computer.model, SentenceTransformerStub)
    assert computer.model.model_name_or_path == str(unresolved)


def test_compute_semantic_embedding_mock(mock_embedding_computer):
    """Test semantic embedding computation with mocked model."""
    text = "This is a test sentence."

    embedding = mock_embedding_computer.compute_semantic(text)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (384,)  # all-MiniLM-L6-v2 produces 384-dim embeddings

    # Verify deterministic behaviour - same text produces same embedding
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
    results = find_similar_notes(query, fixed_embeddings, count=2)

    assert len(results) == 2
    assert results[0][0] == "note1.md"  # Exact match
    assert results[1][0] == "note2.md"  # Close match

    # Test with exclusion
    results = find_similar_notes(query, fixed_embeddings, count=2, exclude_paths={"note1.md"})

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


def test_session_embedding_retention_prunes_old_sessions(
    db_with_notes, mock_embedding_computer, sample_notes
):
    """Sessions beyond the retention window have their embeddings pruned."""
    retention = 2
    dates = [datetime(2023, 1, day) for day in range(1, 7)]  # 6 sessions
    for session_date in dates:
        session = Session(
            session_date,
            db_with_notes,
            computer=mock_embedding_computer,
            embedding_retention=retention,
        )
        session.compute_embeddings(sample_notes)

    # At most `retention` recent sessions plus the current one keep embeddings.
    distinct = db_with_notes.execute(
        "SELECT COUNT(DISTINCT session_id) FROM session_embeddings"
    ).fetchone()[0]
    assert distinct <= retention + 1

    retained = {
        row[0]
        for row in db_with_notes.execute(
            """
            SELECT s.date FROM sessions s
            WHERE EXISTS (
                SELECT 1 FROM session_embeddings se WHERE se.session_id = s.session_id
            )
            """
        ).fetchall()
    }
    assert "2023-01-06" in retained  # newest kept
    assert "2023-01-01" not in retained  # oldest pruned


def test_session_embedding_retention_zero_keeps_all(
    db_with_notes, mock_embedding_computer, sample_notes
):
    """A retention of 0 disables pruning (all sessions keep embeddings)."""
    dates = [datetime(2023, 1, day) for day in range(1, 5)]  # 4 sessions
    for session_date in dates:
        session = Session(
            session_date,
            db_with_notes,
            computer=mock_embedding_computer,
            embedding_retention=0,
        )
        session.compute_embeddings(sample_notes)

    distinct = db_with_notes.execute(
        "SELECT COUNT(DISTINCT session_id) FROM session_embeddings"
    ).fetchone()[0]
    assert distinct == 4


def test_is_offline_mode_respects_env_flags(monkeypatch):
    """is_offline_mode honours GeistFabrik and HuggingFace offline flags."""
    from geistfabrik.embeddings import is_offline_mode

    for var in ("GEISTFABRIK_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.delenv(var, raising=False)
    assert is_offline_mode() is False

    monkeypatch.setenv("GEISTFABRIK_OFFLINE", "1")
    assert is_offline_mode() is True
    monkeypatch.setenv("GEISTFABRIK_OFFLINE", "yes")
    assert is_offline_mode() is True

    monkeypatch.setenv("GEISTFABRIK_OFFLINE", "")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    assert is_offline_mode() is True

    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    assert is_offline_mode() is True
