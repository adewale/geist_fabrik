"""Temporal analysis abstractions for GeistFabrik.

Provides tools for analyzing how note embeddings evolve across sessions.
Tracks semantic trajectories, drift patterns, and temporal relationships
between notes.

This module extracts the recurring pattern from temporal geists (concept_drift,
convergent_evolution, divergent_evolution, burst_evolution) into reusable
components.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
    cosine_similarity as sklearn_cosine,
)

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext


class EmbeddingTrajectoryCalculator:
    """Calculates how a note's embedding evolves across sessions.

    Provides uniform API for temporal analysis patterns. Handles session
    history queries, embedding reconstruction, and drift computation with
    caching for efficiency.

    Example:
        >>> calc = EmbeddingTrajectoryCalculator(vault, note)
        >>> drift = calc.total_drift()
        >>> if drift > 0.2:
        ...     print(f"Note has drifted significantly: {drift:.2f}")
    """

    def __init__(
        self,
        vault: "VaultContext",
        note: "Note",
        sessions: Optional[List[int]] = None,
    ):
        """Initialize trajectory calculator for a note.

        Args:
            vault: VaultContext with session history
            note: Note to track
            sessions: Optional specific session IDs (default: all available)
        """
        self.vault = vault
        self.note = note
        self.sessions = sessions or self._get_available_sessions()
        self._snapshots_cache: Optional[List[Tuple[datetime, np.ndarray]]] = None

    def _get_available_sessions(self) -> List[int]:
        """Get all available session IDs from database.

        Returns:
            List of session IDs ordered by date
        """
        cursor = self.vault.db.execute(
            "SELECT session_id FROM sessions ORDER BY session_date ASC"
        )
        return [row[0] for row in cursor.fetchall()]

    def snapshots(self) -> List[Tuple[datetime, np.ndarray]]:
        """Get (date, embedding) for all sessions containing this note.

        Returns:
            List of (session_date, embedding) tuples ordered by date
        """
        if self._snapshots_cache is None:
            self._snapshots_cache = self._load_snapshots()
        return self._snapshots_cache

    def _load_snapshots(self) -> List[Tuple[datetime, np.ndarray]]:
        """Load embedding snapshots from database.

        Returns:
            List of (session_date, embedding) tuples
        """
        snapshots = []

        # Get session info
        cursor = self.vault.db.execute(
            """
            SELECT session_id, session_date FROM sessions
            ORDER BY session_date ASC
            """
        )
        sessions = cursor.fetchall()

        # Load embeddings for each session
        for session_id, session_date in sessions:
            if self.sessions and session_id not in self.sessions:
                continue

            cursor = self.vault.db.execute(
                """
                SELECT embedding FROM session_embeddings
                WHERE session_id = ? AND note_path = ?
                """,
                (session_id, self.note.path),
            )
            row = cursor.fetchone()
            if row:
                emb = np.frombuffer(row[0], dtype=np.float32)
                snapshots.append((session_date, emb))

        return snapshots

    def total_drift(self) -> float:
        """Compute total drift (1 - cosine_sim(first, last)).

        Returns:
            Drift distance (0-2, typically 0-1)
        """
        snapshots = self.snapshots()
        if len(snapshots) < 2:
            return 0.0

        first_emb = snapshots[0][1]
        last_emb = snapshots[-1][1]

        similarity = sklearn_cosine(first_emb.reshape(1, -1), last_emb.reshape(1, -1))
        return 1.0 - float(similarity[0, 0])

    def drift_direction_vector(self) -> np.ndarray:
        """Compute unit vector of drift direction (last - first, normalized).

        Returns:
            Unit vector pointing in drift direction (or zero vector if no drift)
        """
        snapshots = self.snapshots()
        if len(snapshots) < 2:
            return np.zeros_like(snapshots[0][1]) if snapshots else np.zeros(384)

        first_emb = snapshots[0][1]
        last_emb = snapshots[-1][1]

        drift_vector = last_emb - first_emb
        norm = float(np.linalg.norm(drift_vector))

        if norm < 1e-10:  # Avoid division by zero
            return np.zeros_like(drift_vector)

        return drift_vector / norm  # type: ignore[no-any-return]

    def drift_alignment(self, direction: np.ndarray) -> float:
        """Compute how aligned trajectory is with a given direction (dot product).

        Args:
            direction: Direction vector to compare against

        Returns:
            Alignment score (-1 to 1, where 1 = perfectly aligned)
        """
        drift_dir = self.drift_direction_vector()
        direction_norm = np.linalg.norm(direction)

        if direction_norm < 1e-10:
            return 0.0

        # Normalize direction vector
        direction_unit = direction / direction_norm

        # Compute dot product (alignment)
        return float(np.dot(drift_dir, direction_unit))

    def windowed_drift_rates(self, window_size: int = 3) -> List[float]:
        """Compute drift rates in sliding windows of consecutive sessions.

        Args:
            window_size: Number of sessions per window

        Returns:
            List of drift rates (one per window)
        """
        snapshots = self.snapshots()
        if len(snapshots) < window_size:
            return []

        drift_rates = []
        for i in range(len(snapshots) - window_size + 1):
            window_start = snapshots[i][1]
            window_end = snapshots[i + window_size - 1][1]

            similarity = sklearn_cosine(
                window_start.reshape(1, -1), window_end.reshape(1, -1)
            )
            drift = 1.0 - float(similarity[0, 0])
            drift_rates.append(drift)

        return drift_rates

    def early_late_split(self) -> Tuple[float, float]:
        """Return (early_avg_sim, late_avg_sim) for convergence detection.

        Splits trajectory into first and second half, computes average similarity
        to current embedding within each half.

        Returns:
            Tuple of (early_avg_similarity, late_avg_similarity)
        """
        snapshots = self.snapshots()
        if len(snapshots) < 4:  # Need at least 4 sessions to split
            return (0.0, 0.0)

        current_emb = snapshots[-1][1]
        midpoint = len(snapshots) // 2

        # Compute average similarity in early half
        early_sims = []
        for _, emb in snapshots[:midpoint]:
            sim = sklearn_cosine(emb.reshape(1, -1), current_emb.reshape(1, -1))
            early_sims.append(float(sim[0, 0]))

        # Compute average similarity in late half (excluding current)
        late_sims = []
        for _, emb in snapshots[midpoint:-1]:
            sim = sklearn_cosine(emb.reshape(1, -1), current_emb.reshape(1, -1))
            late_sims.append(float(sim[0, 0]))

        early_avg = np.mean(early_sims) if early_sims else 0.0
        late_avg = np.mean(late_sims) if late_sims else 0.0

        return (float(early_avg), float(late_avg))

    def is_accelerating(self, threshold: float = 0.1) -> bool:
        """Check if drift rate is increasing over time.

        Args:
            threshold: Minimum increase in drift rate to be considered accelerating

        Returns:
            True if drift is accelerating
        """
        drift_rates = self.windowed_drift_rates(window_size=3)
        if len(drift_rates) < 2:
            return False

        # Compare first and last window drift rates
        initial_rate = drift_rates[0]
        final_rate = drift_rates[-1]

        return (final_rate - initial_rate) > threshold

    def similarity_with_trajectory(
        self, other: "EmbeddingTrajectoryCalculator"
    ) -> List[float]:
        """Compute similarity between this note and another note at each session.

        Only computes similarity for sessions where both notes exist.

        Args:
            other: Another trajectory calculator

        Returns:
            List of similarity scores (one per shared session)
        """
        self_snapshots = self.snapshots()
        other_snapshots = other.snapshots()

        # Build lookup for other's embeddings by date
        other_by_date = {date: emb for date, emb in other_snapshots}

        similarities = []
        for date, self_emb in self_snapshots:
            if date in other_by_date:
                other_emb = other_by_date[date]
                sim = sklearn_cosine(self_emb.reshape(1, -1), other_emb.reshape(1, -1))
                similarities.append(float(sim[0, 0]))

        return similarities

    def is_converging_with(
        self, other: "EmbeddingTrajectoryCalculator", threshold: float = 0.15
    ) -> bool:
        """Check if trajectories are converging (recent sim > early sim + threshold).

        Args:
            other: Another trajectory calculator
            threshold: Minimum increase in similarity to be considered converging

        Returns:
            True if trajectories are converging
        """
        similarities = self.similarity_with_trajectory(other)
        if len(similarities) < 3:
            return False

        # Compare early vs late similarity
        midpoint = len(similarities) // 2
        early_avg = float(np.mean(similarities[:midpoint]))
        late_avg = float(np.mean(similarities[midpoint:]))

        return bool((late_avg - early_avg) > threshold)

    def is_diverging_from(
        self, other: "EmbeddingTrajectoryCalculator", threshold: float = 0.15
    ) -> bool:
        """Check if trajectories are diverging (early sim > recent sim + threshold).

        Args:
            other: Another trajectory calculator
            threshold: Minimum decrease in similarity to be considered diverging

        Returns:
            True if trajectories are diverging
        """
        similarities = self.similarity_with_trajectory(other)
        if len(similarities) < 3:
            return False

        # Compare early vs late similarity
        midpoint = len(similarities) // 2
        early_avg = float(np.mean(similarities[:midpoint]))
        late_avg = float(np.mean(similarities[midpoint:]))

        return bool((early_avg - late_avg) > threshold)


class TemporalPatternFinder:
    """Finds patterns across multiple trajectories.

    Provides high-level operations for finding converging pairs, drifting notes,
    and other temporal patterns. Builds on EmbeddingTrajectoryCalculator to
    analyze multiple notes at once.

    Example:
        >>> finder = TemporalPatternFinder(vault)
        >>> drifting = finder.find_high_drift_notes(notes, min_drift=0.2)
        >>> for note, drift_vector in drifting:
        ...     print(f"{note.title} has drifted significantly")
    """

    def __init__(self, vault: "VaultContext"):
        """Initialize pattern finder with vault context.

        Args:
            vault: VaultContext with session history
        """
        self.vault = vault

    def find_converging_pairs(
        self,
        candidate_pairs: List[Tuple["Note", "Note"]],
        threshold: float = 0.15,
    ) -> List[Tuple["Note", "Note"]]:
        """Find pairs whose embeddings are converging across sessions.

        Args:
            candidate_pairs: List of (note_a, note_b) pairs to check
            threshold: Minimum similarity increase to be considered converging

        Returns:
            List of converging pairs
        """
        converging = []

        for note_a, note_b in candidate_pairs:
            calc_a = EmbeddingTrajectoryCalculator(self.vault, note_a)
            calc_b = EmbeddingTrajectoryCalculator(self.vault, note_b)

            if calc_a.is_converging_with(calc_b, threshold):
                converging.append((note_a, note_b))

        return converging

    def find_high_drift_notes(
        self, notes: List["Note"], min_drift: float = 0.2
    ) -> List[Tuple["Note", np.ndarray]]:
        """Find notes with significant drift and their drift direction vectors.

        Args:
            notes: Notes to analyze
            min_drift: Minimum drift to be considered high

        Returns:
            List of (note, drift_direction_vector) tuples
        """
        high_drift = []

        for note in notes:
            calc = EmbeddingTrajectoryCalculator(self.vault, note)

            # Need at least 3 sessions for meaningful drift
            if len(calc.snapshots()) < 3:
                continue

            drift = calc.total_drift()
            if drift >= min_drift:
                drift_vector = calc.drift_direction_vector()
                high_drift.append((note, drift_vector))

        return high_drift

    def find_aligned_with_direction(
        self,
        notes: List["Note"],
        direction: np.ndarray,
        min_alignment: float = 0.5,
    ) -> List["Note"]:
        """Find notes drifting in a specific semantic direction.

        Args:
            notes: Notes to analyze
            direction: Direction vector to compare against
            min_alignment: Minimum alignment score (-1 to 1)

        Returns:
            List of notes aligned with direction
        """
        aligned = []

        for note in notes:
            calc = EmbeddingTrajectoryCalculator(self.vault, note)

            # Need at least 2 sessions for drift direction
            if len(calc.snapshots()) < 2:
                continue

            alignment = calc.drift_alignment(direction)
            if alignment >= min_alignment:
                aligned.append(note)

        return aligned

    def find_cycling_notes(
        self, notes: List["Note"], min_cycles: int = 2
    ) -> List["Note"]:
        """Find notes that return to previous semantic states (cyclical thinking).

        A note is considered cyclical if it alternates between being similar and
        dissimilar to its first state across sessions.

        Args:
            notes: Notes to analyze
            min_cycles: Minimum number of cycles to detect

        Returns:
            List of cyclical notes
        """
        cycling = []

        for note in notes:
            calc = EmbeddingTrajectoryCalculator(self.vault, note)
            snapshots = calc.snapshots()

            # Need at least 2*min_cycles + 1 sessions
            if len(snapshots) < (2 * min_cycles + 1):
                continue

            # Check for alternating similarity to first embedding
            first_emb = snapshots[0][1]
            similarities = []

            for _, emb in snapshots[1:]:
                sim = sklearn_cosine(first_emb.reshape(1, -1), emb.reshape(1, -1))
                similarities.append(float(sim[0, 0]))

            # Count transitions from high->low->high similarity
            cycles = 0
            state = "high" if similarities[0] > 0.7 else "low"

            for sim in similarities[1:]:
                new_state = "high" if sim > 0.7 else "low"
                if new_state != state:
                    if state == "low" and new_state == "high":
                        cycles += 1
                    state = new_state

            if cycles >= min_cycles:
                cycling.append(note)

        return cycling
