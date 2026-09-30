"""Hermeneutic Instability geist - finds variable semantic representations."""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with high semantic-vector variance across sessions.

    Uses EmbeddingTrajectoryCalculator to get embedding history, then
    calculates mean distance from the note's semantic-vector centroid.

    Returns:
        List of suggestions highlighting variable semantic representations
    """
    from scipy.spatial.distance import euclidean  # type: ignore[import-untyped]

    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import (
        EmbeddingTrajectoryCalculator,
        semantic_component,
    )

    # For each note, calculate embedding variance across sessions. Geist
    # journal session notes are output, not notes with an interpretation.
    notes = vault.notes_excluding_journal()
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
        embeddings = [semantic_component(emb) for _date, emb in snapshots]

        # Calculate variance (how much embeddings differ from mean)
        embeddings_array = np.array(embeddings)
        mean_embedding = np.mean(embeddings_array, axis=0)

        # Measure instability as average distance from mean
        distances = [euclidean(emb, mean_embedding) for emb in embeddings_array]
        instability = np.mean(distances)

        # High variance is an embedding observation, not evidence about the
        # author's interpretation or the cause of the movement.
        if instability > 0.2:  # Threshold for significant instability
            # Check if content is actually changing
            metadata = vault.metadata(note)
            days_since_modified = metadata.get("days_since_modified", 0)

            if days_since_modified > 60:
                text = (
                    f"The semantic representation of [[{note.link_text}]] varied across "
                    f"its last {len(embeddings)} recorded sessions, while the note has "
                    f"not been edited in {days_since_modified} days. Review the snapshots "
                    f"before deciding whether the variation is meaningful."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text],
                        geist_id="hermeneutic_instability",
                    )
                )

    return vault.sample(suggestions, count=2)
