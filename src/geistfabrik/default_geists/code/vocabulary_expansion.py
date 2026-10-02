"""Vocabulary Expansion geist - tracks note-vector dispersion over time.

Compares the mean semantic distance from each session's note-vector centroid.
It reports only that measured distribution change, not the user's mental state,
and names two of the notes nearest the centre (when the spread narrowed) or
farthest from it (when it widened) as places to look.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext

logger = logging.getLogger(__name__)


def _edge_notes(vault: "VaultContext", *, nearest: bool) -> list["Note"]:
    """Two of the five notes nearest to (or farthest from) the current centroid.

    The suggestion names notes so it survives the quality filter, which
    drops a suggestion that names none. Sampling among the five keeps one
    outlier from being named every session.
    """
    vectors = vault.get_all_embeddings()
    if not vectors:
        return []
    paths = sorted(vectors)
    matrix = np.array([vectors[path] for path in paths])
    distances = np.linalg.norm(matrix - matrix.mean(axis=0), axis=1)
    order = np.argsort(distances, kind="stable")
    if not nearest:
        order = order[::-1]
    candidates = [note for i in order[:5] if (note := vault.get_note(paths[i])) is not None]
    return vault.sample(candidates, min(2, len(candidates)))


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Measure note-vector dispersion across sessions.

    Returns:
        List of suggestions about semantic coverage changes
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import semantic_component

    suggestions = []

    try:
        # Get recent session history via VaultContext abstraction
        session_data = vault.session_embeddings_by_session()

        if len(session_data) < 3:
            return []

        # For each session, calculate mean semantic distance from its centroid.
        coverage_by_session = []

        for _session_id, session_date_str, embeddings in session_data:
            if len(embeddings) < 10:
                continue

            embeddings_array = np.array(
                [semantic_component(embedding) for embedding in embeddings]
            )
            centroid = np.mean(embeddings_array, axis=0)

            # Use scipy for Euclidean distance calculation
            from scipy.spatial.distance import euclidean  # type: ignore[import-untyped]

            distances = [euclidean(emb, centroid) for emb in embeddings_array]
            coverage = float(np.mean(distances))

            coverage_by_session.append((session_date_str, coverage))

        if len(coverage_by_session) < 3:
            return []

        # Analyze trend
        coverage_by_session.sort(key=lambda x: x[0])  # Sort by date

        recent_coverage = np.mean([c for _, c in coverage_by_session[-2:]])
        older_coverage = np.mean([c for _, c in coverage_by_session[:2]])

        # Describe significant changes in the measured distribution only.
        if recent_coverage < older_coverage * 0.8:
            direction, edge = "lower", "nearest"
            question = "Is the vault gathering around them?"
        elif recent_coverage > older_coverage * 1.2:
            direction, edge = "higher", "farthest from"
            question = "Is this where your range is widening?"
        else:
            return []

        named = _edge_notes(vault, nearest=direction == "lower")
        if not named:
            return []
        links = " and ".join(f"[[{note.link_text}]]" for note in named)
        verb = "sits" if len(named) == 1 else "sit"
        recent_date = coverage_by_session[-1][0]
        older_date = coverage_by_session[0][0]
        text = (
            f"The mean semantic distance of note vectors from their session centroid "
            f"is {direction} in recent snapshots (through {recent_date}) than in earlier "
            f"ones (around {older_date}). {links} {verb} {edge} the centre now. {question}"
        )
        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text for note in named],
                geist_id="vocabulary_expansion",
            )
        )

    except Exception:
        logger.debug("vocabulary_expansion geist failed", exc_info=True)
        return []

    return vault.sample(suggestions, count=1)
