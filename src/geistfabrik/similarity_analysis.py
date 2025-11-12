"""Similarity analysis abstractions for GeistFabrik.

Provides semantic threshold naming, similarity profiling, and declarative
filtering for note similarity operations. Replaces ad-hoc magic numbers
(0.6, 0.5, 0.7) with named constants and reusable patterns.
"""

from typing import TYPE_CHECKING, List, Optional

import numpy as np

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext


class SimilarityLevel:
    """Semantic names for similarity thresholds.

    Provides consistent vocabulary across geists for describing semantic
    similarity ranges. Using named constants improves code readability and
    enables systematic threshold tuning (change the constant once to affect
    all geists).

    Values are tuned based on empirical observation of sentence-transformers
    (all-MiniLM-L6-v2) embeddings in Obsidian vaults.
    """

    VERY_HIGH = 0.80  # Almost identical semantically (near-duplicates)
    HIGH = 0.65  # Clearly related concepts (bridge candidates)
    MODERATE = 0.50  # Meaningfully connected (thematic overlap)
    WEAK = 0.35  # Tangentially related (shared context)
    NOISE = 0.15  # Mostly unrelated (random similarity)


class SimilarityProfile:
    """Analyzes a note's similarity distribution against candidates.

    Provides statistical operations on similarity scores: counting, percentiles,
    structural role detection (hub, bridge). Enables reasoning about a note's
    semantic position in the vault without manual similarity computation loops.

    Example:
        >>> profile = SimilarityProfile(vault, note)
        >>> if profile.is_hub(threshold=SimilarityLevel.HIGH, min_count=10):
        ...     print(f"{note.title} is a semantic hub")
    """

    def __init__(
        self, vault: "VaultContext", note: "Note", candidates: Optional[List["Note"]] = None
    ):
        """Initialize similarity profile for a note against candidates.

        Args:
            vault: VaultContext for similarity computations
            note: Note to analyze
            candidates: Notes to compute similarity against (default: all notes)
        """
        self.vault = vault
        self.note = note
        self.candidates = candidates if candidates is not None else vault.notes()
        self._similarities_cache: Optional[List[float]] = None

    def _get_similarities(self) -> List[float]:
        """Compute similarities to all candidates (cached).

        Returns:
            List of similarity scores (excludes self-similarity)
        """
        if self._similarities_cache is None:
            similarities = []
            for candidate in self.candidates:
                if candidate.path != self.note.path:  # Exclude self
                    sim = self.vault.similarity(self.note, candidate)
                    similarities.append(sim)
            self._similarities_cache = similarities
        return self._similarities_cache

    def count_above(self, threshold: float) -> int:
        """Count candidates with similarity >= threshold.

        Args:
            threshold: Minimum similarity (0-1)

        Returns:
            Number of candidates meeting threshold
        """
        similarities = self._get_similarities()
        return sum(1 for sim in similarities if sim >= threshold)

    def count_in_range(self, min_sim: float, max_sim: float) -> int:
        """Count candidates with similarity in [min_sim, max_sim].

        Args:
            min_sim: Minimum similarity (inclusive)
            max_sim: Maximum similarity (inclusive)

        Returns:
            Number of candidates in range
        """
        similarities = self._get_similarities()
        return sum(1 for sim in similarities if min_sim <= sim <= max_sim)

    def percentile(self, p: float) -> float:
        """Get pth percentile of similarity distribution.

        Args:
            p: Percentile (0-100)

        Returns:
            Similarity value at pth percentile
        """
        similarities = self._get_similarities()
        if not similarities:
            return 0.0
        return float(np.percentile(similarities, p))

    def is_hub(self, threshold: float = SimilarityLevel.HIGH, min_count: int = 10) -> bool:
        """Check if note has many high-similarity neighbors (hub pattern).

        A hub is a note that is highly similar to many other notes, indicating
        it's a central concept or synthesizer in the vault.

        Args:
            threshold: Minimum similarity to be considered a neighbor
            min_count: Minimum number of high-similarity neighbors to be a hub

        Returns:
            True if note is a hub
        """
        return self.count_above(threshold) >= min_count

    def is_bridge(
        self, threshold: float = SimilarityLevel.HIGH, unlinked_only: bool = True
    ) -> bool:
        """Check if note connects unlinked high-similarity notes.

        A bridge is a note that is highly similar to other notes that aren't
        directly linked to each other, indicating it connects disparate parts
        of the vault.

        Args:
            threshold: Minimum similarity for bridge connections
            unlinked_only: If True, only consider unlinked candidates

        Returns:
            True if note acts as a bridge
        """
        # Get high-similarity candidates
        high_sim_candidates = []
        for candidate in self.candidates:
            if candidate.path == self.note.path:
                continue
            sim = self.vault.similarity(self.note, candidate)
            if sim >= threshold:
                high_sim_candidates.append(candidate)

        if len(high_sim_candidates) < 2:
            return False  # Need at least 2 candidates to bridge

        if unlinked_only:
            # Check if any pair of high-sim candidates are unlinked
            for i, note_a in enumerate(high_sim_candidates):
                for note_b in high_sim_candidates[i + 1 :]:
                    # Check if note_a and note_b are linked
                    a_links = {link.target for link in note_a.links}
                    b_links = {link.target for link in note_b.links}

                    # Not linked if neither links to the other
                    if note_b.title not in a_links and note_a.title not in b_links:
                        return True  # Found unlinked pair
            return False
        else:
            # Just need 2+ high-similarity candidates (no link check)
            return True


