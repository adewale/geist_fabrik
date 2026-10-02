"""Concept Drift geist - notices notes you have rewritten, and where they went.

Stored session vectors are computed from note content (and cached by it), so a
note's meaning vector only moves when its text was edited. This geist finds
notes that moved far from their first recorded vector, says since which
session you have been rewriting them (the latest session whose vector differs
from today's), adds "changing more lately" when the change across its last
three recorded sessions exceeds the change across its first three, and names
the current neighbour the edits moved it towards.

(Absorbs the former session_drift and drift_velocity_anomaly geists.)
"""

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# A session whose vector differs from today's by more than this was before
# a real rewrite (not a typo fix).
REWRITE_DRIFT = 0.15
# "Changing more lately": drift across the last three recorded sessions
# exceeds drift across the first three by more than this.
ACCELERATION = 0.1


def _rewritten_since(snapshots: list[tuple[datetime, np.ndarray]]) -> datetime | None:
    """Date of the latest earlier session whose meaning vector differs from the
    latest one by more than REWRITE_DRIFT, or None."""
    from geistfabrik.temporal_analysis import semantic_component

    latest = semantic_component(snapshots[-1][1])
    latest_norm = float(np.linalg.norm(latest))
    for date, embedding in reversed(snapshots[:-1]):
        earlier = semantic_component(embedding)
        norm = float(np.linalg.norm(earlier)) * latest_norm
        if norm < 1e-10:
            continue
        if 1.0 - float(np.dot(earlier, latest)) / norm > REWRITE_DRIFT:
            return date
    return None


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find rewritten notes and the neighbour their edits moved them towards.

    Uses TemporalPatternFinder to identify high-drift notes (>= 3 snapshots,
    first-to-latest drift >= 0.2), then finds which current neighbour is most
    aligned with the drift direction.

    Returns:
        Up to 2 suggestions about rewritten notes
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import (
        EmbeddingTrajectoryCalculator,
        TemporalPatternFinder,
        semantic_component,
    )

    # Find notes with significant drift (>0.2)
    notes = vault.notes()
    finder = TemporalPatternFinder(vault)
    drifting = finder.find_high_drift_notes(notes, min_drift=0.2)

    if not drifting:
        return []

    # Sample up to 30 drifting notes (as original did)
    sampled_drifting = vault.sample(drifting, count=min(30, len(drifting)))

    suggestions = []
    for note, drift_vector in sampled_drifting:
        # Try to characterize the drift by finding what it's moving toward
        current_neighbours = vault.neighbours(note, count=5)

        if not current_neighbours:
            continue

        # Find which neighbours are most aligned with the drift direction
        neighbour_alignments = []
        for neighbour in current_neighbours:
            if neighbour.path == note.path:
                continue

            # Get neighbour's current embedding from their trajectory
            neighbour_calc = EmbeddingTrajectoryCalculator(vault, neighbour)
            neighbour_snapshots = neighbour_calc.snapshots()

            if not neighbour_snapshots:
                continue

            # Use most recent embedding
            neighbour_emb = semantic_component(neighbour_snapshots[-1][1])

            # How aligned is neighbour with drift direction?
            # drift_vector is already a unit vector from TemporalPatternFinder
            neighbour_norm = np.linalg.norm(neighbour_emb)
            if neighbour_norm < 1e-10:
                continue
            alignment = np.dot(drift_vector, neighbour_emb) / neighbour_norm
            neighbour_alignments.append((neighbour, alignment))

        if not neighbour_alignments:
            continue

        neighbour_alignments.sort(key=lambda x: x[1], reverse=True)
        top_neighbour, top_alignment = neighbour_alignments[0]

        # The note moved away from every sampled neighbour: none lies in the
        # direction of the change, so "aligns most" would be false.
        if top_alignment <= 0:
            continue

        calc = EmbeddingTrajectoryCalculator(vault, note)
        snapshots = calc.snapshots()
        since = _rewritten_since(snapshots) if len(snapshots) >= 2 else None
        if since is None:
            continue

        lately = (
            ", and it has been changing more lately"
            if calc.is_accelerating(threshold=ACCELERATION)
            else ""
        )
        text = (
            f"You've rewritten [[{note.link_text}]] since your session on "
            f"{since:%Y-%m-%d}{lately}. Of its current neighbours, the edits moved it "
            f"most toward [[{top_neighbour.link_text}]]. What were you reaching for?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text, top_neighbour.link_text],
                geist_id="concept_drift",
            )
        )

    return vault.sample(suggestions, count=2)
