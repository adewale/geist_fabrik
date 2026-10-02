"""Session Drift geist - finds content representations that moved across sessions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes whose semantic embedding shifted between sessions.

    Uses EmbeddingTrajectoryCalculator to compare recent session embeddings,
    comparing content-derived dimensions without calendar features.

    Returns:
        List of suggestions highlighting semantic-representation drift
    """
    from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
        cosine_similarity as sklearn_cosine,
    )

    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import (
        EmbeddingTrajectoryCalculator,
        semantic_component,
    )

    # For each note, compare embeddings across recent sessions
    notes = vault.notes()
    suggestions = []

    for note in vault.sample(notes, min(50, len(notes))):
        # Get embedding trajectory
        calc = EmbeddingTrajectoryCalculator(vault, note)
        snapshots = calc.snapshots()

        if len(snapshots) < 2:
            continue

        # Calculate drift between most recent and previous session
        current_emb = semantic_component(snapshots[-1][1])
        previous_emb = semantic_component(snapshots[-2][1])

        similarity = float(
            sklearn_cosine(current_emb.reshape(1, -1), previous_emb.reshape(1, -1))[0, 0]
        )
        drift = 1.0 - similarity

        # High drift records a content-representation change; it does not
        # establish what the author thought or why the representation moved.
        if drift > 0.15:  # Threshold for significant drift
            # Modification age provides context only; historical vectors do not
            # prove why the representation changed.
            metadata = vault.metadata(note)
            days_since_modified = metadata.get("days_since_modified", 0)

            if days_since_modified > 30:  # Content hasn't changed recently
                text = (
                    f"The semantic representation of [[{note.link_text}]] differs "
                    f"between its two latest recorded sessions. The note has not "
                    f"been edited in {days_since_modified} days; reread it and decide "
                    f"what, if anything, changed in its meaning."
                )
            else:
                text = (
                    f"The semantic representation of [[{note.link_text}]] differs "
                    f"between its two latest recorded sessions. Recent edits may "
                    f"explain the change; review the note to decide whether it matters."
                )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="session_drift",
                )
            )

    return vault.sample(suggestions, count=3)
