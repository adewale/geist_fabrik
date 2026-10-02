"""Density Inversion geist - detects mismatches between link and semantic structure.

Finds cases where notes are densely linked but semantically scattered (form without
meaning) or semantically similar but sparsely linked (meaning without form).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from geistfabrik import Suggestion, VaultContext
    from geistfabrik.models import Note

# Rows of the neighbour similarity matrix computed at once, bounding memory
# for a hub with thousands of graph neighbours.
_SIMILARITY_ROW_BLOCK = 1024


def _link_count(neighbours: list["Note"], neighbour_paths: "Callable[[Note], set[str]]") -> int:
    """Pairs of the neighbours linked to each other (in either direction).

    Two notes are linked exactly when each is in the other's graph
    neighbours, so each link is seen from both of its ends.
    """
    members = {n.path for n in neighbours}
    return sum(len(neighbour_paths(n) & members) for n in neighbours) // 2


def _semantic_density(vault: "VaultContext", neighbours: list["Note"]) -> float:
    """Mean pairwise similarity of the neighbours (upper triangle, i < j).

    One vectorised similarity matrix (in row blocks) rather than a
    similarity() call per pair; batch_similarity() returns cached values
    where the session already has them, so each pair scores as similarity()
    would.
    """
    count = len(neighbours)
    total = 0.0
    for start in range(0, count, _SIMILARITY_ROW_BLOCK):
        block = vault.batch_similarity(
            neighbours[start : start + _SIMILARITY_ROW_BLOCK], neighbours
        )
        for offset, row in enumerate(block):
            total += float(row[start + offset + 1 :].sum())
    pairs = count * (count - 1) / 2
    return total / pairs if pairs else 0.0


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find dense links with sparse meaning, or vice versa.

    Returns:
        List of suggestions highlighting structure/meaning mismatches
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 20:
        return []

    # Graph neighbour paths per note, built once per run
    adjacency: dict[str, set[str]] = {}

    def neighbour_paths(n: "Note") -> set[str]:
        paths = adjacency.get(n.path)
        if paths is None:
            paths = adjacency[n.path] = {m.path for m in vault.graph_neighbours(n)}
        return paths

    for note in vault.sample(notes, min(30, len(notes))):
        # Get graph neighbours (notes linked to/from this note)
        graph_neighbours = vault.graph_neighbours(note)

        if len(graph_neighbours) < 3:
            continue

        # Calculate graph density (how interconnected are the neighbours?)
        edges = _link_count(graph_neighbours, neighbour_paths)

        max_possible_edges = len(graph_neighbours) * (len(graph_neighbours) - 1) / 2
        graph_density = edges / max_possible_edges if max_possible_edges > 0 else 0

        # Calculate semantic density (how similar are the neighbours?)
        semantic_density = _semantic_density(vault, graph_neighbours)

        # Detect inversions

        # Case 1: Dense links, sparse meaning (tightly linked but semantically scattered)
        if graph_density > 0.6 and semantic_density < 0.3:
            neighbour_sample = vault.sample(graph_neighbours, count=3)
            neighbour_names = ", ".join([f"[[{n.link_text}]]" for n in neighbour_sample])

            text = (
                f"[[{note.link_text}]]'s neighbours ({neighbour_names}) are tightly "
                f"linked to each other but semantically scattered. Is there a coherent "
                f"topic here, or is this just organizational linking?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text] + [n.link_text for n in neighbour_sample],
                    geist_id="density_inversion",
                )
            )

        # Case 2: Sparse links, dense meaning (semantically similar but not linked)
        elif graph_density < 0.3 and semantic_density > 0.6:
            neighbour_sample = vault.sample(graph_neighbours, count=3)
            neighbour_names = ", ".join([f"[[{n.link_text}]]" for n in neighbour_sample])

            text = (
                f"[[{note.link_text}]]'s neighbours ({neighbour_names}) are "
                f"semantically similar but few of them link to each other. "
                f"Missing connections in a coherent cluster?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text] + [n.link_text for n in neighbour_sample],
                    geist_id="density_inversion",
                )
            )

    return vault.sample(suggestions, count=2)
