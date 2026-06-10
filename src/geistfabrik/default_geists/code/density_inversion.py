"""Density Inversion geist - detects mismatches between link and semantic structure.

Finds cases where notes are densely linked but semantically scattered (form without
meaning) or semantically similar but sparsely linked (meaning without form).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


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

    for note in vault.sample(notes, min(30, len(notes))):
        # Get graph neighbours (notes linked to/from this note)
        graph_neighbours = vault.graph_neighbours(note)

        if len(graph_neighbours) < 3:
            continue

        # Calculate graph density (how interconnected are the neighbours?)
        edges = 0
        for i, n1 in enumerate(graph_neighbours):
            for n2 in graph_neighbours[i + 1 :]:
                if vault.links_between(n1, n2):
                    edges += 1

        max_possible_edges = len(graph_neighbours) * (len(graph_neighbours) - 1) / 2
        graph_density = edges / max_possible_edges if max_possible_edges > 0 else 0

        # Calculate semantic density (how similar are the neighbours?)
        similarities = []
        for i, n1 in enumerate(graph_neighbours):
            for n2 in graph_neighbours[i + 1 :]:
                sim = vault.similarity(n1, n2)
                similarities.append(sim)

        semantic_density = sum(similarities) / len(similarities) if similarities else 0

        # Detect inversions

        # Case 1: Dense links, sparse meaning (tightly linked but semantically scattered)
        if graph_density > 0.6 and semantic_density < 0.3:
            neighbour_sample = vault.sample(graph_neighbours, k=3)
            neighbour_names = ", ".join([f"[[{n.obsidian_link}]]" for n in neighbour_sample])

            text = (
                f"[[{note.obsidian_link}]]'s neighbours ({neighbour_names}) are tightly "
                f"linked to each other but semantically scattered. Is there a coherent "
                f"topic here, or is this just organizational linking?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link] + [n.obsidian_link for n in neighbour_sample],
                    geist_id="density_inversion",
                )
            )

        # Case 2: Sparse links, dense meaning (semantically similar but not linked)
        elif graph_density < 0.3 and semantic_density > 0.6:
            neighbour_sample = vault.sample(graph_neighbours, k=3)
            neighbour_names = ", ".join([f"[[{n.obsidian_link}]]" for n in neighbour_sample])

            text = (
                f"[[{note.obsidian_link}]]'s neighbours ({neighbour_names}) are "
                f"semantically similar but aren't linked to each other. "
                f"Missing connections in a coherent cluster?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link] + [n.obsidian_link for n in neighbour_sample],
                    geist_id="density_inversion",
                )
            )

    return vault.sample(suggestions, k=2)
