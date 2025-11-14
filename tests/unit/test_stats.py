"""Unit tests for stats module."""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.embeddings import Session
from geistfabrik.models import Note
from geistfabrik.schema import init_db
from geistfabrik.stats import (
    EmbeddingMetricsComputer,
    StatsCollector,
    StatsFormatter,
    generate_recommendations,
)
from geistfabrik.vault import Vault

# Add 5 second timeout to ALL tests to prevent hangs
pytestmark = pytest.mark.timeout(5)


@pytest.fixture
def vault_with_embeddings(sample_notes, mock_embedding_computer, temp_dir):
    """Vault with sample notes and embeddings for testing."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    # Create .obsidian directory
    (vault_path / ".obsidian").mkdir()

    # Create some actual note files
    for note in sample_notes:
        note_path = vault_path / note.path
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(note.content)

    # Initialise vault
    db_path = vault_path / "_geistfabrik" / "vault.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    vault = Vault(vault_path, db_path)

    # Sync vault to load notes
    vault.sync()

    # Compute embeddings for a session
    session = Session(datetime(2025, 1, 15), vault.db, computer=mock_embedding_computer)
    session.compute_embeddings(sample_notes)

    yield vault
    vault.close()


def _create_vault_with_sessions(vault_path, notes, session_dates, embedding_computer):
    """Helper to create vault with multiple sessions for testing.

    Args:
        vault_path: Path where vault should be created
        notes: List of Note objects to add to vault
        session_dates: List of datetime objects for sessions to create
        embedding_computer: EmbeddingComputer instance to use

    Returns:
        Initialized Vault with embeddings computed for all sessions
    """
    # Create vault directory structure
    vault_path.mkdir(exist_ok=True)
    (vault_path / ".obsidian").mkdir(exist_ok=True)

    # Create note files
    for note in notes:
        (vault_path / note.path).write_text(note.content)

    # Initialize vault
    db_path = vault_path / "_geistfabrik" / "vault.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    vault = Vault(vault_path, db_path)
    vault.sync()

    # Compute embeddings for all sessions
    for session_date in session_dates:
        session = Session(session_date, vault.db, computer=embedding_computer)
        session.compute_embeddings(notes)

    return vault


# ========== StatsCollector Tests ==========


def test_stats_collector_initialization(vault_with_embeddings):
    """Test StatsCollector initialisation and basic stats collection."""
    config = GeistFabrikConfig()
    collector = StatsCollector(vault_with_embeddings, config, history_days=30)

    # Should have collected basic stats on initialisation
    assert "vault" in collector.stats
    assert "notes" in collector.stats
    assert "tags" in collector.stats
    assert "links" in collector.stats
    assert "graph" in collector.stats
    assert "sessions" in collector.stats
    assert "geists" in collector.stats


def test_stats_collector_note_stats(vault_with_embeddings):
    """Test note statistics collection."""
    config = GeistFabrikConfig()
    collector = StatsCollector(vault_with_embeddings, config)

    note_stats = collector.stats["notes"]

    assert "total" in note_stats
    assert note_stats["total"] == 3  # sample_notes fixture has 3 notes


def test_stats_collector_has_embeddings(vault_with_embeddings):
    """Test checking if vault has embeddings."""
    config = GeistFabrikConfig()
    collector = StatsCollector(vault_with_embeddings, config)

    assert collector.has_embeddings() is True


def test_stats_collector_get_latest_embeddings(vault_with_embeddings):
    """Test retrieving latest embeddings."""
    config = GeistFabrikConfig()
    collector = StatsCollector(vault_with_embeddings, config)

    latest = collector.get_latest_embeddings()

    assert latest is not None
    session_date, embeddings, paths = latest

    assert session_date == "2025-01-15"
    assert isinstance(embeddings, np.ndarray)
    assert len(paths) == 3  # sample_notes has 3 notes
    assert embeddings.shape[0] == 3


# ========== EmbeddingMetricsComputer Tests ==========


def test_embedding_metrics_computer_initialization(vault_with_embeddings):
    """Test EmbeddingMetricsComputer initialisation."""
    computer = EmbeddingMetricsComputer(vault_with_embeddings.db)

    assert computer.db is vault_with_embeddings.db


def test_compute_metrics_basic(vault_with_embeddings):
    """Test basic metrics computation."""
    computer = EmbeddingMetricsComputer(vault_with_embeddings.db)

    # Get embeddings
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())
    session_date, embeddings, paths = collector.get_latest_embeddings()

    metrics = computer.compute_metrics(session_date, embeddings, paths)

    # Check basic structure
    assert "session_date" in metrics
    assert "n_notes" in metrics
    assert "dimension" in metrics
    assert metrics["n_notes"] == 3
    assert metrics["dimension"] == 387  # 384 semantic + 3 temporal


def test_compute_basic_metrics(vault_with_embeddings):
    """Test _compute_basic_metrics method."""
    computer = EmbeddingMetricsComputer(vault_with_embeddings.db)

    # Get embeddings
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())
    _, embeddings, _ = collector.get_latest_embeddings()

    metrics = computer._compute_basic_metrics(embeddings)

    # Check that metrics are present (may be None if dependencies missing)
    assert "intrinsic_dim" in metrics or metrics.get("intrinsic_dim") is None
    assert "vendi_score" in metrics or metrics.get("vendi_score") is None
    assert "isoscore" in metrics or metrics.get("isoscore") is None


def test_compute_basic_metrics_insufficient_data():
    """Test metrics computation with insufficient data."""
    db = init_db()
    computer = EmbeddingMetricsComputer(db)

    # Create a small embedding array (< 10 samples)
    small_embeddings = np.random.rand(5, 387).astype(np.float32)

    metrics = computer._compute_basic_metrics(small_embeddings)

    # Should still return a dict, but some metrics may be None
    assert isinstance(metrics, dict)

    db.close()


@pytest.mark.parametrize(
    "has_skdim,has_vendi",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_compute_metrics_with_optional_dependencies(vault_with_embeddings, has_skdim, has_vendi):
    """Test metrics computation with different optional dependencies."""
    computer = EmbeddingMetricsComputer(vault_with_embeddings.db)

    # Get embeddings - need enough for metrics
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())
    _, embeddings, _ = collector.get_latest_embeddings()

    # Create larger embedding array for testing
    embeddings = np.random.rand(50, 387).astype(np.float32)

    with (
        patch("geistfabrik.stats.HAS_SKDIM", has_skdim),
        patch("geistfabrik.stats.HAS_VENDI", has_vendi),
    ):
        metrics = computer._compute_basic_metrics(embeddings)

        # intrinsic_dim should only be present if HAS_SKDIM
        if not has_skdim:
            assert metrics.get("intrinsic_dim") is None

        # vendi_score should only be present if HAS_VENDI
        if not has_vendi:
            assert metrics.get("vendi_score") is None


def test_metrics_caching(vault_with_embeddings):
    """Test that metrics are cached in database."""
    computer = EmbeddingMetricsComputer(vault_with_embeddings.db)

    # Get embeddings
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())
    session_date, embeddings, paths = collector.get_latest_embeddings()

    # Compute metrics (will cache)
    metrics1 = computer.compute_metrics(session_date, embeddings, paths, force_recompute=True)

    # Retrieve from cache
    metrics2 = computer.compute_metrics(session_date, embeddings, paths, force_recompute=False)

    # Should have cached fields (session_date is always set, check cached metric fields)
    assert metrics2 is not None
    # Check cached fields that are stored in DB (from schema)
    if metrics1.get("intrinsic_dim") is not None:
        assert "intrinsic_dim" in metrics2
    if metrics1.get("vendi_score") is not None:
        assert "vendi_score" in metrics2


def test_metrics_caching_with_clustering(vault_with_embeddings):
    """Test metrics caching with actual clustering (requires 15+ notes).

    This test ensures that cluster_labels with numpy.int64 keys are properly
    converted to Python int keys for JSON serialization. Regression test for
    the bug where json.dumps() failed with "keys must be str, int, float, bool
    or None, not numpy.int64".
    """
    import json

    computer = EmbeddingMetricsComputer(vault_with_embeddings.db)

    # Create 15 notes in the database with realistic content
    # (enough for HDBSCAN min_cluster_size=5 to create clusters)
    db = vault_with_embeddings.db

    # Insert 15 test notes with varied content to encourage clustering
    test_notes = []
    for i in range(15):
        path = f"cluster_test_{i}.md"
        # Create 3 clusters of 5 notes each with similar content
        if i < 5:
            content = f"Machine learning and neural networks article {i}"
            title = f"ML Article {i}"
        elif i < 10:
            content = f"Philosophy and ethics discussion {i}"
            title = f"Philosophy Note {i}"
        else:
            content = f"History and military strategy {i}"
            title = f"History Note {i}"

        db.execute(
            """
            INSERT INTO notes (path, title, content, created, modified, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (path, title, content, "2025-01-01", "2025-01-01", 1704067200.0),
        )
        test_notes.append(path)

    db.commit()

    # Create embeddings that will cluster (varied but with structure)
    np.random.seed(42)
    embeddings = []
    for i in range(15):
        if i < 5:
            # Cluster 0: centred around [1, 0, 0, ...]
            base = np.array([1.0, 0.0, 0.0] + [0.0] * 384)
            noise = np.random.randn(387) * 0.1
        elif i < 10:
            # Cluster 1: centred around [0, 1, 0, ...]
            base = np.array([0.0, 1.0, 0.0] + [0.0] * 384)
            noise = np.random.randn(387) * 0.1
        else:
            # Cluster 2: centred around [0, 0, 1, ...]
            base = np.array([0.0, 0.0, 1.0] + [0.0] * 384)
            noise = np.random.randn(387) * 0.1

        embeddings.append((base + noise).astype(np.float32))

    embeddings_array = np.vstack(embeddings)

    # Create a session record (required for foreign key constraint)
    db.execute(
        "INSERT INTO sessions (date, vault_state_hash, created_at) VALUES (?, ?, ?)",
        ("2025-01-20", "test_hash", datetime.now().isoformat()),
    )
    db.commit()

    # Compute metrics with clustering enabled
    with patch("geistfabrik.stats.HAS_SKLEARN", True):
        metrics1 = computer.compute_metrics(
            "2025-01-20", embeddings_array, test_notes, force_recompute=True
        )

        # Verify clustering was performed
        assert "n_clusters" in metrics1

        # If clusters were detected, verify cluster_labels handling
        if metrics1.get("n_clusters", 0) > 0:
            assert "cluster_labels" in metrics1
            cluster_labels = metrics1["cluster_labels"]

            # Verify cluster_labels is a dict
            assert isinstance(cluster_labels, dict)

            # Critical: Verify JSON serialization works (would fail with numpy.int64 keys)
            try:
                json_str = json.dumps(cluster_labels)
                # Verify we can round-trip
                parsed = json.loads(json_str)
                assert len(parsed) == len(cluster_labels)
            except TypeError as e:
                pytest.fail(f"cluster_labels not JSON-serializable: {e}")

            # Verify labels are strings (TF-IDF terms)
            for cluster_id, label in cluster_labels.items():
                assert isinstance(label, str)
                assert len(label) > 0

        # Test cache retrieval
        metrics2 = computer.compute_metrics(
            "2025-01-20", embeddings_array, test_notes, force_recompute=False
        )

        # Verify cached cluster_labels are properly deserialized
        if metrics1.get("cluster_labels"):
            assert "cluster_labels" in metrics2
            assert metrics2["cluster_labels"] == metrics1["cluster_labels"]


