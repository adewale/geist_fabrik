"""Tests for cluster labelling methods (c-TF-IDF and KeyBERT)."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.cluster_labeling import apply_mmr


@pytest.fixture
def mock_db(tmp_path):
    """Create a mock database with test notes."""
    import sqlite3

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
        ("note2.md", "Neural Networks", "Backpropagation gradient descent optimisation"),
        ("note3.md", "AI Training", "Model training validation testing evaluation"),
        ("note4.md", "React Components", "React hooks useState useEffect components"),
        ("note5.md", "Frontend Development", "JavaScript TypeScript web development"),
        ("note6.md", "Web Architecture", "Frontend architecture patterns state management"),
    ]

    db.executemany("INSERT INTO notes (path, title, content) VALUES (?, ?, ?)", test_notes)
    db.commit()

    return db


class TestClusterLabelingTFIDF:
    """Test c-TF-IDF cluster labelling method."""

    def test_label_clusters_tfidf_basic(self, mock_db):
        """Test that c-TF-IDF labelling produces keyword lists."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

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

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # All noise points
        paths = ["note1.md", "note2.md"]
        labels = np.array([-1, -1])

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        # Should return empty dict
        assert result == {}

    def test_label_clusters_tfidf_single_cluster(self, mock_db):
        """Test c-TF-IDF with single cluster."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        assert 0 in result
        assert isinstance(result[0], str)


class TestClusterLabelingKeyBERT:
    """Test KeyBERT cluster labelling method."""

    def test_label_clusters_keybert_basic(self, mock_db):
        """Test that KeyBERT labelling produces semantic phrases."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

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

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # All noise points
        paths = ["note1.md", "note2.md"]
        labels = np.array([-1, -1])

        result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Should return empty dict
        assert result == {}

    def test_label_clusters_keybert_fallback_on_error(self, mock_db):
        """Test KeyBERT falls back gracefully on errors."""

        from unittest.mock import patch

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        # Mock EmbeddingComputer to raise an error
        with patch("geistfabrik.embeddings.EmbeddingComputer") as mock_computer:
            mock_computer.return_value.compute_batch_semantic.side_effect = Exception(
                "Model failed"
            )

            result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

            # Should have fallback label
            assert 0 in result
            assert "Cluster 0" in result[0]


class TestClusterLabelingComparison:
    """Compare c-TF-IDF and KeyBERT methods."""

    def test_both_methods_produce_labels(self, mock_db):
        """Verify both methods produce valid labels for the same input."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

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

    def test_keybert_labels_use_trigrams_tfidf_labels_do_not(self, mock_db):
        """KeyBERT draws candidates from 1-3 word n-grams, c-TF-IDF from 1-2.

        Under the lexical stub a trigram of central words sits closest to the
        cluster centroid, so KeyBERT picks one; narrowing its ngram_range
        (or routing it through the c-TF-IDF candidates) fails this test.
        """
        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)
        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])

        keybert = metrics._label_clusters_keybert(paths, labels, n_terms=3)
        tfidf = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        def ngram_lengths(label: str) -> list[int]:
            return [len(term.split()) for term in label.split(", ")]

        for cluster_id in (0, 1):
            assert max(ngram_lengths(keybert[cluster_id])) == 3, keybert
            assert max(ngram_lengths(tfidf[cluster_id])) <= 2, tfidf


def _naive_mmr(terms: list[str], scores: list[float], lambda_param: float, k: int) -> list[str]:
    """Textbook greedy MMR with word-set Jaccard as the redundancy measure."""
    if len(terms) <= k:
        return terms

    def jaccard(x: str, y: str) -> float:
        a, b = set(x.lower().split()), set(y.lower().split())
        return len(a & b) / len(a | b) if a and b else 0.0

    selected: list[str] = []
    while len(selected) < k:
        best_term, best_score = "", float("-inf")
        for term, relevance in zip(terms, scores, strict=True):
            if term in selected:
                continue
            redundancy = max((jaccard(term, s) for s in selected), default=0.0)
            score = lambda_param * relevance - (1 - lambda_param) * redundancy
            if score > best_score:  # first maximum wins, like np.argmax
                best_term, best_score = term, score
        selected.append(best_term)
    return selected


_WORDS = ["neural", "network", "deep", "learning", "model", "graph", "garden"]
_terms = st.lists(
    st.lists(st.sampled_from(_WORDS), min_size=1, max_size=3).map(" ".join),
    min_size=1,
    max_size=10,
    unique=True,
)


@given(
    data=st.data(),
    terms=_terms,
    lambda_param=st.sampled_from([0.0, 0.3, 0.5, 0.7, 1.0]),
    k=st.integers(min_value=1, max_value=6),
)
@settings(max_examples=100, deadline=None)
def test_apply_mmr_matches_naive_reference(
    data: st.DataObject, terms: list[str], lambda_param: float, k: int
) -> None:
    """apply_mmr selects exactly what greedy MMR selects, in order.

    Regressions caught: penalising by the least (not most) similar selected
    term, dropping the diversity term or the lambda weighting, re-selecting a
    term, and an exception silently degrading to plain top-k by score.
    """
    scores = data.draw(
        st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=len(terms),
            max_size=len(terms),
        )
    )

    got = apply_mmr(terms, np.array(scores), lambda_param=lambda_param, k=k)

    assert got == _naive_mmr(terms, scores, lambda_param, k)


def test_apply_mmr_prefers_diverse_term_over_redundant_one() -> None:
    """Known answer: the runner-up shares a word with the winner, so a less
    relevant but unrelated term is picked second."""
    terms = ["neural network", "neural model", "garden soil"]
    scores = np.array([0.9, 0.85, 0.6])

    assert apply_mmr(terms, scores, lambda_param=0.5, k=2) == ["neural network", "garden soil"]
    # Pure relevance ignores redundancy.
    assert apply_mmr(terms, scores, lambda_param=1.0, k=2) == ["neural network", "neural model"]


class TestClusterConfig:
    """Test cluster configuration integration."""

    def test_config_defaults(self):
        """Verify clustering config has sensible defaults."""
        from geistfabrik.config_loader import ClusterConfig

        config = ClusterConfig()

        assert config.labeling_method == "keybert"
        assert config.min_cluster_size == 5
        assert config.n_label_terms == 4
