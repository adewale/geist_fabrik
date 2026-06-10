"""Vocabulary Expansion geist - tracks semantic space coverage over time.

Measures how much semantic territory your notes explore across sessions,
detecting periods of convergence (focusing) or divergence (exploring).
"""

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

logger = logging.getLogger(__name__)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Measure semantic territory exploration across sessions.

    Returns:
        List of suggestions about semantic coverage changes
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        # Get recent session history via VaultContext abstraction
        session_data = vault.session_embeddings_by_session()

        if len(session_data) < 3:
            return []

        # For each session, calculate semantic coverage (dispersion)
        coverage_by_session = []

        for _session_id, session_date_str, embeddings in session_data:
            if len(embeddings) < 10:
                continue

            # Calculate dispersion (standard deviation from centroid)
            embeddings_array = np.array(embeddings)
            centroid = np.mean(embeddings_array, axis=0)

            # Use scipy for Euclidean distance calculation
            from scipy.spatial.distance import euclidean  # type: ignore[import-untyped]

            distances = [euclidean(emb, centroid) for emb in embeddings_array]
            coverage = np.std(distances)

            coverage_by_session.append((session_date_str, coverage))

        if len(coverage_by_session) < 3:
            return []

        # Analyze trend
        coverage_by_session.sort(key=lambda x: x[0])  # Sort by date

        recent_coverage = np.mean([c for _, c in coverage_by_session[-2:]])
        older_coverage = np.mean([c for _, c in coverage_by_session[:2]])

        # Detect significant changes in exploration

        # Convergence (focusing on fewer topics)
        if recent_coverage < older_coverage * 0.8:
            recent_date = coverage_by_session[-1][0]
            older_date = coverage_by_session[0][0]

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
            recent_date = coverage_by_session[-1][0]
            older_date = coverage_by_session[0][0]

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
        logger.debug("vocabulary_expansion geist failed", exc_info=True)
        return []

    return vault.sample(suggestions, k=1)
