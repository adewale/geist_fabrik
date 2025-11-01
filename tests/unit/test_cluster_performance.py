"""Performance tests for cluster caching optimization.

These tests validate that get_clusters() caching reduces redundant HDBSCAN
clustering operations from O(n) to O(1) within a session.
"""

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from geistfabrik import VaultContext


class TestClusterCaching:
    """Test session-scoped caching for get_clusters()."""

    def test_get_clusters_caches_by_min_size(self, vault_with_notes: "VaultContext") -> None:
        """Verify get_clusters() caches results per session by min_size parameter.

        Before optimization: get_clusters() re-computes HDBSCAN on every call
        After optimization: get_clusters() returns cached result within session

        This test verifies caching works correctly by tracking HDBSCAN calls.
        """
        # Skip if sklearn not available
        pytest.importorskip("sklearn")

        # Create vault with enough notes for clustering
        vault = vault_with_notes

        # Track HDBSCAN.fit_predict calls
        with patch("sklearn.cluster.HDBSCAN") as mock_hdbscan_class:
            mock_clusterer = MagicMock()
            mock_hdbscan_class.return_value = mock_clusterer
            # Return valid labels (all noise points for simplicity)
            mock_clusterer.fit_predict.return_value = [-1] * 20

            # First call should trigger clustering
            result1 = vault.get_clusters(min_size=5)

            # Second call with same min_size should use cache
            result2 = vault.get_clusters(min_size=5)

            # Third call with same min_size should use cache
            result3 = vault.get_clusters(min_size=5)

            # Verify HDBSCAN was only called ONCE (cached for subsequent calls)
            assert mock_clusterer.fit_predict.call_count == 1

            # Verify results are identical (same dict reference due to caching)
            assert result1 is result2
            assert result2 is result3

    def test_get_clusters_different_min_size_creates_new_cache(
        self, vault_with_notes: "VaultContext"
    ) -> None:
        """Verify different min_size parameters create separate cache entries.

        Cache key should include min_size so different parameters don't
        return stale results.
        """
        # Skip if sklearn not available
        pytest.importorskip("sklearn")

        vault = vault_with_notes

        with patch("sklearn.cluster.HDBSCAN") as mock_hdbscan_class:
            mock_clusterer = MagicMock()
            mock_hdbscan_class.return_value = mock_clusterer
            mock_clusterer.fit_predict.return_value = [-1] * 20

            # Call with min_size=5
            result1 = vault.get_clusters(min_size=5)

            # Call with min_size=10 should trigger new clustering
            _ = vault.get_clusters(min_size=10)

            # Call with min_size=5 again should use cached result
            result3 = vault.get_clusters(min_size=5)

            # Verify HDBSCAN was called twice (once per unique min_size)
            assert mock_clusterer.fit_predict.call_count == 2

            # Verify cached result is same reference
            assert result1 is result3

    def test_get_cluster_representatives_with_clusters_param(
        self, vault_with_notes: "VaultContext"
    ) -> None:
        """Verify get_cluster_representatives() accepts clusters parameter to avoid re-clustering.

        Before optimization: get_cluster_representatives() calls get_clusters() internally
        After optimization: accepts optional clusters parameter to reuse existing results

        This is the key fix for cluster_mirror's redundant clustering.
        """
        # Skip if sklearn not available
        pytest.importorskip("sklearn")

        vault = vault_with_notes

        with patch("sklearn.cluster.HDBSCAN") as mock_hdbscan_class:
            mock_clusterer = MagicMock()
            mock_hdbscan_class.return_value = mock_clusterer
            # Return labels with one cluster
            mock_clusterer.fit_predict.return_value = [0] * 20

            # Get clusters once
            clusters = vault.get_clusters(min_size=5)

            # Reset call count after initial clustering
            mock_clusterer.fit_predict.reset_mock()

            if clusters:
                cluster_id = list(clusters.keys())[0]

                # Call get_cluster_representatives WITH clusters parameter
                # Should NOT trigger new clustering
                _ = vault.get_cluster_representatives(cluster_id, k=3, clusters=clusters)

                # Verify no additional clustering occurred
                assert mock_clusterer.fit_predict.call_count == 0

    def test_cluster_mirror_performance_improvement(self, vault_with_notes: "VaultContext") -> None:
        """Integration test: verify cluster_mirror uses caching and clusters parameter.

        Before optimization: 4 clustering operations (1 initial + 3 in loop)
        After optimization: 1 clustering operation (cached for subsequent calls)

        This test simulates the actual cluster_mirror geist execution.
        """
        # Skip if sklearn not available
        pytest.importorskip("sklearn")

        vault = vault_with_notes

        with patch("sklearn.cluster.HDBSCAN") as mock_hdbscan_class:
            mock_clusterer = MagicMock()
            mock_hdbscan_class.return_value = mock_clusterer
            # Return labels with 3 valid clusters
            labels = [0] * 7 + [1] * 7 + [2] * 6
            mock_clusterer.fit_predict.return_value = labels

            # Simulate cluster_mirror execution
            clusters = vault.get_clusters(min_size=5)

            # Select 3 clusters (as cluster_mirror does)
            cluster_ids = list(clusters.keys())[:3]

            # Get representatives for each cluster
            for cluster_id in cluster_ids:
                vault.get_cluster_representatives(cluster_id, k=3, clusters=clusters)

            # Verify HDBSCAN was called only ONCE (not 4 times)
            # This is the 4x performance improvement
            assert mock_clusterer.fit_predict.call_count == 1

    def test_timing_baseline_without_caching(self, vault_with_notes: "VaultContext") -> None:
        """Baseline timing test WITHOUT caching (for comparison).

        This documents the before-optimization behavior for regression testing.
        """
        # Skip if sklearn not available
        pytest.importorskip("sklearn")

        vault = vault_with_notes

        # Simulate old behavior: call get_clusters() 4 times
        start_time = time.perf_counter()

        clusters1 = vault.get_clusters(min_size=5)
        clusters2 = vault.get_clusters(min_size=5)
        clusters3 = vault.get_clusters(min_size=5)
        clusters4 = vault.get_clusters(min_size=5)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Document timing for baseline
        # With caching: should be ~4x faster than this baseline
        # (actual speedup depends on HDBSCAN performance)
        print(f"\nBaseline (4 calls): {total_time:.3f}s")

        # Verify all calls return same cluster structure
        # (Note: can't use == due to numpy arrays in centroid)
        assert len(clusters1) == len(clusters2) == len(clusters3) == len(clusters4)
        assert set(clusters1.keys()) == set(clusters2.keys())


@pytest.fixture
def vault_with_notes(tmp_path):
    """Create test vault with enough notes for clustering."""
    from geistfabrik import Vault, VaultContext

    # Create vault directory
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()

    # Create 20 notes with varied content for clustering
    topics = {
        "python": 7,
        "rust": 7,
        "javascript": 6,
    }

    note_id = 0
    for topic, count in topics.items():
        for i in range(count):
            note_path = vault_dir / f"{topic}_{i}.md"
            note_path.write_text(
                f"# {topic.title()} Note {i}\n\n"
                f"This is a note about {topic} programming. "
                f"Content about {topic} development and {topic} best practices."
            )
            note_id += 1

    # Initialize vault
    vault = Vault(str(vault_dir))
    vault.sync()

    # Create session with embeddings
    from datetime import datetime

    from geistfabrik.embeddings import Session

    session_date = datetime(2023, 6, 15)
    session = Session(session_date, vault.db)
    session.compute_embeddings(vault.all_notes())

    # Create VaultContext
    context = VaultContext(vault, session)

    return context