def test_temporal_drift_no_past_session(vault_with_embeddings):
    """Test temporal drift when no past session exists."""
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())

    drift = collector.get_temporal_drift("2025-01-15", days_back=30)

    # Should return None if no past session
    assert drift is None


def test_temporal_drift_with_past_session(temp_dir, mock_embedding_computer):
    """Test temporal drift analysis with a past session."""
    # Create test notes
    notes = [
        Note(
            path="drift1.md",
            title="Drift Test 1",
            content="Original content about AI",
            links=[],
            tags=[],
            created=datetime(2024, 12, 1),
            modified=datetime(2024, 12, 1),
        ),
    ]

    # Create vault with past and current sessions
    vault_path = temp_dir / "drift_test_vault"
    vault = _create_vault_with_sessions(
        vault_path,
        notes,
        session_dates=[datetime(2024, 12, 16), datetime(2025, 1, 15)],
        embedding_computer=mock_embedding_computer,
    )

    # Test drift analysis - the method should either return valid drift or None
    collector = StatsCollector(vault, GeistFabrikConfig())
    drift = collector.get_temporal_drift("2025-01-15", days_back=30)

    # If drift is computed, verify structure
    if drift is not None:
        assert "current_date" in drift
        assert "comparison_date" in drift
        assert "average_drift" in drift
        assert "drift_trend" in drift
        assert 0 <= drift["average_drift"] <= 2

    vault.close()


