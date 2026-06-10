"""Embedding metrics computation for GeistFabrik.

Extracted from stats.py to reduce module size. Computes advanced
embedding-based metrics including clustering, dimensionality,
and diversity scores.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

import numpy as np

from .embeddings import cosine_similarity

# Optional dependencies for advanced metrics
try:
    from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
    from sklearn.metrics import silhouette_score  # type: ignore[import-untyped]
    from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
        cosine_similarity as sklearn_cosine,
    )

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from skdim.id import TwoNN  # type: ignore

    HAS_SKDIM = True
except ImportError:
    HAS_SKDIM = False

try:
    from vendi_score import vendi  # type: ignore

    HAS_VENDI = True
except ImportError:
    HAS_VENDI = False

logger = logging.getLogger(__name__)


class EmbeddingMetricsComputer:
    """Computes advanced embedding-based metrics."""

    def __init__(self, db: sqlite3.Connection, config: Any = None):
        """Initialise metrics computer.

        Args:
            db: SQLite database connection
            config: Optional configuration object
        """
        self.db = db
        self.config = config

    def compute_metrics(
        self,
        session_date: str,
        embeddings: np.ndarray,
        paths: list[str],
        force_recompute: bool = False,
    ) -> dict[str, Any]:
        """Compute and cache embedding metrics.

        Args:
            session_date: Session date (YYYY-MM-DD)
            embeddings: Embedding matrix (n_notes, dim)
            paths: Note paths corresponding to embeddings
            force_recompute: Force recomputation even if cached

        Returns:
            Dictionary of computed metrics
        """
        # Check cache first
        if not force_recompute:
            cached = self._load_cached_metrics(session_date)
            if cached:
                # Always include dimension and n_notes from current embeddings
                # (these are not cached because they can change)
                cached["n_notes"] = len(embeddings)
                cached["dimension"] = embeddings.shape[1]
                cached["session_date"] = session_date
                return cached

        # Compute metrics
        metrics: dict[str, Any] = {
            "session_date": session_date,
            "n_notes": len(embeddings),
            "dimension": embeddings.shape[1],
        }

        # Basic metrics (always available)
        metrics.update(self._compute_basic_metrics(embeddings))

        # Advanced metrics (require sklearn)
        if HAS_SKLEARN:
            metrics.update(self._compute_clustering_metrics(embeddings, paths))
        else:
            metrics["clustering_available"] = False

        # Cache results
        self._cache_metrics(session_date, metrics)

        return metrics

    def _load_cached_metrics(self, session_date: str) -> dict[str, Any] | None:
        """Load cached metrics from database."""
        cursor = self.db.execute(
            "SELECT * FROM embedding_metrics WHERE session_date = ?", (session_date,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Convert row to dict
        columns = [desc[0] for desc in cursor.description]
        cached = dict(zip(columns, row))

        # Parse cluster_labels JSON and convert string keys back to int
        if cached.get("cluster_labels"):
            cluster_labels_raw = json.loads(cached["cluster_labels"])
            # JSON converts int keys to strings, convert them back
            cached["cluster_labels"] = {int(k): v for k, v in cluster_labels_raw.items()}

        # Ensure integer fields are actually integers (SQLite sometimes returns blobs)
        for key in ["n_clusters", "n_gaps"]:
            if key in cached and cached[key] is not None:
                try:
                    # Handle both regular ints and blobs (numpy int serialization)
                    if isinstance(cached[key], bytes):
                        # Blob from numpy int - use struct to unpack
                        import struct

                        cached[key] = struct.unpack("<q", cached[key])[0]  # little-endian int64
                    else:
                        cached[key] = int(cached[key])
                except (TypeError, ValueError, struct.error):
                    # If conversion fails, set to None rather than keeping invalid data
                    cached[key] = None

        return cached

    def _cache_metrics(self, session_date: str, metrics: dict[str, Any]) -> None:
        """Cache computed metrics to database."""
        # Serialise cluster_labels to JSON (keys already converted to Python int)
        cluster_labels_json = json.dumps(metrics.get("cluster_labels", {}))

        # Convert numpy types to Python types for SQLite
        def to_python_type(val: Any) -> Any:
            if val is None:
                return None
            if isinstance(val, (np.integer, np.int64, np.int32)):
                return int(val)
            if isinstance(val, (np.floating, np.float64, np.float32)):
                return float(val)
            return val

        self.db.execute(
            """
            INSERT OR REPLACE INTO embedding_metrics
            (session_date, intrinsic_dim, vendi_score, shannon_entropy,
             silhouette_score, n_clusters, n_gaps, cluster_labels, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_date,
                to_python_type(metrics.get("intrinsic_dim")),
                to_python_type(metrics.get("vendi_score")),
                to_python_type(metrics.get("shannon_entropy")),
                to_python_type(metrics.get("silhouette_score")),
                to_python_type(metrics.get("n_clusters")),
                to_python_type(metrics.get("n_gaps")),
                cluster_labels_json,
                datetime.now().isoformat(),
            ),
        )
        self.db.commit()

    def _compute_basic_metrics(self, embeddings: np.ndarray) -> dict[str, Any]:
        """Compute basic metrics that don't require external libraries."""
        metrics: dict[str, Any] = {}

        # Intrinsic dimensionality (if available)
        if HAS_SKDIM and len(embeddings) >= 10:
            try:
                id_estimator = TwoNN()
                intrinsic_dim = id_estimator.fit_transform(embeddings)
                metrics["intrinsic_dim"] = round(float(intrinsic_dim), 1)
            except Exception:
                # TwoNN can fail on some data distributions
                logger.debug("TwoNN estimation failed", exc_info=True)

        # Vendi Score (if available)
        if HAS_VENDI and HAS_SKLEARN and len(embeddings) >= 2:
            try:
                # Compute similarity matrix for Vendi Score
                similarity_matrix = sklearn_cosine(embeddings)
                vendi_score_value = vendi.score_K(similarity_matrix)
                metrics["vendi_score"] = round(float(vendi_score_value), 1)
            except Exception:
                # Vendi computation can fail
                logger.debug("Vendi score computation failed", exc_info=True)

        # IsoScore: measure of embedding space uniformity
        # Based on variance in the eigenvalues of the covariance matrix
        if len(embeddings) >= 10:
            try:
                # Compute covariance matrix
                cov_matrix = np.cov(embeddings.T)
                eigenvalues = np.linalg.eigvalsh(cov_matrix)
                eigenvalues = eigenvalues[eigenvalues > 1e-10]  # Filter near-zero

                if len(eigenvalues) > 0:
                    # IsoScore: normalise eigenvalues and compute entropy
                    eigenvalues_norm = eigenvalues / eigenvalues.sum()
                    entropy = -np.sum(eigenvalues_norm * np.log(eigenvalues_norm + 1e-10))
                    max_entropy = np.log(len(eigenvalues))
                    isoscore = entropy / max_entropy if max_entropy > 0 else 0
                    metrics["isoscore"] = round(float(isoscore), 2)
            except Exception:
                # Eigenvalue computation can fail
                logger.debug("IsoScore computation failed", exc_info=True)

        # Basic similarity statistics
        # Sample for efficiency if large
        if len(embeddings) > 1000:
            indices = np.random.choice(len(embeddings), 1000, replace=False)
            sample_embeddings = embeddings[indices]
        else:
            sample_embeddings = embeddings

        # Compute similarity matrix (vectorized for performance)
        if HAS_SKLEARN and len(sample_embeddings) > 1:
            # Use sklearn's vectorized cosine_similarity (~100x faster)
            similarity_matrix_sim = sklearn_cosine(sample_embeddings)
            # Extract upper triangle (excluding diagonal)
            similarities = similarity_matrix_sim[np.triu_indices_from(similarity_matrix_sim, k=1)]

            metrics["avg_similarity"] = float(np.mean(similarities))
            metrics["std_similarity"] = float(np.std(similarities))
        elif len(sample_embeddings) > 1:
            # Fallback to manual computation if sklearn not available
            similarities_list = []
            for i in range(len(sample_embeddings)):
                for j in range(i + 1, len(sample_embeddings)):
                    sim = cosine_similarity(sample_embeddings[i], sample_embeddings[j])
                    similarities_list.append(sim)

            if similarities_list:
                metrics["avg_similarity"] = float(np.mean(similarities_list))
                metrics["std_similarity"] = float(np.std(similarities_list))

        return metrics

    def _compute_clustering_metrics(
        self, embeddings: np.ndarray, paths: list[str]
    ) -> dict[str, Any]:
        """Compute clustering-based metrics (requires sklearn)."""
        metrics: dict[str, Any] = {}

        # Run HDBSCAN clustering
        clusterer = HDBSCAN(min_cluster_size=5, min_samples=3)
        labels = clusterer.fit_predict(embeddings)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = np.sum(labels == -1)

        metrics["n_clusters"] = n_clusters
        metrics["n_gaps"] = n_noise
        metrics["gap_pct"] = round(n_noise / len(labels) * 100, 1) if len(labels) > 0 else 0

        # Silhouette score (only if we have clusters)
        if n_clusters > 1:
            # Filter out noise points for silhouette calculation
            mask = labels != -1
            if np.sum(mask) > 1:
                silhouette = silhouette_score(embeddings[mask], labels[mask])
                metrics["silhouette_score"] = round(float(silhouette), 3)

        # Shannon entropy of cluster distribution
        if n_clusters > 0:
            cluster_counts = np.bincount(labels[labels >= 0])
            cluster_dist = cluster_counts / cluster_counts.sum()
            shannon = -np.sum(cluster_dist * np.log2(cluster_dist + 1e-10))
            metrics["shannon_entropy"] = round(float(shannon), 2)

        # Label clusters using configured method (or default to tfidf if no config)
        if n_clusters > 0:
            if self.config:
                labeling_method = self.config.clustering.labeling_method
                n_terms = self.config.clustering.n_label_terms
            else:
                # Default to tfidf if no config provided (backwards compatibility)
                labeling_method = "tfidf"
                n_terms = 4

            if labeling_method == "keybert":
                cluster_labels = self._label_clusters_keybert(paths, labels, n_terms=n_terms)
            else:
                cluster_labels = self._label_clusters_tfidf(paths, labels, n_terms=n_terms)
            # Convert numpy.int64 keys to Python int for JSON serialization
            metrics["cluster_labels"] = {int(k): v for k, v in cluster_labels.items()}

        return metrics

    def _apply_mmr_filtering(
        self,
        terms: list[str],
        tfidf_scores: np.ndarray,
        lambda_param: float = 0.5,
        k: int = 4,
    ) -> list[str]:
        """Apply Maximal Marginal Relevance to select diverse terms.

        Thin wrapper around the shared cluster_labeling.apply_mmr implementation
        so the MMR algorithm lives in a single place (previously this logic was
        duplicated here and in cluster_labeling). See apply_mmr for details.
        """
        from .cluster_labeling import apply_mmr

        return apply_mmr(terms, tfidf_scores, lambda_param=lambda_param, k=k)

    def _label_clusters_tfidf(
        self, paths: list[str], labels: np.ndarray, n_terms: int = 4
    ) -> dict[int, str]:
        """Generate cluster labels using c-TF-IDF with MMR filtering.

        Args:
            paths: Note paths
            labels: Cluster labels
            n_terms: Number of terms to use in final label (after MMR)

        Returns:
            Dictionary mapping cluster_id to label string
        """
        cluster_labels: dict[int, str] = {}

        # Load note titles/content for each cluster
        clusters: dict[int, list[str]] = {}
        for i, label in enumerate(labels):
            if label == -1:
                continue
            if label not in clusters:
                clusters[label] = []

            # Get note title from path
            path = paths[i]
            cursor = self.db.execute("SELECT title, content FROM notes WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                title, content = row
                # Use title + first 200 chars of content
                text = f"{title} {content[:200]}"
                clusters[label].append(text)

        if not clusters:
            return {}

        # Concatenate all text per cluster
        cluster_texts = {cid: " ".join(texts) for cid, texts in clusters.items()}

        # Compute TF-IDF
        vectorizer = TfidfVectorizer(max_features=100, stop_words="english", ngram_range=(1, 2))

        try:
            tfidf_matrix = vectorizer.fit_transform(cluster_texts.values())
            feature_names = vectorizer.get_feature_names_out()

            # Extract top terms per cluster with MMR filtering
            for i, cluster_id in enumerate(cluster_texts.keys()):
                cluster_vector = tfidf_matrix[i].toarray()[0]

                # Extract top 8 candidates before MMR filtering
                n_candidates = min(8, len(feature_names))
                top_indices = cluster_vector.argsort()[-n_candidates:][::-1]
                candidate_terms = [feature_names[idx] for idx in top_indices]
                candidate_scores = cluster_vector[top_indices]

                # Apply MMR to select diverse subset
                diverse_terms = self._apply_mmr_filtering(
                    candidate_terms, candidate_scores, lambda_param=0.5, k=n_terms
                )

                cluster_labels[cluster_id] = ", ".join(diverse_terms)
        except Exception:
            # If TF-IDF fails, use simple fallback
            logger.debug(
                "TF-IDF cluster labeling failed",
                exc_info=True,
            )
            for cluster_id in clusters.keys():
                cluster_labels[cluster_id] = f"Cluster {cluster_id}"

        return cluster_labels

    def _label_clusters_keybert(
        self, paths: list[str], labels: np.ndarray, n_terms: int = 4
    ) -> dict[int, str]:
        """Generate cluster labels using KeyBERT approach with semantic embeddings.

        Args:
            paths: Note paths
            labels: Cluster labels
            n_terms: Number of terms to use in final label (after MMR)

        Returns:
            Dictionary mapping cluster_id to label string
        """
        from .embeddings import EmbeddingComputer

        cluster_labels: dict[int, str] = {}

        # Load note titles/content for each cluster
        clusters: dict[int, list[str]] = {}
        for i, label in enumerate(labels):
            if label == -1:
                continue
            if label not in clusters:
                clusters[label] = []

            # Get note title and content
            path = paths[i]
            cursor = self.db.execute("SELECT title, content FROM notes WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                title, content = row
                # Use title + first 200 chars of content
                text = f"{title} {content[:200]}"
                clusters[label].append(text)

        if not clusters:
            return {}

        # Get embedding computer (lazy-load model)
        try:
            computer = EmbeddingComputer()
        except Exception:
            # If model loading fails, fall back to simple labels for all clusters
            logger.debug(
                "Model loading failed for KeyBERT labeling",
                exc_info=True,
            )
            return {cid: f"Cluster {cid}" for cid in clusters.keys()}

        # Get cluster embeddings to compute centroids
        cluster_embeddings: dict[int, list[np.ndarray]] = {}
        for cluster_id, texts in clusters.items():
            try:
                # Embed all texts in this cluster
                embeddings = computer.compute_batch_semantic(texts)
                cluster_embeddings[cluster_id] = list(embeddings)
            except Exception:
                # If embedding fails for this cluster, skip to simple label
                logger.debug(
                    "Embedding failed for cluster %d",
                    cluster_id,
                    exc_info=True,
                )
                cluster_labels[cluster_id] = f"Cluster {cluster_id}"

        # Process each cluster
        for cluster_id, texts in clusters.items():
            # Skip if embedding failed earlier
            if cluster_id in cluster_labels:
                continue
            # Concatenate all text for n-gram extraction
            cluster_text = " ".join(texts)

            # Compute cluster centroid
            centroid = np.mean(cluster_embeddings[cluster_id], axis=0)

            # Extract candidate phrases using TF-IDF to get good candidates
            vectorizer = TfidfVectorizer(max_features=100, stop_words="english", ngram_range=(1, 3))
            try:
                # Fit on this cluster's text only
                tfidf_matrix = vectorizer.fit_transform([cluster_text])
                feature_names = vectorizer.get_feature_names_out()
                cluster_vector = tfidf_matrix[0].toarray()[0]

                # Get top 16 candidates by TF-IDF
                n_candidates = min(16, len(feature_names))
                top_indices = cluster_vector.argsort()[-n_candidates:][::-1]
                candidate_terms = [feature_names[idx] for idx in top_indices]

                # Skip if no candidates
                if not candidate_terms:
                    cluster_labels[cluster_id] = f"Cluster {cluster_id}"
                    continue

                # Embed candidate phrases
                candidate_embs = computer.compute_batch_semantic(candidate_terms)

                # Compute semantic similarity to cluster centroid
                centroid_2d = centroid.reshape(1, -1)
                similarities = sklearn_cosine(centroid_2d, candidate_embs)[0]

                # Apply MMR with semantic scores
                diverse_terms = self._apply_mmr_filtering(
                    candidate_terms, similarities, lambda_param=0.5, k=n_terms
                )

                cluster_labels[cluster_id] = ", ".join(diverse_terms)

            except Exception:
                # If KeyBERT approach fails, use simple fallback
                logger.debug(
                    "KeyBERT labeling failed for cluster %d",
                    cluster_id,
                    exc_info=True,
                )
                cluster_labels[cluster_id] = f"Cluster {cluster_id}"

        return cluster_labels
