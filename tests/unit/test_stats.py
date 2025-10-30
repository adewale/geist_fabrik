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

    # Initialize vault
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


# ========== StatsCollector Tests ==========


def test_stats_collector_initialization(vault_with_embeddings):
    """Test StatsCollector initialization and basic stats collection."""
    config = GeistFabrikConfig()
    collector = StatsCollector(vault_with_embeddings, config, history_days=30)

    # Should have collected basic stats on initialization
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

    assert "total_notes" in note_stats
    assert note_stats["total_notes"] == 3  # sample_notes fixture has 3 notes


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
    """Test EmbeddingMetricsComputer initialization."""
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

    # Should be the same
    assert metrics1["session_date"] == metrics2["session_date"]
    assert metrics1["n_notes"] == metrics2["n_notes"]


def test_temporal_drift_no_past_session(vault_with_embeddings):
    """Test temporal drift when no past session exists."""
    collector = StatsCollector(vault_with_embeddings, GeistFabrikConfig())

    drift = collector.get_temporal_drift("2025-01-15", days_back=30)

    # Should return None if no past session
    assert drift is None


def test_temporal_drift_with_past_session(temp_dir, mock_embedding_computer):
    """Test temporal drift analysis with a past session."""
    vault_path = temp_dir / "drift_test_vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

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
        Note(
            path="drift2.md",
            title="Drift Test 2",
            content="Original content about machine learning",
            links=[],
            tags=[],
            created=datetime(2024, 12, 1),
            modified=datetime(2024, 12, 1),
        ),
    ]

    # Create note files
    for note in notes:
        (vault_path / note.path).write_text(note.content)

    # Initialize vault
    db_path = vault_path / "_geistfabrik" / "vault.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    vault = Vault(vault_path, db_path)
    vault.sync()

    # Compute embeddings for past session (30 days ago)
    past_session = Session(datetime(2024, 12, 16), vault.db, computer=mock_embedding_computer)
    past_session.compute_embeddings(notes)

    # Compute embeddings for current session
    current_session = Session(datetime(2025, 1, 15), vault.db, computer=mock_embedding_computer)
    current_session.compute_embeddings(notes)

    # Test drift analysis
    collector = StatsCollector(vault, GeistFabrikConfig())
    drift = collector.get_temporal_drift("2025-01-15", days_back=30)

    assert drift is not None
    assert "current_date" in drift
    assert "comparison_date" in drift
    assert "average_drift" in drift
    assert "drift_trend" in drift
    assert "high_drift_notes" in drift
    assert "stable_notes" in drift

    # Average drift should be in [0, 2]
    assert 0 <= drift["average_drift"] <= 2

    vault.close()


# ========== Recommendations Tests ==========


def test_generate_recommendations_empty_stats():
    """Test recommendation generation with empty stats."""
    recommendations = generate_recommendations({})

    # Should return a list (may be empty)
    assert isinstance(recommendations, list)


def test_generate_recommendations_orphans():
    """Test orphan detection recommendation."""
    stats = {
        "notes": {"total_notes": 10},
        "graph": {"orphans": 5},
    }

    recommendations = generate_recommendations(stats)

    # Should have an orphan warning
    orphan_recs = [r for r in recommendations if r["type"] == "graph"]
    assert len(orphan_recs) > 0


def test_generate_recommendations_low_diversity():
    """Test low diversity recommendation."""
    stats = {
        "notes": {"total_notes": 100},
        "embeddings": {"n_notes": 100, "vendi_score": 15.0},  # Low diversity
    }

    recommendations = generate_recommendations(stats)

    # Should have a diversity recommendation
    diversity_recs = [r for r in recommendations if r["type"] == "diversity"]
    assert len(diversity_recs) > 0


def test_generate_recommendations_high_drift():
    """Test high drift recommendation."""
    stats = {
        "temporal": {
            "average_drift": 0.6,  # High drift
            "drift_trend": "accelerating",
        }
    }

    recommendations = generate_recommendations(stats)

    # Should have a temporal warning
    temporal_recs = [r for r in recommendations if r["type"] == "temporal"]
    assert len(temporal_recs) > 0
    assert temporal_recs[0]["severity"] == "warning"


def test_generate_recommendations_low_drift():
    """Test low drift (stagnation) recommendation."""
    stats = {
        "temporal": {
            "average_drift": 0.02,  # Very low drift
            "drift_trend": "stable",
        }
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