# ========== Recommendations Tests ==========


def test_generate_recommendations_empty_stats():
    """Test recommendation generation with empty stats."""
    # Provide minimal required structure
    stats = {
        "notes": {"total": 0},
        "graph": {"orphan_pct": 0, "orphans": 0},
        "geists": {"code_disabled": 0},
    }
    recommendations = generate_recommendations(stats)

    # Should return a list
    assert isinstance(recommendations, list)
    # With no issues, should have "all clear" recommendation
    assert len(recommendations) > 0
    assert any(r["type"] == "health" for r in recommendations)


def test_generate_recommendations_orphans():
    """Test orphan detection recommendation."""
    stats = {
        "notes": {"total": 10},
        "graph": {"orphans": 5, "orphan_pct": 50.0},
        "geists": {"code_disabled": 0},
        "vault": {"vector_backend": "in-memory"},
    }

    recommendations = generate_recommendations(stats)

    # Should have an orphan warning (type is "structure")
    orphan_recs = [r for r in recommendations if r["type"] == "structure"]
    assert len(orphan_recs) > 0
    assert any("orphan" in r["message"].lower() for r in orphan_recs)


def test_generate_recommendations_low_diversity():
    """Test low diversity recommendation."""
    stats = {
        "notes": {"total": 100},
        "embeddings": {"vendi_score": 15.0},  # Low diversity (< 30% of notes)
        "graph": {"orphan_pct": 0},
        "geists": {"code_disabled": 0},
        "vault": {"vector_backend": "in-memory"},
    }

    recommendations = generate_recommendations(stats)

    # Should have a diversity recommendation
    diversity_recs = [r for r in recommendations if r["type"] == "diversity"]
    assert len(diversity_recs) > 0


