"""Convergent Evolution geist - finds notes developing toward each other.

Identifies pairs of notes whose embeddings have been converging across sessions,
suggesting ideas that are independently developing in the same direction.
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes whose understanding is converging across sessions.

    Returns:
        List of suggestions showing convergent development
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        # Get session history (need at least 3 sessions)
        cursor = vault.db.execute(
            """
            SELECT session_id FROM sessions
            ORDER BY session_date ASC
            """
        )
        sessions = [row[0] for row in cursor.fetchall()]

        if len(sessions) < 3:
            return []

        # Sample note pairs and check if they're converging
        notes = vault.notes()

        if len(notes) < 10:
            return []

        pairs = []
        sample_notes = vault.sample(notes, min(30, len(notes)))

        for i, note_a in enumerate(sample_notes):
            for note_b in sample_notes[i + 1 :]:
                pairs.append((note_a, note_b))

        # Check convergence for each pair
        for note_a, note_b in vault.sample(pairs, min(100, len(pairs))):
            # Get embedding history for both notes
            embeddings_a = []
            embeddings_b = []

            for session_id in sessions:
                cursor_a = vault.db.execute(
                    "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
                    (session_id, note_a.path),
                )
                cursor_b = vault.db.execute(
                    "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
                    (session_id, note_b.path),
                )

                row_a = cursor_a.fetchone()
                row_b = cursor_b.fetchone()

                if row_a and row_b:
                    emb_a = np.frombuffer(row_a[0], dtype=np.float32)
                    emb_b = np.frombuffer(row_b[0], dtype=np.float32)
                    embeddings_a.append(emb_a)
                    embeddings_b.append(emb_b)

            if len(embeddings_a) < 3:
                continue

            # Calculate similarity trajectory
            similarities = []
            for emb_a, emb_b in zip(embeddings_a, embeddings_b):
                sim = np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b))
                similarities.append(sim)

            # Check if similarity is increasing (convergence)
            early_sim = np.mean(similarities[: len(similarities) // 2])
            recent_sim = np.mean(similarities[len(similarities) // 2 :])

            if recent_sim > early_sim + 0.15:  # Significant convergence
                # Check if they're currently similar but not linked
                if not vault.links_between(note_a, note_b):
                    text = (
                        f"[[{note_a.title}]] and [[{note_b.title}]] have been converging "
                        f"semantically across your last {len(similarities)} sessions. "
                        f"Two ideas independently developing in the same direction—time to link them?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[note_a.title, note_b.title],
                            geist_id="convergent_evolution",
                        )
                    )

    except Exception:
        return []

    return vault.sample(suggestions, k=2)
