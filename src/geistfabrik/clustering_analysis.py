"""Clustering analysis abstractions for GeistFabrik.

Provides session-scoped clustering with strategy swapping and centralized
cluster labeling. Single source of truth for clustering operations, avoiding
duplication across geists and enabling cluster-based analysis.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    notes: list["Note"]
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

        # Get note embedding via public accessor
        note_emb = vault.get_embedding(note.path)
        if note_emb is None:
            return 0.0

        # Compute similarity to centroid
        similarity = sklearn_cosine(note_emb.reshape(1, -1), self.centroid.reshape(1, -1))
        return float(similarity[0, 0])


def format_cluster_label(keyword_label: str) -> str:
    """Format keyword list as readable phrase.

    This is the single source of truth for cluster label formatting.
    Used by both VaultContext.get_clusters() and ClusterAnalyser.

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
        min_size: int | None = None,
    ):
        """Initialize clustering analyser.

        Args:
            vault: VaultContext
            strategy: "hdbscan", "kmeans", "agglomerative" (future)
            min_size: Minimum cluster size; defaults to the vault configuration
        """
        self.vault = vault
        self.strategy = strategy
        self.min_size = min_size

    def get_clusters(self) -> dict[int, Cluster]:
        """Get clusters (cached per session).

        Uses cluster_labeling module for labelling to avoid circular
        dependency with stats.py.

        Returns:
            Dictionary mapping cluster_id to Cluster
        """
        # Run clustering based on strategy
        if self.strategy == "hdbscan":
            clusters = self._cluster_hdbscan()
        else:
            # Future strategies: kmeans, agglomerative
            clusters = self._cluster_hdbscan()  # Fallback to HDBSCAN

        return clusters

    def _cluster_hdbscan(self) -> dict[int, Cluster]:
        """Use the context's canonical clustering, cache, and history writer."""
        return self.vault.get_clusters(min_size=self.min_size)

    def get_cluster_for_note(self, note: "Note") -> int | None:
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

    def get_representatives(self, cluster_id: int, k: int = 3) -> list["Note"]:
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
