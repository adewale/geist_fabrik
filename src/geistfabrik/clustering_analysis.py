"""Clustering analysis abstractions for GeistFabrik.

Provides session-scoped clustering with strategy swapping and centralized
cluster labeling. Single source of truth for clustering operations, avoiding
duplication across geists and enabling cluster-based analysis.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext


@dataclass
class Cluster:
    """Represents a semantic cluster of notes.

    Immutable representation of a cluster with its properties and members.
    """

    cluster_id: int
    label: str  # "keyword, list, here"
    formatted_label: str  # "Notes about keyword, list, and here"
    notes: List["Note"]
    size: int
    centroid: np.ndarray

    def contains(self, note: "Note") -> bool:
        """Check if note is in cluster.

        Args:
            note: Note to check

        Returns:
            True if note is in this cluster
        """
        return any(n.path == note.path for n in self.notes)

    def similarity_to_note(self, note: "Note", vault: "VaultContext") -> float:
        """Compute note's similarity to cluster centroid.

        Args:
            note: Note to compute similarity for
            vault: VaultContext for embedding access

        Returns:
            Cosine similarity to cluster centroid (0-1)
        """
        from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
            cosine_similarity as sklearn_cosine,
        )

        # Get note embedding from vault's current session
        cursor = vault.db.execute(
            """
            SELECT embedding FROM session_embeddings
            WHERE session_id = ? AND note_path = ?
            """,
            (vault.session.session_id, note.path),
        )
        row = cursor.fetchone()
        if row is None:
            return 0.0

        note_emb = np.frombuffer(row[0], dtype=np.float32)

        # Compute similarity to centroid
        similarity = sklearn_cosine(
            note_emb.reshape(1, -1), self.centroid.reshape(1, -1)
        )
        return float(similarity[0, 0])


class ClusterAnalyser:
    """Session-scoped clustering with strategy swapping.

    Single source of truth for clustering. Delegates labelling to
    cluster_labeling module to avoid circular dependencies with stats.py.

    Provides session-scoped caching so multiple geists can share
    clustering results without recomputation.

    Example:
        >>> analyser = ClusterAnalyser(vault, strategy="hdbscan", min_size=5)
        >>> clusters = analyser.get_clusters()
        >>> for cluster_id, cluster in clusters.items():
        ...     print(f"{cluster.formatted_label}: {cluster.size} notes")
    """

    def __init__(
        self,
        vault: "VaultContext",
        strategy: str = "hdbscan",
        min_size: int = 5,
    ):
        """Initialize clustering analyser.

        Args:
            vault: VaultContext
            strategy: "hdbscan", "kmeans", "agglomerative" (future)
            min_size: Minimum cluster size
        """
        self.vault = vault
        self.strategy = strategy
        self.min_size = min_size
        self._clusters_cache: Optional[Dict[int, Cluster]] = None

    def get_clusters(self) -> Dict[int, Cluster]:
        """Get clusters (cached per session).

        Uses cluster_labeling module for labelling to avoid circular
        dependency with stats.py.

        Returns:
            Dictionary mapping cluster_id to Cluster
        """
        if self._clusters_cache is not None:
            return self._clusters_cache

        # Run clustering based on strategy
        if self.strategy == "hdbscan":
            clusters = self._cluster_hdbscan()
        else:
            # Future strategies: kmeans, agglomerative
            clusters = self._cluster_hdbscan()  # Fallback to HDBSCAN

        self._clusters_cache = clusters
        return clusters

    def _cluster_hdbscan(self) -> Dict[int, Cluster]:
        """Run HDBSCAN clustering.

        Returns:
            Dictionary mapping cluster_id to Cluster
        """
        from geistfabrik import cluster_labeling

        # Import optional dependency
        try:
            from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
        except ImportError:
            return {}

        # Get all embeddings and paths for current session
        cursor = self.vault.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (self.vault.session.session_id,),
        )
        embeddings_dict = {}
        for row in cursor.fetchall():
            note_path, embedding_bytes = row
            embeddings_dict[note_path] = np.frombuffer(
                embedding_bytes, dtype=np.float32
            )

        if (
            len(embeddings_dict) < self.min_size * 2
        ):  # Need at least 2 clusters worth
            return {}

        paths = list(embeddings_dict.keys())
        embeddings_array = np.array([embeddings_dict[p] for p in paths])

        # Run HDBSCAN clustering
        clusterer = HDBSCAN(min_cluster_size=self.min_size, min_samples=3)
        labels = clusterer.fit_predict(embeddings_array)

        # Group notes by cluster
        clusters_notes: Dict[int, List[Note]] = {}
        cluster_paths: Dict[int, List[str]] = {}

        for i, label in enumerate(labels):
            if label == -1:  # Noise points
                continue
            if label not in clusters_notes:
                clusters_notes[label] = []
                cluster_paths[label] = []

            note = self.vault.get_note(paths[i])
            if note:
                clusters_notes[label].append(note)
                cluster_paths[label].append(paths[i])

        if not clusters_notes:
            return {}

        # Generate labels using cluster_labeling module
        labeling_method = self.vault.vault.config.clustering.labeling_method
        n_terms = self.vault.vault.config.clustering.n_label_terms

        if labeling_method == "keybert":
            cluster_labels_raw = cluster_labeling.label_keybert(
                paths, labels, self.vault.db, n_terms=n_terms
            )
        else:  # Default to tfidf
            cluster_labels_raw = cluster_labeling.label_tfidf(
                paths, labels, self.vault.db, n_terms=n_terms
            )

        # Build Cluster objects
        result: Dict[int, Cluster] = {}

        for cluster_id, notes in clusters_notes.items():
            # Get embeddings for this cluster
            cluster_embeddings = np.array(
                [embeddings_dict[path] for path in cluster_paths[cluster_id]]
            )

            # Calculate centroid (mean of embeddings)
            centroid = np.mean(cluster_embeddings, axis=0)

            # Format label as phrase
            keyword_label = cluster_labels_raw.get(
                cluster_id, f"Cluster {cluster_id}"
            )
            formatted_label = self._format_cluster_label(keyword_label)

            result[cluster_id] = Cluster(
                cluster_id=cluster_id,
                label=keyword_label,
                formatted_label=formatted_label,
                notes=notes,
                size=len(notes),
                centroid=centroid,
            )

        return result

    def _format_cluster_label(self, keyword_label: str) -> str:
        """Format keyword list as readable phrase.

        Args:
            keyword_label: Comma-separated keywords

        Returns:
            Formatted phrase template
        """
        terms = [t.strip() for t in keyword_label.split(",")]

        if len(terms) == 1:
            return f"Notes about {terms[0]}"
        elif len(terms) == 2:
            return f"Notes about {terms[0]} and {terms[1]}"
        else:
            # Oxford comma for 3+ terms
            return f"Notes about {', '.join(terms[:-1])}, and {terms[-1]}"

    def get_cluster_for_note(self, note: "Note") -> Optional[int]:
        """Get cluster ID for a note.

        Args:
            note: Note to find cluster for

        Returns:
            Cluster ID if note is in a cluster, None otherwise
        """
        clusters = self.get_clusters()

        for cluster_id, cluster in clusters.items():
            if cluster.contains(note):
                return cluster_id

        return None

    def get_representatives(self, cluster_id: int, k: int = 3) -> List["Note"]:
        """Get k most representative notes for cluster.

        Representative notes are those closest to the cluster centroid.

        Args:
            cluster_id: Cluster ID
            k: Number of representatives to return

        Returns:
            List of up to k most representative notes
        """
        clusters = self.get_clusters()

        if cluster_id not in clusters:
            return []

        cluster = clusters[cluster_id]

        # Compute similarity of each note to cluster centroid
        note_similarities = []
        for note in cluster.notes:
            sim = cluster.similarity_to_note(note, self.vault)
            note_similarities.append((note, sim))

        # Sort by similarity (descending)
        note_similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        return [note for note, _ in note_similarities[:k]]

    def compare_with_session(
        self, other_session_id: int
    ) -> Dict[str, Any]:
        """Compare current clustering with another session.

        This is a placeholder for future temporal cluster analysis.
        Would track cluster births, deaths, merges, and splits.

        Args:
            other_session_id: Session ID to compare with

        Returns:
            Dictionary with comparison metrics
        """
        # Future implementation: track cluster evolution
        # - New clusters (births)
        # - Disappeared clusters (deaths)
        # - Merged clusters
        # - Split clusters
        # - Migrated notes (changed cluster membership)
        return {
            "births": [],
            "deaths": [],
            "merges": [],
            "splits": [],
            "migrations": [],
        }
