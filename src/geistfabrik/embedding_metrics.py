"""Embedding metrics computation for GeistFabrik.

Extracted from stats.py to reduce module size. Computes advanced
embedding-based metrics including clustering, dimensionality,
and diversity scores.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np

from .config import MODEL_NAME
from .config_loader import GeistFabrikConfig
from .embeddings import cosine_similarity
from .sqlite_transaction import owned_transaction

# Optional dependencies for advanced metrics
try:
    from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
    from sklearn.metrics import silhouette_score  # type: ignore[import-untyped]
    from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
        cosine_similarity as sklearn_cosine,
    )

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    # Optional plugin APIs are discovered dynamically so core installations do
    # not require their packages or stubs. Values are validated where consumed.
    TwoNN = getattr(import_module("skdim.id"), "TwoNN")
    HAS_SKDIM = True
except (ImportError, AttributeError):
    HAS_SKDIM = False

try:
    vendi = import_module("vendi_score.vendi")
    HAS_VENDI = True
except ImportError:
    HAS_VENDI = False

logger = logging.getLogger(__name__)
# Bump when metric formulas, sampling, clustering, or labeling behavior changes.
METRICS_ALGORITHM_VERSION = 1


class EmbeddingMetricsComputer:
    """Computes advanced embedding-based metrics."""

    def __init__(self, db: sqlite3.Connection, config: GeistFabrikConfig | None = None):
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

        KeyBERT labeling is computed without persistent caching: its model loader
        can use external weights or return fallback labels, and currently exposes
        no artifact identity that could establish exact cache provenance.
        """
        if embeddings.ndim != 2 or len(paths) != len(embeddings):
            raise ValueError("Metrics require a matrix and one path per embedding")
        # Callers may retain and mutate their arrays while a worker computes.
        embeddings = embeddings.copy(order="C")
        paths = paths.copy()
        cacheable = self.config is None or self.config.clustering.labeling_method != "keybert"
        if cacheable:
            revision = self._database_revision()
            source_digest = self._source_digest(embeddings, paths)
            algorithm_digest = self._algorithm_digest()
            if not force_recompute:
                cached = self._load_cached_metrics(session_date, source_digest, algorithm_digest)
                if cached is not None:
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
        if cacheable:
            self._cache_metrics(session_date, source_digest, algorithm_digest, metrics, revision)

        return metrics

    def _database_revision(self) -> tuple[int, int]:
        """Observe external commits and writes on our own connection."""
        return int(self.db.execute("PRAGMA data_version").fetchone()[0]), self.db.total_changes

    def _source_digest(self, embeddings: np.ndarray, paths: list[str]) -> str:
        """Identify every ordered input, including the text used to label clusters."""

        def add_field(digest: Any, value: str) -> None:
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)

        # Both labelers consume the complete title but only the first 200
        # characters of content. Retain exactly that bounded input rather than
        # duplicating the entire vault in Python memory. SQLite's text substr()
        # stops at embedded NULs, unlike Python slicing, so rows are streamed and
        # sliced here to preserve the labelers' exact semantics.
        path_set = set(paths)
        label_inputs: dict[str, tuple[str, str]] = {}
        cursor = self.db.execute("SELECT path, title, content FROM notes")
        try:
            for path, title, content in cursor:
                if path in path_set:
                    label_inputs[path] = (title, content[:200])
                # Keep peak memory proportional to one source row, not the sum
                # of every full note returned by the statement.
                del content
        finally:
            cursor.close()
        digest = hashlib.sha256()
        add_field(digest, embeddings.dtype.str)
        add_field(digest, json.dumps(embeddings.shape))
        for path in paths:
            add_field(digest, path)
            label_input = label_inputs.get(path)
            digest.update(b"\x00" if label_input is None else b"\x01")
            if label_input is not None:
                add_field(digest, str(label_input[0]))
                add_field(digest, str(label_input[1]))
        digest.update(embeddings.tobytes(order="C"))
        return digest.hexdigest()

    def _algorithm_digest(self) -> str:
        """Include configuration and optional implementations that affect results."""
        dependencies: dict[str, str | None] = {}
        for package in (
            "numpy",
            "scipy",
            "scikit-learn",
            "scikit-dimension",
            "vendi-score",
            "sentence-transformers",
            "transformers",
            "torch",
        ):
            try:
                dependencies[package] = version(package)
            except PackageNotFoundError:
                dependencies[package] = None
        identity = {
            "version": METRICS_ALGORITHM_VERSION,
            "labeling_method": self.config.clustering.labeling_method if self.config else "tfidf",
            "n_label_terms": self.config.clustering.n_label_terms if self.config else 4,
            "labeling_model": MODEL_NAME,
            "capabilities": [HAS_SKLEARN, HAS_SKDIM, HAS_VENDI],
            "dependencies": dependencies,
        }
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()

    def _load_cached_metrics(
        self, session_date: str, source_digest: str, algorithm_digest: str
    ) -> dict[str, Any] | None:
        """Read only the result for these exact source and algorithm versions."""
        row = self.db.execute(
            """SELECT metrics_json FROM embedding_metrics
               WHERE session_date = ? AND source_digest = ? AND algorithm_digest = ?""",
            (session_date, source_digest, algorithm_digest),
        ).fetchone()
        if row is None:
            return None
        cached: dict[str, Any] = json.loads(row[0])
        if cached.get("cluster_labels"):
            cached["cluster_labels"] = {int(k): v for k, v in cached["cluster_labels"].items()}
        return cached

    def _cache_metrics(
        self,
        session_date: str,
        source_digest: str,
        algorithm_digest: str,
        metrics: dict[str, Any],
        revision: tuple[int, int],
    ) -> None:
        """Version derived results; a slow old worker never replaces a newer snapshot."""

        def to_python_type(val: Any) -> Any:
            if isinstance(val, np.generic):
                return val.item()
            raise TypeError(f"Cannot serialize metric value of type {type(val).__name__}")

        with owned_transaction(self.db, "EmbeddingMetricsComputer._cache_metrics"):
            # Labeling reads note text during computation. Any intervening commit
            # may have changed that input (including an ABA change); do not cache
            # an output whose label snapshot cannot be established.
            if (
                revision != self._database_revision()
                or algorithm_digest != self._algorithm_digest()
            ):
                return
            self.db.execute(
                """
                INSERT INTO embedding_metrics
                (session_date, source_digest, algorithm_digest, metrics_json, computed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_date, source_digest, algorithm_digest) DO UPDATE SET
                    metrics_json = excluded.metrics_json,
                    computed_at = excluded.computed_at
                """,
                (
                    session_date,
                    source_digest,
                    algorithm_digest,
                    json.dumps(metrics, default=to_python_type),
                    datetime.now().isoformat(),
                ),
            )

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
        # Single source of truth: delegate to the shared cluster_labeling
        # module (previously this was a line-for-line copy of label_tfidf).
        from .cluster_labeling import label_tfidf

        return label_tfidf(paths, labels, self.db, n_terms=n_terms)

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
        # Single source of truth: delegate to the shared cluster_labeling
        # module (previously this was a line-for-line copy of label_keybert).
        from .cluster_labeling import label_keybert

        return label_keybert(paths, labels, self.db, n_terms=n_terms)