class SimilarityFilter:
    """Declarative filtering on similarity.

    Provides composable filters for finding notes by similarity criteria.
    Replaces manual similarity computation loops with named operations.

    Example:
        >>> filter = SimilarityFilter(vault)
        >>> # Notes similar to topic A or B, but not C
        >>> candidates = filter.filter_similar_to_any([note_a, note_b], all_notes)
        >>> candidates = filter.filter_dissimilar_to_all([note_c], candidates)
    """

    def __init__(self, vault: "VaultContext"):
        """Initialize similarity filter with vault context.

        Args:
            vault: VaultContext for similarity computations
        """
        self.vault = vault

    def filter_by_range(
        self,
        source: "Note",
        candidates: List["Note"],
        min_sim: float,
        max_sim: float,
    ) -> List["Note"]:
        """Filter candidates by similarity range to source.

        Args:
            source: Source note to compare against
            candidates: Candidate notes to filter
            min_sim: Minimum similarity (inclusive)
            max_sim: Maximum similarity (inclusive)

        Returns:
            Candidates with similarity in [min_sim, max_sim]
        """
        result = []
        for candidate in candidates:
            if candidate.path == source.path:
                continue  # Skip self
            sim = self.vault.similarity(source, candidate)
            if min_sim <= sim <= max_sim:
                result.append(candidate)
        return result

    def filter_similar_to_any(
        self,
        anchors: List["Note"],
        candidates: List["Note"],
        threshold: float = SimilarityLevel.MODERATE,
    ) -> List["Note"]:
        """Find candidates similar to ANY anchor (union).

        Returns candidates that are similar to at least one anchor note.

        Args:
            anchors: Anchor notes to compare against
            candidates: Candidate notes to filter
            threshold: Minimum similarity to any anchor

        Returns:
            Candidates similar to at least one anchor
        """
        result = []
        for candidate in candidates:
            # Skip if candidate is one of the anchors
            if any(candidate.path == anchor.path for anchor in anchors):
                continue

            # Check if similar to any anchor
            for anchor in anchors:
                sim = self.vault.similarity(candidate, anchor)
                if sim >= threshold:
                    result.append(candidate)
                    break  # Found match, no need to check other anchors

        return result

    def filter_similar_to_all(
        self,
        anchors: List["Note"],
        candidates: List["Note"],
        threshold: float = SimilarityLevel.MODERATE,
    ) -> List["Note"]:
        """Find candidates similar to ALL anchors (intersection).

        Returns candidates that are similar to every anchor note. Useful for
        finding notes that bridge multiple topics.

        Args:
            anchors: Anchor notes to compare against
            candidates: Candidate notes to filter
            threshold: Minimum similarity to each anchor

        Returns:
            Candidates similar to all anchors
        """
        if not anchors:
            return []

        result = []
        for candidate in candidates:
            # Skip if candidate is one of the anchors
            if any(candidate.path == anchor.path for anchor in anchors):
                continue

            # Check if similar to all anchors
            similar_to_all = True
            for anchor in anchors:
                sim = self.vault.similarity(candidate, anchor)
                if sim < threshold:
                    similar_to_all = False
                    break

            if similar_to_all:
                result.append(candidate)

        return result

    def filter_dissimilar_to_all(
        self,
        anchors: List["Note"],
        candidates: List["Note"],
        max_sim: float = SimilarityLevel.WEAK,
    ) -> List["Note"]:
        """Find candidates dissimilar to ALL anchors.

        Returns candidates that are dissimilar to every anchor note. Useful
        for finding contrarian or unrelated notes.

        Args:
            anchors: Anchor notes to compare against
            candidates: Candidate notes to filter
            max_sim: Maximum similarity to any anchor (exclusive)

        Returns:
            Candidates dissimilar to all anchors
        """
        if not anchors:
            return candidates

        result = []
        for candidate in candidates:
            # Skip if candidate is one of the anchors
            if any(candidate.path == anchor.path for anchor in anchors):
                continue

            # Check if dissimilar to all anchors
            dissimilar_to_all = True
            for anchor in anchors:
                sim = self.vault.similarity(candidate, anchor)
                if sim >= max_sim:
                    dissimilar_to_all = False
                    break

            if dissimilar_to_all:
                result.append(candidate)

        return result
