"""Unit tests for sklearn/scipy migration in BIG OPTIMISATION #2.

Tests verify that sklearn/scipy implementations produce identical results
to manual implementations for cosine similarity and Euclidean distance.
"""

import numpy as np
from scipy.spatial.distance import euclidean
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine


class TestCosineSimilarityMigration:
    """Tests for cosine similarity sklearn migration."""

    def test_single_pair_cosine_similarity(self):
        """Test that sklearn cosine_similarity produces same results as manual implementation."""
        # Create test embeddings
        np.random.seed(42)
        a = np.random.rand(384)
        b = np.random.rand(384)

        # BEFORE: Manual implementation
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        manual_similarity = float(dot_product / (norm_a * norm_b))

        # AFTER: sklearn implementation
        # sklearn expects 2D arrays (samples × features)
        sklearn_similarity = float(sklearn_cosine(a.reshape(1, -1), b.reshape(1, -1))[0, 0])

        # Should produce identical results (within floating-point precision)
        np.testing.assert_allclose(manual_similarity, sklearn_similarity, rtol=1e-7)

    def test_zero_vector_handling(self):
        """Test that zero vectors are handled correctly."""
        a = np.zeros(384)
        b = np.random.rand(384)

        # Manual implementation returns 0.0 for zero vectors
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            manual_result = 0.0
        else:
            manual_result = float(dot_product / (norm_a * norm_b))

        # sklearn will return 0.0 as well (dot product is 0)
        sklearn_result = float(sklearn_cosine(a.reshape(1, -1), b.reshape(1, -1))[0, 0])

        assert manual_result == 0.0
        np.testing.assert_allclose(manual_result, sklearn_result, rtol=1e-7)

    def test_batch_cosine_similarity(self):
        """Test that sklearn can efficiently compute pairwise similarities."""
        # Simulate find_similar_notes pattern
        np.random.seed(42)
        query_embedding = np.random.rand(384)
        embeddings = {f"note_{i}.md": np.random.rand(384) for i in range(100)}

        # BEFORE: Loop over embeddings (O(N) cosine computations)
        manual_similarities = []
        for note_path, embedding in embeddings.items():
            dot_product = np.dot(query_embedding, embedding)
            norm_a = np.linalg.norm(query_embedding)
            norm_b = np.linalg.norm(embedding)
            similarity = float(dot_product / (norm_a * norm_b))
            manual_similarities.append((note_path, similarity))

        manual_similarities.sort(key=lambda x: x[0])  # Sort by path for comparison

        # AFTER: sklearn batch computation
        paths = list(embeddings.keys())
        embedding_matrix = np.vstack([embeddings[p] for p in paths])
        # sklearn_cosine returns (1, N) matrix when comparing 1 query to N embeddings
        similarity_matrix = sklearn_cosine(query_embedding.reshape(1, -1), embedding_matrix)
        sklearn_similarities_array = similarity_matrix[0]
        sklearn_similarities = [
            (paths[i], float(sklearn_similarities_array[i])) for i in range(len(paths))
        ]
        sklearn_similarities.sort(key=lambda x: x[0])

        # Should produce identical results
        for (path1, sim1), (path2, sim2) in zip(manual_similarities, sklearn_similarities):
            assert path1 == path2
            np.testing.assert_allclose(sim1, sim2, rtol=1e-7)


class TestEuclideanDistanceMigration:
    """Tests for Euclidean distance scipy migration."""

    def test_euclidean_distance_equivalence(self):
        """Test that scipy.spatial.distance.euclidean matches np.linalg.norm."""
        np.random.seed(42)
        a = np.random.rand(384)
        b = np.random.rand(384)

        # BEFORE: Manual implementation
        manual_distance = np.linalg.norm(a - b)

        # AFTER: scipy implementation
        scipy_distance = euclidean(a, b)

        # Should produce identical results
        np.testing.assert_allclose(manual_distance, scipy_distance, rtol=1e-7)

    def test_euclidean_batch_computation(self):
        """Test batch Euclidean distance computation."""
        # Simulate hermeneutic_instability pattern
        np.random.seed(42)
        embeddings_array = np.random.rand(10, 384)  # 10 embeddings
        mean_embedding = np.mean(embeddings_array, axis=0)

        # BEFORE: List comprehension with np.linalg.norm
        manual_distances = [np.linalg.norm(emb - mean_embedding) for emb in embeddings_array]

        # AFTER: scipy in list comprehension (or vectorized)
        scipy_distances = [euclidean(emb, mean_embedding) for emb in embeddings_array]

        # Should produce identical results
        np.testing.assert_allclose(manual_distances, scipy_distances, rtol=1e-7)


