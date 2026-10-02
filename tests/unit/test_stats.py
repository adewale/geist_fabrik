"""Unit tests for stats module."""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.embedding_metrics import EmbeddingMetricsComputer
from geistfabrik.embeddings import Session
from geistfabrik.schema import init_db
from geistfabrik.stats import StatsCollector, VaultStats
from geistfabrik.stats_formatter import StatsFormatter, generate_recommendations
from geistfabrik.vault import Vault
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder
from tests.fixtures.temporal import set_session_text

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

    # Compute from the canonical rows produced by filesystem synchronization.
    session = Session(datetime(2025, 1, 15), vault.db, computer=mock_embedding_computer)
    session.compute_embeddings(vault.all_notes())

    yield vault
    vault.close()


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
    latest = collector.get_latest_embeddings()
    assert latest is not None
    session_date, embeddings, paths = latest

    metrics = computer.compute_metrics(session_date, embeddings, paths)

    # Check basic structure
    assert "session_date" in metrics
    assert "n_notes" in metrics
    assert "dimension" in metrics
    assert metrics["n_notes"] == 3
    # Stats describe meaning: the 3 calendar features of a stored session
    # embedding are dropped, leaving the 384 semantic dimensions.
    assert metrics["dimension"] == 384


@pytest.fixture(params=[True, False], ids=["sklearn", "fallback"])
def similarity_path(request, monkeypatch):
    """Run a test through both the sklearn and the pure-Python similarity branch."""
    import geistfabrik.embedding_metrics as em

    monkeypatch.setattr(em, "HAS_SKLEARN", request.param)
    monkeypatch.setattr(em, "HAS_VENDI", False)
    monkeypatch.setattr(em, "HAS_SKDIM", False)
    return request.param


@pytest.mark.parametrize(
    ("embeddings", "mean", "std"),
    [
        # Orthogonal rows of different lengths: every pair scores 0.
        (np.eye(4, 8) * np.array([[1.0], [2.0], [0.5], [3.0]]), 0.0, 0.0),
        # Identical (scaled) directions: every pair scores 1.
        (np.array([[1.0, 2.0, 2.0]] * 3) * np.array([[1.0], [3.0], [0.1]]), 1.0, 0.0),
        # Pairs (e1, e1), (e1, e2), (e1, e2) score 1, 0, 0.
        (np.array([[1.0, 0.0], [2.0, 0.0], [0.0, 5.0]]), 1 / 3, np.sqrt(2) / 3),
    ],
    ids=["orthogonal", "identical", "mixed"],
)
def test_basic_metrics_similarity_known_answers(similarity_path, embeddings, mean, std):
    """avg/std_similarity are the mean and population std of pairwise cosine
    over distinct pairs (upper triangle, no diagonal), on either branch.

    Regressions caught: including self-pairs, using dot products instead of
    cosine, or reporting variance instead of standard deviation.
    """
    db = init_db()
    try:
        metrics = EmbeddingMetricsComputer(db)._compute_basic_metrics(embeddings.astype(np.float32))
    finally:
        db.close()

    assert metrics["avg_similarity"] == pytest.approx(mean, abs=1e-6)
    assert metrics["std_similarity"] == pytest.approx(std, abs=1e-6)


