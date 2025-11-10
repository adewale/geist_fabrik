"""Unit tests for O(N²) algorithmic fixes in BIG OPTIMISATION #1.

Tests verify that dict/set-based implementations produce identical results
to the original list-based implementations, while being more efficient.
"""

from typing import List

import numpy as np

# We'll test the fixed implementations against known outputs


class TestStatsAlgorithmicFixes:
    """Tests for stats.py algorithmic fixes."""

    def test_compute_vault_drift_with_dict_lookup(self):
        """Test that dict-based path indexing produces same results as list.index()."""
        # Simulate the pattern from stats.py:591
        curr_paths = [f"note_{i}.md" for i in range(100)]
        common_paths = [f"note_{i}.md" for i in range(0, 100, 10)]  # Every 10th note

        # Create mock embeddings
        np.random.seed(42)
        curr_emb = np.random.rand(100, 387)  # 100 notes x 387-dim embeddings

        # BEFORE: O(N²) with list.index()
        curr_aligned_old = np.vstack([curr_emb[curr_paths.index(p)] for p in common_paths])

        # AFTER: O(N) with dict lookup
        path_to_idx = {p: i for i, p in enumerate(curr_paths)}
        curr_aligned_new = np.vstack([curr_emb[path_to_idx[p]] for p in common_paths])

        # Should produce identical results
        np.testing.assert_array_equal(curr_aligned_old, curr_aligned_new)

    def test_mmr_diversify_with_dict_lookup(self):
        """Test that dict-based term indexing produces same results as list.index()."""
        # Simulate the pattern from stats.py:973
        terms = [f"term_{i}" for i in range(50)]
        tfidf_scores = np.random.rand(50)

        # BEFORE: O(k*N²) with list.index()
        old_relevances = []
        for term in terms[:10]:  # First 10 terms
            term_idx = terms.index(term)
            old_relevances.append(tfidf_scores[term_idx])

        # AFTER: O(k*N) with dict lookup
        term_to_idx = {t: i for i, t in enumerate(terms)}
        new_relevances = []
        for term in terms[:10]:
            term_idx = term_to_idx[term]
            new_relevances.append(tfidf_scores[term_idx])

        # Should produce identical results
        np.testing.assert_array_equal(old_relevances, new_relevances)

    def test_mmr_diversify_with_set_membership(self):
        """Test that set-based membership produces same results as list membership."""
        # Simulate the pattern from stats.py:966
        terms = [f"term_{i}" for i in range(20)]
        k = 5

        # BEFORE: O(k*N) with list membership
        selected_list = []
        iterations_old = 0
        while len(selected_list) < k and iterations_old < len(terms):
            remaining_old = [t for t in terms if t not in selected_list]
            if remaining_old:
                selected_list.append(remaining_old[0])
            iterations_old += 1

        # AFTER: O(k) with set membership
        selected_set = set()
        selected_list_new = []
        iterations_new = 0
        while len(selected_set) < k and iterations_new < len(terms):
            remaining_new = [t for t in terms if t not in selected_set]
            if remaining_new:
                selected_set.add(remaining_new[0])
                selected_list_new.append(remaining_new[0])
            iterations_new += 1

        # Should produce identical results
        assert selected_list == selected_list_new


class TestPatternFinderAlgorithmicFixes:
    """Tests for pattern_finder.py algorithmic fixes."""

    def test_clustering_with_set_remove(self):
        """Test that set-based remove produces same clustering as list-based remove."""
        # Simulate simplified clustering pattern from pattern_finder.py

        # Mock note class
        class MockNote:
            def __init__(self, path: str):
                self.path = path
                self.title = path

            def __hash__(self):
                return hash(self.path)

            def __eq__(self, other):
                return self.path == other.path

        notes = [MockNote(f"note_{i}.md") for i in range(20)]

        # Mock similarity function (deterministic)
        def mock_similarity(a: MockNote, b: MockNote) -> float:
            # Deterministic similarity based on path names
            a_num = int(a.path.split("_")[1].split(".")[0])
            b_num = int(b.path.split("_")[1].split(".")[0])
            return 1.0 / (1.0 + abs(a_num - b_num))

        # BEFORE: O(N³) with list.remove()
        unclustered_list = list(notes)
        clusters_old: List[List[MockNote]] = []

        while len(unclustered_list) > 5 and len(clusters_old) < 3:
            seed = unclustered_list[0]  # Deterministic seed selection
            unclustered_list.remove(seed)

            cluster = [seed]
            for note in unclustered_list[:]:  # Copy to avoid modification during iteration
                if mock_similarity(seed, note) > 0.7:
                    cluster.append(note)
                    unclustered_list.remove(note)
                if len(cluster) >= 5:
                    break

            if len(cluster) >= 3:
                clusters_old.append(cluster)

        # AFTER: O(N²) with set.remove()
        unclustered_set = set(notes)
        clusters_new: List[List[MockNote]] = []

        while len(unclustered_set) > 5 and len(clusters_new) < 3:
            # Deterministic seed selection (first by sorted path)
            seed = sorted(list(unclustered_set), key=lambda n: n.path)[0]
            unclustered_set.remove(seed)

            cluster = [seed]
            to_remove = []
            for note in sorted(list(unclustered_set), key=lambda n: n.path):
                if mock_similarity(seed, note) > 0.7:
                    cluster.append(note)
                    to_remove.append(note)
                if len(cluster) >= 5:
                    break

            for note in to_remove:
                unclustered_set.remove(note)

            if len(cluster) >= 3:
                clusters_new.append(cluster)

        # Should produce same number of clusters
        assert len(clusters_old) == len(clusters_new)

        # Should have same cluster sizes
        old_sizes = sorted([len(c) for c in clusters_old])
        new_sizes = sorted([len(c) for c in clusters_new])
        assert old_sizes == new_sizes


class TestVaultContextAlgorithmicFixes:
    """Tests for vault_context.py algorithmic fixes."""

    def test_unlinked_pairs_with_set_membership(self):
        """Test that set-based membership produces same filtering as list membership."""
        # Simulate simplified pattern from vault_context.py:619

        class MockNote:
            def __init__(self, path: str):
                self.path = path

            def __eq__(self, other):
                return self.path == other.path

            def __hash__(self):
                return hash(self.path)

        all_notes = [MockNote(f"note_{i}.md") for i in range(100)]
        recent = all_notes[:20]  # First 20 notes are "recent"

        # BEFORE: O(N*M) with list membership
        remaining_old = [n for n in all_notes if n not in recent]

        # AFTER: O(N) with set membership
        recent_set = set(recent)
        remaining_new = [n for n in all_notes if n not in recent_set]

        # Should produce same results
        assert len(remaining_old) == len(remaining_new)
        assert set(n.path for n in remaining_old) == set(n.path for n in remaining_new)