class TestRedundantNormCaching:
    """Tests for caching redundant np.linalg.norm() calls."""

    def test_drift_vector_norm_caching(self):
        """Test that caching drift_vector norm produces same results."""
        # Simulate concept_drift.py pattern
        np.random.seed(42)
        first_emb = np.random.rand(384)
        last_emb = np.random.rand(384)
        drift_vector = last_emb - first_emb

        # Simulate 5 neighbour embeddings
        neighbor_embeddings = [np.random.rand(384) for _ in range(5)]

        # BEFORE: Redundant norm computation in loop (5 times)
        alignments_old = []
        for neighbor_emb in neighbor_embeddings:
            alignment = np.dot(drift_vector, neighbor_emb) / (
                np.linalg.norm(drift_vector) * np.linalg.norm(neighbor_emb)
            )
            alignments_old.append(alignment)

        # AFTER: Cache norm outside loop (1 time)
        drift_vector_norm = np.linalg.norm(drift_vector)
        alignments_new = []
        for neighbor_emb in neighbor_embeddings:
            alignment = np.dot(drift_vector, neighbor_emb) / (
                drift_vector_norm * np.linalg.norm(neighbor_emb)
            )
            alignments_new.append(alignment)

        # Should produce identical results
        np.testing.assert_allclose(alignments_old, alignments_new, rtol=1e-7)

    def test_norm_caching_with_zero_vector(self):
        """Test that cached norm handles zero vectors correctly."""
        drift_vector = np.zeros(384)
        neighbor_embeddings = [np.random.rand(384) for _ in range(3)]

        # BEFORE: Redundant computation
        alignments_old = []
        for neighbor_emb in neighbor_embeddings:
            norm_drift = np.linalg.norm(drift_vector)
            norm_neighbor = np.linalg.norm(neighbor_emb)
            if norm_drift == 0 or norm_neighbor == 0:
                alignment = 0.0
            else:
                alignment = np.dot(drift_vector, neighbor_emb) / (norm_drift * norm_neighbor)
            alignments_old.append(alignment)

        # AFTER: Cached norm
        drift_vector_norm = np.linalg.norm(drift_vector)
        alignments_new = []
        for neighbor_emb in neighbor_embeddings:
            norm_neighbor = np.linalg.norm(neighbor_emb)
            if drift_vector_norm == 0 or norm_neighbor == 0:
                alignment = 0.0
            else:
                alignment = np.dot(drift_vector, neighbor_emb) / (drift_vector_norm * norm_neighbor)
            alignments_new.append(alignment)

        # Should produce identical results
        np.testing.assert_allclose(alignments_old, alignments_new, rtol=1e-7)


class TestVectorizedOperations:
    """Tests for vectorized matrix operations."""

    def test_similarity_matrix_computation(self):
        """Test that sklearn can compute full similarity matrix efficiently."""
        # Simulate vault_context.py pattern for similarity matrices
        np.random.seed(42)
        embeddings = [np.random.rand(384) for _ in range(20)]
        embedding_matrix = np.vstack(embeddings)

        # BEFORE: Nested loops for similarity matrix
        n = len(embeddings)
        manual_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dot_product = np.dot(embeddings[i], embeddings[j])
                norm_i = np.linalg.norm(embeddings[i])
                norm_j = np.linalg.norm(embeddings[j])
                manual_matrix[i, j] = dot_product / (norm_i * norm_j)

        # AFTER: sklearn vectorized computation
        sklearn_matrix = sklearn_cosine(embedding_matrix)

        # Should produce identical results
        np.testing.assert_allclose(manual_matrix, sklearn_matrix, rtol=1e-6)
