"""Bridge Hunter geist - finds semantic paths through graph deserts.

Discovers semantic stepping-stone paths between unlinked notes, showing how
ideas could connect even when direct graph paths don't exist.
"""

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find semantic paths where no graph path exists.

    Returns:
        List of suggestions showing semantic bridge paths
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    # Get unlinked pairs
    all_pairs = vault.unlinked_pairs(k=20)

    # Filter out pairs involving geist journal notes
    pairs = [
        (a, b)
        for a, b in all_pairs
        if not a.path.startswith("geist journal/") and not b.path.startswith("geist journal/")
    ]

    if len(pairs) < 2:
        return []

    for note_a, note_b in pairs:
        # Try to find a semantic path using intermediate notes
        path = _find_semantic_path(vault, note_a, note_b, max_hops=3)

        if path and len(path) > 2:
            # Found a multi-hop semantic path
            path_str = " → ".join([f"[[{n.obsidian_link}]]" for n in path])

            # Calculate path strength (average similarity between consecutive notes)
            path_strength = sum(
                vault.similarity(path[i], path[i + 1]) for i in range(len(path) - 1)
            ) / (len(path) - 1)

            if path_strength > SimilarityLevel.MODERATE:  # Strong enough path
                text = (
                    f"Semantic bridge from [[{note_a.obsidian_link}]] to "
                    f"[[{note_b.obsidian_link}]]: {path_str}. No direct links exist, "
                    f"but the ideas connect through these stepping stones."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[n.obsidian_link for n in path],
                        geist_id="bridge_hunter",
                    )
                )

    return vault.sample(suggestions, k=2)


def _filter_journal_notes(
    candidates_with_scores: list[tuple["Note", float]],
) -> list[tuple["Note", float]]:
    """Filter out geist journal notes from candidate list.

    Args:
        candidates_with_scores: List of (note, score) tuples

    Returns:
        Filtered list excluding journal notes
    """
    return [
        (n, score) for n, score in candidates_with_scores if not n.path.startswith("geist journal/")
    ]


def _find_semantic_path(
    vault: "VaultContext",
    start: "Note",
    end: "Note",
    max_hops: int = 3,
) -> Optional[List["Note"]]:
    """Find semantic path between two notes using greedy best-first search."""
    from geistfabrik.similarity_analysis import SimilarityLevel

    if max_hops < 2:
        return None

    # For 2-hop path: start -> intermediate -> end
    if max_hops == 2:
        # Find notes similar to start (get scores to avoid recomputation)
        all_candidates_with_scores = vault.neighbours(start, k=10, return_scores=True)

        # Filter out geist journal notes
        candidates_with_scores = _filter_journal_notes(all_candidates_with_scores)

        best_path = None
        best_score = 0.0

        # Compute similarities using individual calls to benefit from cache
        for candidate, sim_start_mid in candidates_with_scores:
            if candidate.path == end.path:
                continue

            # Score is average similarity (already have sim_start_mid from neighbours)
            sim_mid_end = vault.similarity(candidate, end)
            avg_sim = (sim_start_mid + sim_mid_end) / 2

            if avg_sim > best_score and avg_sim > SimilarityLevel.WEAK:
                best_score = avg_sim
                best_path = [start, candidate, end]

        return best_path

    # For 3-hop path: start -> mid1 -> mid2 -> end
    if max_hops == 3:
        # Get scores to avoid recomputing start->mid1 and end->mid2
        all_candidates1_with_scores = vault.neighbours(start, k=10, return_scores=True)
        all_candidates2_with_scores = vault.neighbours(end, k=10, return_scores=True)

        # Filter out geist journal notes
        candidates1_with_scores = _filter_journal_notes(all_candidates1_with_scores)
        candidates2_with_scores = _filter_journal_notes(all_candidates2_with_scores)

        best_path = None
        best_score = 0.0

        # Compute similarities using individual calls to benefit from cache
        for mid1, sim1 in candidates1_with_scores:
            for mid2, sim3 in candidates2_with_scores:
                if mid1.path == mid2.path or mid1.path == end.path or mid2.path == start.path:
                    continue

                # Calculate path quality (already have sim1 and sim3 from neighbours)
                sim2 = vault.similarity(mid1, mid2)
                avg_sim = (sim1 + sim2 + sim3) / 3

                if avg_sim > best_score and avg_sim > SimilarityLevel.WEAK:
                    best_score = avg_sim
                    best_path = [start, mid1, mid2, end]

        return best_path

    return None