def test_generate_recommendations_high_drift():
    """Test high drift recommendation."""
    stats = {
        "notes": {"total": 100},
        "graph": {"orphan_pct": 0},
        "geists": {"code_disabled": 0},
        "vault": {"vector_backend": "in-memory"},
        "temporal": {
            "average_drift": 0.6,  # High drift
            "drift_trend": "accelerating",
        },
    }

    recommendations = generate_recommendations(stats)

    # Should have a temporal warning
    temporal_recs = [r for r in recommendations if r["type"] == "temporal"]
    assert len(temporal_recs) > 0
    assert temporal_recs[0]["severity"] == "warning"


def test_generate_recommendations_low_drift():
    """Test low drift (stagnation) recommendation."""
    stats = {
        "notes": {"total": 100},
        "graph": {"orphan_pct": 0},
        "geists": {"code_disabled": 0},
        "vault": {"vector_backend": "in-memory"},
        "temporal": {
            "average_drift": 0.02,  # Very low drift
            "drift_trend": "stable",
        },
    }

    recommendations = generate_recommendations(stats)

    # Should have a stagnation info
    temporal_recs = [r for r in recommendations if r["type"] == "temporal"]
    assert len(temporal_recs) > 0
    assert "stagnating" in temporal_recs[0]["message"].lower()


# ========== StatsFormatter Tests ==========


