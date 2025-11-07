"""Session Drift geist - tracks how understanding of notes evolves across sessions.

Uses temporal embeddings to detect when your interpretation of notes changes
significantly between sessions, even when content doesn't change.
"""

from typing import TYPE_CHECKING, List, Optional

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes whose interpretation has shifted between sessions.

    Returns:
        List of suggestions highlighting interpretive drift
    """
    from geistfabrik import Suggestion

    suggestions = []

    # This requires temporal embeddings - check if session history exists
    try:
        # Get recent sessions (requires temporal embedding support)
        session_history = _get_session_history(vault, sessions_back=5)

        if len(session_history) < 2:
            return []  # Need at least 2 sessions for comparison

        # For each note, compare embeddings across sessions
        notes = vault.notes()

        for note in vault.sample(notes, min(50, len(notes))):
            # Get embedding history for this note
            embeddings_over_time = []

            for session_id in session_history:
                emb = _get_note_embedding_for_session(vault, note.path, session_id)
                if emb is not None:
                    embeddings_over_time.append(emb)

            if len(embeddings_over_time) < 2:
                continue

            # Calculate drift between most recent and previous session
            current_emb = embeddings_over_time[-1]
            previous_emb = embeddings_over_time[-2]

            drift = _calculate_drift(current_emb, previous_emb)

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

    except Exception:
        # Temporal embeddings not available yet
        return []

    return vault.sample(suggestions, k=3)


def _get_session_history(vault: "VaultContext", sessions_back: int = 5) -> List[int]:
    """Get list of recent session IDs."""
    try:
        cursor = vault.db.execute(
            """
            SELECT session_id FROM sessions
            ORDER BY session_date DESC
            LIMIT ?
            """,
            (sessions_back,),
        )
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []


def _get_note_embedding_for_session(
    vault: "VaultContext", note_path: str, session_id: int
) -> Optional[npt.NDArray[np.float32]]:
    """Get embedding for a specific note from a specific session."""
    try:
        cursor = vault.db.execute(
            """
            SELECT embedding FROM session_embeddings
            WHERE session_id = ? AND note_path = ?
            """,
            (session_id, note_path),
        )
        row = cursor.fetchone()
        if row:
            # Embedding stored as blob, convert to numpy array
            return np.frombuffer(row[0], dtype=np.float32)
        return None
    except Exception:
        return None


def _calculate_drift(emb1: npt.NDArray[np.float32], emb2: npt.NDArray[np.float32]) -> float:
    """Calculate drift between two embeddings."""
    from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
        cosine_similarity as sklearn_cosine,
    )

    # Use cosine distance as drift measure
    similarity = float(sklearn_cosine(emb1.reshape(1, -1), emb2.reshape(1, -1))[0, 0])
    drift = 1.0 - similarity
    return drift
