"""Vocabulary Expansion geist - tracks semantic space coverage over time.

Measures how much semantic territory your notes explore across sessions,
detecting periods of convergence (focusing) or divergence (exploring).
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Measure semantic territory exploration across sessions.

    Returns:
        List of suggestions about semantic coverage changes
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        # Get recent session history
        cursor = vault.db.execute(
            """
            SELECT session_id, date FROM sessions
            ORDER BY date DESC
            LIMIT 5
            """
        )
        sessions = cursor.fetchall()

        if len(sessions) < 3:
            return []

        # For each session, calculate semantic coverage (dispersion from centroid)
        coverage_by_session = []

        for session_id, session_date in sessions:
            # Get all embeddings for this session
            cursor = vault.db.execute(
                """
                SELECT embedding FROM session_embeddings
                WHERE session_id = ?
                """,
                (session_id,),
            )

            embeddings = [np.frombuffer(row[0], dtype=np.float32) for row in cursor.fetchall()]

            if len(embeddings) < 10:
                continue

            # Calculate dispersion (standard deviation from centroid)
            embeddings_array = np.array(embeddings)
            centroid = np.mean(embeddings_array, axis=0)

            # Use scipy for Euclidean distance calculation
            from scipy.spatial.distance import euclidean  # type: ignore[import-untyped]

            distances = [euclidean(emb, centroid) for emb in embeddings_array]
            coverage = np.std(distances)

            coverage_by_session.append((session_date, coverage))

        if len(coverage_by_session) < 3:
            return []

        # Analyze trend
        coverage_by_session.sort(key=lambda x: x[0])  # Sort by date

        recent_coverage = np.mean([c for _, c in coverage_by_session[-2:]])
        older_coverage = np.mean([c for _, c in coverage_by_session[:2]])

        # Detect significant changes in exploration

        # Convergence (focusing on fewer topics)
        if recent_coverage < older_coverage * 0.8:
            recent_date = coverage_by_session[-1][0].strftime("%Y-%m")
            older_date = coverage_by_session[0][0].strftime("%Y-%m")

            text = (
                f"Your recent notes (since {recent_date}) explore less semantic territory "
                f"than earlier ones (around {older_date}). You're converging on specific topics—"
                f"deep focus or narrowing perspective?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[],
                    geist_id="vocabulary_expansion",
                )
            )

        # Divergence (exploring more diverse topics)
        elif recent_coverage > older_coverage * 1.2:
            recent_date = coverage_by_session[-1][0].strftime("%Y-%m")
            older_date = coverage_by_session[0][0].strftime("%Y-%m")

            text = (
                f"Your recent notes (since {recent_date}) cover more semantic ground "
                f"than before (around {older_date}). You're branching into new areas—"
                f"expansion phase or intellectual restlessness?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[],
                    geist_id="vocabulary_expansion",
                )
            )

    except Exception:
        return []

    return vault.sample(suggestions, k=1)
