"""Divergent Evolution geist - finds linked notes growing semantically apart.

Identifies notes that are linked but whose embeddings have been diverging across
sessions, suggesting old connections that may no longer hold.
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find linked notes whose understanding is diverging across sessions.

    Returns:
        List of suggestions showing divergent development
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        # Get session history
        cursor = vault.db.execute(
            """
            SELECT session_id FROM sessions
            ORDER BY session_date ASC
            """
        )
        sessions = [row[0] for row in cursor.fetchall()]

        if len(sessions) < 3:
            return []

        # Find linked note pairs
        notes = vault.notes()
        linked_pairs = []

        for note in vault.sample(notes, min(30, len(notes))):
            for target_note in vault.outgoing_links(note)[:5]:  # Check first 5 links
                linked_pairs.append((note, target_note))

        if len(linked_pairs) < 2:
            return []

        # Check divergence for linked pairs
        for note_a, note_b in vault.sample(linked_pairs, min(50, len(linked_pairs))):
            # Get embedding history for both notes
            embeddings_a = []
            embeddings_b = []

            for session_id in sessions:
                cursor_a = vault.db.execute(
                    """
                    SELECT embedding FROM session_embeddings
                    WHERE session_id = ? AND note_path = ?
                    """,
                    (session_id, note_a.path),
                )
                cursor_b = vault.db.execute(
                    """
                    SELECT embedding FROM session_embeddings
                    WHERE session_id = ? AND note_path = ?
                    """,
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

            # Calculate similarity trajectory using sklearn
            from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
                cosine_similarity as sklearn_cosine,
            )

            similarities = []
            for emb_a, emb_b in zip(embeddings_a, embeddings_b):
                sim = float(sklearn_cosine(emb_a.reshape(1, -1), emb_b.reshape(1, -1))[0, 0])
                similarities.append(sim)

            # Check if similarity is decreasing (divergence)
            early_sim = np.mean(similarities[: len(similarities) // 2])
            recent_sim = np.mean(similarities[len(similarities) // 2 :])

            if early_sim > recent_sim + 0.15:  # Significant divergence
                text = (
                    f"[[{note_a.title}]] and [[{note_b.title}]] are linked, "
                    f"but they've been semantically diverging across your last "
                    f"{len(similarities)} sessions. They were similar when connected "
                    f"but have drifted apart—does the link still make sense?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note_a.title, note_b.title],
                        geist_id="divergent_evolution",
                    )
                )

    except Exception:
        return []

    return vault.sample(suggestions, k=2)