def test_basic_metrics_insufficient_data_omits_undefined_metrics(similarity_path):
    """Metrics that need more data are absent, never NaN or zero placeholders:
    one note has no pairs; fewer than 10 notes gets no IsoScore."""
    db = init_db()
    try:
        computer = EmbeddingMetricsComputer(db)
        single = computer._compute_basic_metrics(np.ones((1, 387), dtype=np.float32))
        few = computer._compute_basic_metrics(np.eye(5, 387, dtype=np.float32))
    finally:
        db.close()

    assert single == {}
    assert set(few) == {"avg_similarity", "std_similarity"}


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
    latest = collector.get_latest_embeddings()
    assert latest is not None
    _, embeddings, _ = latest

    # Create larger embedding array for testing
    embeddings = np.random.rand(50, 387).astype(np.float32)

    with (
        patch("geistfabrik.embedding_metrics.HAS_SKDIM", has_skdim),
        patch("geistfabrik.embedding_metrics.HAS_VENDI", has_vendi),
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
    latest = collector.get_latest_embeddings()
    assert latest is not None
    session_date, embeddings, paths = latest

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
    with patch("geistfabrik.embedding_metrics.HAS_SKLEARN", True):
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


def test_temporal_drift_aligns_sessions_by_note_path(tmp_path):
    """Drift compares each note with ITS OWN past embedding.

    Content is unchanged between sessions, but a new note that sorts first
    appears, shifting every row index. Aligned by path, every note has zero
    drift; paired by row position, notes are compared with their neighbours.
    Titles are under three characters so the lexical stub embeds only the
    bodies, whose irregular word overlaps make row-mispaired notes differ.
    """
    bodies = {
        "N1": "amber basil cedar",
        "N2": "basil cedar delta ember",
        "N3": "amber fjord",
        "N4": "cedar ember fjord grove",
        "N5": "amber delta grove",
        "N6": "basil fjord",
    }
    for title, body in bodies.items():
        (tmp_path / f"{title}.md").write_text(f"# {title}\n\n{body}")
    vault = Vault(str(tmp_path), ":memory:")
    try:
        vault.sync()
        Session(datetime(2024, 12, 1), vault.db).compute_embeddings(vault.all_notes())
        (tmp_path / "A0.md").write_text("# A0\n\nburrow termites savanna")
        vault.sync()
        Session(datetime(2025, 1, 15), vault.db).compute_embeddings(vault.all_notes())

        drift = StatsCollector(vault, GeistFabrikConfig()).get_temporal_drift(
            "2025-01-15", days_back=30
        )
    finally:
        vault.close()

    assert drift is not None
    assert drift["comparison_date"] == "2024-12-01"
    assert drift["notes_compared"] == 6  # A0 has no past embedding
    reported = drift["high_drift_notes"] + drift["stable_notes"]
    assert {n["title"] for n in reported} == set(bodies)
    assert drift["average_drift"] == 0.0
    assert all(n["drift"] == 0.0 for n in reported), reported


# Eight notes with mutually disjoint vocabularies. Only REWRITTEN and REVISED
# said something different in the history session; FRESH was created on the
# history date, so its calendar tail (age, session season) moves the most.
DRIFT_HISTORY = datetime(2022, 9, 15)
DRIFT_BODIES = {
    "Rewritten": "harbour lighthouse tide ferry anchor",
    "Revised": "glacier moraine crevasse summit valley",
    "Fresh": "pottery kiln glaze clay wheel",
    "Ledger": "invoice receipt budget audit",
    "Orchid": "petal stamen pollen nectar",
    "Comet": "orbit perihelion nucleus coma",
    "Falcon": "talon plumage hover swoop",
    "Quartz": "crystal lattice facet mineral",
}
# Title word shared, bodies disjoint: 6 vs 5 content words, overlap 1.
REWRITTEN_PAST = "# Rewritten\n\nviolin sonata rehearsal concerto"
# Title plus three body words shared, two swapped: 6 vs 6 words, overlap 4.
REVISED_PAST = "# Revised\n\nglacier moraine crevasse orchard vineyard"


def test_temporal_drift_known_answers_for_rewritten_unchanged_and_calendar_only(tmp_path):
    """Drift measures what a note says, in the pinned model's own coordinates.

    Contract: a note whose text was replaced drifts by 1 - cos(old, new); an
    unchanged note drifts 0 even when its calendar features moved; the
    changed notes head the report and never appear among the stable ones.
    Regressions caught: re-introducing an alignment fitted to the same few
    notes (a rotation in 384 dims absorbs the rewrite and smears it over
    unchanged notes), comparing the full vector including the calendar tail,
    and reporting a rewritten note as a "smallest change" in small vaults.
    """
    builder = VaultBuilder(tmp_path)
    for title, body in DRIFT_BODIES.items():
        created = DRIFT_HISTORY if title == "Fresh" else datetime(2021, 6, 1)
        builder.note(title, body, created=created, modified=created)
    ctx = builder.build(history=[DRIFT_HISTORY])
    set_session_text(ctx, "Rewritten.md", DRIFT_HISTORY, REWRITTEN_PAST)
    set_session_text(ctx, "Revised.md", DRIFT_HISTORY, REVISED_PAST)

    drift = StatsCollector(ctx.vault, GeistFabrikConfig()).get_temporal_drift(
        SESSION_DATE.strftime("%Y-%m-%d")
    )

    assert drift is not None
    assert drift["comparison_date"] == DRIFT_HISTORY.strftime("%Y-%m-%d")
    assert drift["notes_compared"] == len(DRIFT_BODIES)
    high = [(n["title"], n["drift"]) for n in drift["high_drift_notes"]]
    rewritten = round(1 - 1 / np.sqrt(6 * 5), 2)  # 0.82
    revised = round(1 - 4 / 6, 2)  # 0.33
    assert high[:2] == [("Rewritten", rewritten), ("Revised", revised)]
    # Every other note, including calendar-only FRESH, did not move.
    stable = [(n["title"], n["drift"]) for n in drift["stable_notes"]]
    assert not {title for title, _ in high} & {title for title, _ in stable}
    unchanged = high[2:] + stable
    assert {title for title, _ in unchanged} <= set(DRIFT_BODIES) - {"Rewritten", "Revised"}
    assert "Fresh" in {title for title, _ in unchanged}
    assert all(value == 0.0 for _, value in unchanged), unchanged
    expected_mean = (1 - 1 / np.sqrt(30) + 1 - 4 / 6) / len(DRIFT_BODIES)
    assert drift["average_drift"] == pytest.approx(expected_mean, abs=0.002)


# ========== Recommendations Tests ==========


def test_generate_recommendations_empty_stats():
    """Test recommendation generation with empty stats."""
    # Provide minimal required structure
    stats: VaultStats = {
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
    stats: VaultStats = {
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
    stats: VaultStats = {
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
    stats: VaultStats = {
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
    """Test low snapshot-distance recommendation without a mental-state claim."""
    stats: VaultStats = {
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

    # Low movement is measured; whether the vault is stagnating is not.
    temporal_recs = [r for r in recommendations if r["type"] == "temporal"]
    assert len(temporal_recs) > 0
    assert "compared snapshots" in temporal_recs[0]["message"].lower()
    assert "stagnating" not in temporal_recs[0]["message"].lower()


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
    stats: VaultStats = {
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

    stats: VaultStats = {
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

    stats: VaultStats = {
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
    latest = collector.get_latest_embeddings()
    assert latest is not None
    session_date, embeddings, paths = latest
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
