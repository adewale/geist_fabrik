"""Tests for cluster labeling methods (c-TF-IDF and KeyBERT)."""

import pytest
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.stats import EmbeddingMetricsComputer


@pytest.fixture
def mock_db(tmp_path):
    """Create a mock database with test notes."""
    import sqlite3
    from pathlib import Path

    db_path = tmp_path / "test.db"
    db = sqlite3.connect(str(db_path))

    # Create notes table
    db.execute(
        """
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT,
            content TEXT
        )
        """
    )

    # Insert test notes for clustering
    test_notes = [
        ("note1.md", "Machine Learning", "Deep learning neural networks training models"),
        ("note2.md", "Neural Networks", "Backpropagation gradient descent optimization"),
        ("note3.md", "AI Training", "Model training validation testing evaluation"),
        ("note4.md", "React Components", "React hooks useState useEffect components"),
        ("note5.md", "Frontend Development", "JavaScript TypeScript web development"),
        ("note6.md", "Web Architecture", "Frontend architecture patterns state management"),
    ]

    db.executemany("INSERT INTO notes (path, title, content) VALUES (?, ?, ?)", test_notes)
    db.commit()

    return db


class TestClusterLabelingTFIDF:
    """Test c-TF-IDF cluster labeling method."""

    def test_label_clusters_tfidf_basic(self, mock_db):
        """Test that c-TF-IDF labeling produces keyword lists."""
        pytest.importorskip("sklearn")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # Create cluster labels (2 clusters)
        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])  # 3 notes in each cluster

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        # Should have labels for both clusters
        assert 0 in result
        assert 1 in result

        # Labels should be comma-separated strings
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)
        assert "," in result[0] or len(result[0].split()) <= 3
        assert "," in result[1] or len(result[1].split()) <= 3

    def test_label_clusters_tfidf_empty(self, mock_db):
        """Test c-TF-IDF with no clusters."""
        pytest.importorskip("sklearn")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # All noise points
        paths = ["note1.md", "note2.md"]
        labels = np.array([-1, -1])

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        # Should return empty dict
        assert result == {}

    def test_label_clusters_tfidf_single_cluster(self, mock_db):
        """Test c-TF-IDF with single cluster."""
        pytest.importorskip("sklearn")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        assert 0 in result
        assert isinstance(result[0], str)


class TestClusterLabelingKeyBERT:
    """Test KeyBERT cluster labeling method."""

    def test_label_clusters_keybert_basic(self, mock_db):
        """Test that KeyBERT labeling produces semantic phrases."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # Create cluster labels (2 clusters)
        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])

        result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Should have labels for both clusters
        assert 0 in result
        assert 1 in result

        # Labels should be comma-separated strings
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_label_clusters_keybert_empty(self, mock_db):
        """Test KeyBERT with no clusters."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # All noise points
        paths = ["note1.md", "note2.md"]
        labels = np.array([-1, -1])

        result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Should return empty dict
        assert result == {}

    def test_label_clusters_keybert_fallback_on_error(self, mock_db):
        """Test KeyBERT falls back gracefully on errors."""
        pytest.importorskip("sklearn")

        from geistfabrik.stats import EmbeddingMetricsComputer
        from unittest.mock import patch

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        # Mock EmbeddingComputer to raise an error
        with patch("geistfabrik.stats.EmbeddingComputer") as mock_computer:
            mock_computer.side_effect = Exception("Model failed")

            result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

            # Should have fallback label
            assert 0 in result
            assert "Cluster 0" in result[0]


class TestClusterLabelingComparison:
    """Compare c-TF-IDF and KeyBERT methods."""

    def test_both_methods_produce_labels(self, mock_db):
        """Verify both methods produce valid labels for the same input."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])

        tfidf_result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)
        keybert_result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Both should have same cluster IDs
        assert set(tfidf_result.keys()) == set(keybert_result.keys())

        # Both should produce non-empty strings
        for cluster_id in tfidf_result:
            assert len(tfidf_result[cluster_id]) > 0
            assert len(keybert_result[cluster_id]) > 0

    def test_keybert_uses_longer_ngrams(self, mock_db):
        """Verify KeyBERT can produce longer phrases than c-TF-IDF."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.stats import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # Note: This test is more observational - KeyBERT uses ngram_range=(1,3)
        # while c-TF-IDF uses (1,2), so KeyBERT *can* produce longer phrases,
        # though it's not guaranteed every time

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        keybert_result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Just verify it produces a valid label
        assert 0 in keybert_result
        assert isinstance(keybert_result[0], str)
        assert len(keybert_result[0]) > 0


class TestClusterConfig:
    """Test cluster configuration integration."""

    def test_config_has_clustering_section(self):
        """Verify GeistFabrikConfig includes clustering settings."""
        from geistfabrik.config_loader import GeistFabrikConfig, ClusterConfig

        config = GeistFabrikConfig()

        assert hasattr(config, "clustering")
        assert isinstance(config.clustering, ClusterConfig)
        assert hasattr(config.clustering, "labeling_method")
        assert hasattr(config.clustering, "min_cluster_size")
        assert hasattr(config.clustering, "n_label_terms")

    def test_config_defaults(self):
        """Verify clustering config has sensible defaults."""
        from geistfabrik.config_loader import ClusterConfig

        config = ClusterConfig()

        assert config.labeling_method == "keybert"
        assert config.min_cluster_size == 5
        assert config.n_label_terms == 4

    def test_config_from_dict(self):
        """Test loading clustering config from dictionary."""
        from geistfabrik.config_loader import GeistFabrikConfig

        config_dict = {
            "clustering": {
                "labeling_method": "tfidf",
                "min_cluster_size": 10,
                "n_label_terms": 3,
            }
        }

        config = GeistFabrikConfig.from_dict(config_dict)

        assert config.clustering.labeling_method == "tfidf"
        assert config.clustering.min_cluster_size == 10
        assert config.clustering.n_label_terms == 3

    def test_config_to_dict(self):
        """Test serializing clustering config to dictionary."""
        from geistfabrik.config_loader import GeistFabrikConfig, ClusterConfig

        config = GeistFabrikConfig(
            clustering=ClusterConfig(labeling_method="tfidf", min_cluster_size=10, n_label_terms=3)
        )

        config_dict = config.to_dict()

        assert "clustering" in config_dict
        assert config_dict["clustering"]["labeling_method"] == "tfidf"
        assert config_dict["clustering"]["min_cluster_size"] == 10
        assert config_dict["clustering"]["n_label_terms"] == 3
