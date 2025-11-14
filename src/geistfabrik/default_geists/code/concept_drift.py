"""Concept Drift geist - tracks how concepts evolve over time.

Maps the semantic trajectory of notes about the same concept across sessions,
revealing how your understanding of ideas migrates and develops.
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Track embedding trajectory of concept notes across sessions.

    Uses TemporalPatternFinder to identify high-drift notes, then analyzes
    which current neighbors are most aligned with the drift direction.

    Returns:
        List of suggestions showing how concepts evolve
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import (
        EmbeddingTrajectoryCalculator,
        TemporalPatternFinder,
    )

    # Find notes with significant drift (>0.2)
    notes = vault.notes()
    finder = TemporalPatternFinder(vault)
    drifting = finder.find_high_drift_notes(notes, min_drift=0.2)

    if not drifting:
        return []

    # Sample up to 30 drifting notes (as original did)
    sampled_drifting = vault.sample(drifting, k=min(30, len(drifting)))

    suggestions = []
    for note, drift_vector in sampled_drifting:
        # Try to characterize the drift by finding what it's moving toward
        current_neighbors = vault.neighbours(note, k=5)

        if not current_neighbors:
            continue

        # Find which neighbors are most aligned with the drift direction
        neighbor_alignments = []
        for neighbour in current_neighbors:
            if neighbour.path == note.path:
                continue

            # Get neighbor's current embedding from their trajectory
            neighbor_calc = EmbeddingTrajectoryCalculator(vault, neighbour)
            neighbor_snapshots = neighbor_calc.snapshots()

            if not neighbor_snapshots:
                continue

            # Use most recent embedding
            neighbor_emb = neighbor_snapshots[-1][1]

            # How aligned is neighbor with drift direction?
            # drift_vector is already a unit vector from TemporalPatternFinder
            alignment = np.dot(drift_vector, neighbor_emb) / np.linalg.norm(
                neighbor_emb
            )
            neighbor_alignments.append((neighbour, alignment))

        if not neighbor_alignments:
            continue

        neighbor_alignments.sort(key=lambda x: x[1], reverse=True)
        top_neighbor = neighbor_alignments[0][0]

        # Get trajectory dates for context
        calc = EmbeddingTrajectoryCalculator(vault, note)
        snapshots = calc.snapshots()

        if len(snapshots) < 2:
            continue

        first_date = snapshots[0][0].strftime("%Y-%m")
        last_date = snapshots[-1][0].strftime("%Y-%m")

        text = (
            f"[[{note.obsidian_link}]] has semantically migrated since {first_date}. "
            f"It's now drifting toward [[{top_neighbor.obsidian_link}]]—"
            f"concept evolving from {first_date} to {last_date}?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.obsidian_link, top_neighbor.obsidian_link],
                geist_id="concept_drift",
            )
        )

    return vault.sample(suggestions, k=2)
