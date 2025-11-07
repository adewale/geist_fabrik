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

    Returns:
        List of suggestions showing how concepts evolve
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        # Get session history
        cursor = vault.db.execute(
            """
            SELECT session_id, session_date FROM sessions
            ORDER BY session_date ASC
            """
        )
        sessions = cursor.fetchall()

        if len(sessions) < 3:
            return []

        # Find notes that appear in multiple sessions
        notes = vault.notes()

        for note in vault.sample(notes, min(30, len(notes))):
            # Get embedding trajectory for this note
            trajectory = []

            for session_id, session_date in sessions:
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
                    trajectory.append((session_date, emb))

            if len(trajectory) < 3:
                continue

            # Analyze trajectory: has the note's meaning migrated?
            first_emb = trajectory[0][1]
            last_emb = trajectory[-1][1]

            # Calculate drift from first to last using sklearn
            from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
                cosine_similarity as sklearn_cosine,
            )

            similarity = sklearn_cosine(first_emb.reshape(1, -1), last_emb.reshape(1, -1))
            drift = 1.0 - float(similarity[0, 0])

            if drift > 0.2:  # Significant migration
                # Try to characterize the drift by finding what it's moving toward
                current_neighbors = vault.neighbours(note, k=5)

                # Find which neighbors are most aligned with the drift direction
                drift_vector = last_emb - first_emb
                # Cache drift_vector norm to avoid redundant computation (5 times in loop)
                drift_vector_norm = np.linalg.norm(drift_vector)

                neighbor_alignments = []
                for neighbor in current_neighbors:
                    if neighbor.path == note.path:
                        continue

                    # Get neighbor embedding from database
                    cursor = vault.db.execute(
                        """
                        SELECT embedding FROM session_embeddings
                        WHERE session_id = ? AND note_path = ?
                        """,
                        (sessions[-1][0], neighbor.path),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        continue

                    neighbor_emb = np.frombuffer(row[0], dtype=np.float32)

                    # How aligned is neighbor with drift direction?
                    # Use cached drift_vector_norm instead of recomputing
                    alignment = np.dot(drift_vector, neighbor_emb) / (
                        drift_vector_norm * np.linalg.norm(neighbor_emb)
                    )
                    neighbor_alignments.append((neighbor, alignment))

                if neighbor_alignments:
                    neighbor_alignments.sort(key=lambda x: x[1], reverse=True)
                    top_neighbor = neighbor_alignments[0][0]

                    first_date = trajectory[0][0].strftime("%Y-%m")
                    last_date = trajectory[-1][0].strftime("%Y-%m")

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

    except Exception:
        return []

    return vault.sample(suggestions, k=2)
