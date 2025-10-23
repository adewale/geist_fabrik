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

    suggestions = []

    # Get unlinked pairs
    pairs = vault.unlinked_pairs(k=20)

    if len(pairs) < 2:
        return []

    for note_a, note_b in pairs:
        # Try to find a semantic path using intermediate notes
        path = _find_semantic_path(vault, note_a, note_b, max_hops=3)

        if path and len(path) > 2:
            # Found a multi-hop semantic path
            path_str = " → ".join([f"[[{n.title}]]" for n in path])

            # Calculate path strength (average similarity between consecutive notes)
            path_strength = sum(
                vault.similarity(path[i], path[i + 1]) for i in range(len(path) - 1)
            ) / (len(path) - 1)

            if path_strength > 0.5:  # Strong enough path
                text = (
                    f"Semantic bridge from [[{note_a.title}]] to [[{note_b.title}]]: "
                    f"{path_str}. No direct links exist, but the ideas connect through "
                    f"these stepping stones."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[n.title for n in path],
                        geist_id="bridge_hunter",
                    )
                )

    return vault.sample(suggestions, k=2)


def _find_semantic_path(
    vault: "VaultContext",
    start: "Note",
    end: "Note",
    max_hops: int = 3,
) -> Optional[List["Note"]]:
    """Find semantic path between two notes using greedy best-first search."""
    if max_hops < 2:
        return None

    # For 2-hop path: start -> intermediate -> end
    if max_hops == 2:
        # Find notes similar to start
        candidates = vault.neighbours(start, k=10)

        best_path = None
        best_score = 0.0

        for candidate in candidates:
            if candidate.path == end.path:
                continue

            # Score is average similarity
            sim_start_mid = vault.similarity(start, candidate)
            sim_mid_end = vault.similarity(candidate, end)
            avg_sim = (sim_start_mid + sim_mid_end) / 2

            if avg_sim > best_score and avg_sim > 0.4:
                best_score = avg_sim
                best_path = [start, candidate, end]

        return best_path

    # For 3-hop path: start -> mid1 -> mid2 -> end
    if max_hops == 3:
        candidates1 = vault.neighbours(start, k=10)
        candidates2 = vault.neighbours(end, k=10)

        best_path = None
        best_score = 0.0

        for mid1 in candidates1:
            for mid2 in candidates2:
                if mid1.path == mid2.path or mid1.path == end.path or mid2.path == start.path:
                    continue

                # Calculate path quality
                sim1 = vault.similarity(start, mid1)
                sim2 = vault.similarity(mid1, mid2)
                sim3 = vault.similarity(mid2, end)
                avg_sim = (sim1 + sim2 + sim3) / 3

                if avg_sim > best_score and avg_sim > 0.4:
                    best_score = avg_sim
                    best_path = [start, mid1, mid2, end]

        return best_path

    return None