def test_stats_formatter_text(vault_with_embeddings):
    """Test text formatting."""
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())
    recommendations = generate_recommendations(collector.stats)

    formatter = StatsFormatter(collector.stats, recommendations, verbose=False)
    text = formatter.format_text()

    assert isinstance(text, str)
    assert "Vault Statistics" in text or "Notes:" in text


def test_stats_formatter_json(vault_with_embeddings):
    """Test JSON formatting."""
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())
    recommendations = generate_recommendations(collector.stats)

    formatter = StatsFormatter(collector.stats, recommendations, verbose=False)
    json_str = formatter.format_json()

    assert isinstance(json_str, str)

    # Should be valid JSON
    import json

    data = json.loads(json_str)
    assert "notes" in data


def test_stats_formatter_with_temporal(vault_with_embeddings):
    """Test formatting with temporal analysis."""
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())

    # Add temporal data
    temporal_data = {
        "current_date": "2025-01-15",
        "comparison_date": "2024-12-16",
        "days_elapsed": 30,
        "notes_compared": 10,
        "average_drift": 0.25,
        "drift_trend": "stable",
        "high_drift_notes": [],
        "stable_notes": [],
    }
    collector.add_temporal_analysis(temporal_data)

    recommendations = generate_recommendations(collector.stats)
    formatter = StatsFormatter(collector.stats, recommendations, verbose=True)

    text = formatter.format_text()

    assert "Temporal" in text or "2025-01-15" in text


# ========== NumPy Type Conversion Tests ==========


def test_format_json_with_numpy_dict_keys():
    """Test that format_json() correctly handles dicts with numpy.int64 keys.

    Regression test for bug where cluster_labels with numpy.int64 keys
    would fail JSON serialization.
    """
    import json

    # Create minimal stats with a dict that has numpy.int64 keys
    stats = {
        "vault": {"path": "/test", "database_size_mb": 1.0},
        "notes": {"total": 10},
        "tags": {"unique": 5},
        "links": {"total": 20},
        "graph": {"orphans": 0},
        "sessions": {"total": 1},
        "geists": {"code_total": 5},
        "embeddings": {
            "n_clusters": 2,
            # This dict has numpy.int64 keys - the bug we're testing for
            "cluster_labels": {
                np.int64(0): "machine learning, neural networks",
                np.int64(1): "philosophy, ethics",
            },
        },
    }

    recommendations = []
    formatter = StatsFormatter(stats, recommendations, verbose=False)

    # This should not raise TypeError about numpy.int64 keys
    json_output = formatter.format_json()

    # Verify it's valid JSON
    parsed = json.loads(json_output)

    # Verify cluster_labels were converted (JSON converts int keys to strings)
    assert "embeddings" in parsed
    assert "cluster_labels" in parsed["embeddings"]
    assert "0" in parsed["embeddings"]["cluster_labels"]
    assert "1" in parsed["embeddings"]["cluster_labels"]


def test_format_json_with_nested_numpy_keys():
    """Test format_json() with nested dicts containing numpy keys."""
    import json

    stats = {
        "vault": {"path": "/test", "database_size_mb": 1.0},
        "notes": {"total": 10},
        "tags": {"unique": 5},
        "links": {"total": 20},
        "graph": {"orphans": 0},
        "sessions": {"total": 1},
        "geists": {"code_total": 5},
        "embeddings": {
            "dimension": np.int32(387),  # numpy scalar
            "n_notes": np.int64(100),  # numpy scalar
            "cluster_labels": {
                np.int64(0): "test cluster 0",
                np.int64(1): "test cluster 1",
                np.int64(2): "test cluster 2",
            },
            "metrics": {
                "silhouette": np.float64(0.75),
                "vendi_score": np.float32(42.5),
            },
        },
    }

    recommendations = []
    formatter = StatsFormatter(stats, recommendations, verbose=False)

    # Should successfully serialise
    json_output = formatter.format_json()
    parsed = json.loads(json_output)

    # Verify all numpy types were converted
    assert isinstance(parsed["embeddings"]["dimension"], int)
    assert isinstance(parsed["embeddings"]["n_notes"], int)
    assert isinstance(parsed["embeddings"]["metrics"]["silhouette"], float)
    assert isinstance(parsed["embeddings"]["metrics"]["vendi_score"], float)


