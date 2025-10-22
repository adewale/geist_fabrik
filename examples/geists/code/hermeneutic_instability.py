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

    Returns:
        List of suggestions highlighting unstable interpretations
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        # Get session history (need at least 3 sessions for variance)
        cursor = vault.db.execute(
            """
            SELECT session_id FROM sessions
            ORDER BY session_date DESC
            LIMIT 5
            """
        )
        session_ids = [row[0] for row in cursor.fetchall()]

        if len(session_ids) < 3:
            return []

        # For each note, calculate embedding variance across sessions
        notes = vault.notes()

        for note in vault.sample(notes, min(50, len(notes))):
            embeddings = []

            # Get embeddings from all sessions
            for session_id in session_ids:
                cursor = vault.db.execute(
                    """
                    SELECT embedding FROM session_embeddings
                    WHERE session_id = ? AND note_path = ?
                    """,
                    (session_id, note.path),
                )
                row = cursor.fetchone()
                if row:
                    emb = np.frombuffer(row[0], dtype=np.float32)
                    embeddings.append(emb)

            if len(embeddings) < 3:
                continue

            # Calculate variance (how much embeddings differ from mean)
            embeddings_array = np.array(embeddings)
            mean_embedding = np.mean(embeddings_array, axis=0)

            # Measure instability as average distance from mean
            distances = [np.linalg.norm(emb - mean_embedding) for emb in embeddings_array]
            instability = np.mean(distances)

            # High instability = interpretive instability
            if instability > 0.2:  # Threshold for significant instability
                # Check if content is actually changing
                metadata = vault.metadata(note)
                days_since_modified = metadata.get("days_since_modified", 0)

                if days_since_modified > 60:  # Stable content, unstable interpretation
                    text = (
                        f"[[{note.title}]] has been interpreted differently in each of your last "
                        f"{len(embeddings)} sessions, despite not being edited in {days_since_modified} days. "
                        f"Meaning unsettled? Or does it mean different things in different contexts?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[note.title],
                            geist_id="hermeneutic_instability",
                        )
                    )

    except Exception:
        # Temporal embeddings not available
        return []

    return vault.sample(suggestions, k=2)
