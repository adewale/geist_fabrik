"""Session Drift geist - tracks how understanding of notes evolves across sessions.

Uses temporal embeddings to detect when your interpretation of notes changes
significantly between sessions, even when content doesn't change.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes whose interpretation has shifted between sessions.

    Uses EmbeddingTrajectoryCalculator to compare recent session embeddings,
    detecting interpretive drift independent of content changes.

    Returns:
        List of suggestions highlighting interpretive drift
    """
    from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
        cosine_similarity as sklearn_cosine,
    )

    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

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
        current_emb = snapshots[-1][1]
        previous_emb = snapshots[-2][1]

        similarity = float(
            sklearn_cosine(current_emb.reshape(1, -1), previous_emb.reshape(1, -1))[
                0, 0
            ]
        )
        drift = 1.0 - similarity

        # High drift suggests interpretation changed
        if drift > 0.15:  # Threshold for significant drift
            # Check if content actually changed
            # If content didn't change but interpretation did, that's interesting
            metadata = vault.metadata(note)
            days_since_modified = metadata.get("days_since_modified", 0)

            if days_since_modified > 30:  # Content hasn't changed recently
                text = (
                    f"Your understanding of [[{note.obsidian_link}]] shifted significantly "
                    f"between last session and this one, even though you haven't "
                    f"edited it in {days_since_modified} days. "
                    f"What changed in how you're reading it?"
                )
            else:
                text = (
                    f"[[{note.obsidian_link}]] is being interpreted quite differently "
                    f"in this session—meaning evolving as you edit it?"
                )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="session_drift",
                )
            )

    return vault.sample(suggestions, k=3)