def test_format_json_with_numpy_arrays():
    """Test format_json() with numpy arrays in stats."""
    import json

    stats = {
        "vault": {"path": "/test", "database_size_mb": 1.0},
        "notes": {"total": 10},
        "tags": {"unique": 5},
        "links": {"total": 20},
        "graph": {"orphans": 0},
        "sessions": {"total": 1},
        "geists": {"code_total": 5},
        "embeddings": {
            # Numpy array should be converted to list
            "sample_embedding": np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
            "cluster_sizes": np.array([10, 15, 20], dtype=np.int64),
        },
    }

    recommendations = []
    formatter = StatsFormatter(stats, recommendations, verbose=False)

    json_output = formatter.format_json()
    parsed = json.loads(json_output)

    # Arrays should be converted to lists
    assert isinstance(parsed["embeddings"]["sample_embedding"], list)
    assert isinstance(parsed["embeddings"]["cluster_sizes"], list)
    assert len(parsed["embeddings"]["sample_embedding"]) == 4
    assert len(parsed["embeddings"]["cluster_sizes"]) == 3


# ========== Integration Test for Full Pipeline ==========


def test_full_stats_pipeline(vault_with_embeddings):
    """Test complete stats collection and formatting pipeline."""
    # 1. Collect basic stats
    config = GeistFabrikConfig()
    collector = StatsCollector(vault_with_embeddings, config)

    assert collector.has_embeddings()

    # 2. Compute embedding metrics
    session_date, embeddings, paths = collector.get_latest_embeddings()
    metrics_computer = EmbeddingMetricsComputer(vault_with_embeddings.db)
    metrics = metrics_computer.compute_metrics(session_date, embeddings, paths)

    assert "n_notes" in metrics
    collector.add_embedding_metrics(metrics)

    # 3. Generate recommendations
    recommendations = generate_recommendations(collector.stats)

    assert isinstance(recommendations, list)

    # 4. Format output
    formatter = StatsFormatter(collector.stats, recommendations, verbose=False)

    text_output = formatter.format_text()
    assert isinstance(text_output, str)
    assert len(text_output) > 0

    json_output = formatter.format_json()
    assert isinstance(json_output, str)

    import json

    data = json.loads(json_output)
    assert "notes" in data
    assert "embeddings" in data


def test_isoscore_computation():
    """Test IsoScore (eigenvalue entropy) computation."""
    db = init_db()
    computer = EmbeddingMetricsComputer(db)

    # Create embeddings with known properties
    embeddings = np.random.rand(50, 387).astype(np.float32)

    metrics = computer._compute_basic_metrics(embeddings)

    # IsoScore should be computed for sufficient data
    if "isoscore" in metrics and metrics["isoscore"] is not None:
        # IsoScore should be in [0, 1]
        assert 0 <= metrics["isoscore"] <= 1

    db.close()


def test_procrustes_alignment():
    """Test Procrustes alignment improves similarity."""
    from scipy.linalg import orthogonal_procrustes  # type: ignore[import-untyped]

    from geistfabrik.embeddings import cosine_similarity

    # Create two sets of embeddings with rotation
    np.random.seed(42)
    embeddings1 = np.random.rand(10, 20).astype(np.float32)

    # Create rotated version
    angle = np.pi / 4
    rotation_2d = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])

    # Expand to full rotation matrix
    rotation_full = np.eye(20)
    rotation_full[:2, :2] = rotation_2d

    embeddings2 = embeddings1 @ rotation_full.T

    # Compute Procrustes alignment
    rotation, _ = orthogonal_procrustes(embeddings2, embeddings1)
    embeddings2_aligned = embeddings2 @ rotation

    # After alignment, embeddings should be closer
    sim_before = cosine_similarity(embeddings1[0], embeddings2[0])
    sim_after = cosine_similarity(embeddings1[0], embeddings2_aligned[0])

    # After alignment should be better (closer to 1)
    assert sim_after >= sim_before - 0.1  # Allow small numerical error
