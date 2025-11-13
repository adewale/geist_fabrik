"""Hermeneutic Instability geist - finds notes with unstable interpretation.

Identifies notes that are interpreted differently across sessions despite
no content changes, suggesting the meaning is unsettled or actively evolving.
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with high interpretive variance across sessions.

    Uses EmbeddingTrajectoryCalculator to get embedding history, then
    calculates variance as a measure of interpretive instability.

    Returns:
        List of suggestions highlighting unstable interpretations
    """
    from scipy.spatial.distance import euclidean  # type: ignore[import-untyped]

    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

    # For each note, calculate embedding variance across sessions
    notes = vault.notes()
    suggestions = []

    for note in vault.sample(notes, min(50, len(notes))):
        # Get embedding trajectory (limit to last 5 sessions)
        calc = EmbeddingTrajectoryCalculator(vault, note)
        snapshots = calc.snapshots()

        # Take only last 5 sessions for recent variance
        if len(snapshots) > 5:
            snapshots = snapshots[-5:]

        if len(snapshots) < 3:
            continue

        # Extract embeddings (discard dates)
        embeddings = [emb for _date, emb in snapshots]

        # Calculate variance (how much embeddings differ from mean)
        embeddings_array = np.array(embeddings)
        mean_embedding = np.mean(embeddings_array, axis=0)

        # Measure instability as average distance from mean
        distances = [euclidean(emb, mean_embedding) for emb in embeddings_array]
        instability = np.mean(distances)

        # High instability = interpretive instability
        if instability > 0.2:  # Threshold for significant instability
            # Check if content is actually changing
            metadata = vault.metadata(note)
            days_since_modified = metadata.get("days_since_modified", 0)

            if days_since_modified > 60:  # Stable content, unstable interpretation
                text = (
                    f"[[{note.obsidian_link}]] has been interpreted differently in each of "
                    f"your last {len(embeddings)} sessions, despite not being edited "
                    f"in {days_since_modified} days. Meaning unsettled? Or does it mean "
                    f"different things in different contexts?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.obsidian_link],
                        geist_id="hermeneutic_instability",
                    )
                )

    return vault.sample(suggestions, k=2)
