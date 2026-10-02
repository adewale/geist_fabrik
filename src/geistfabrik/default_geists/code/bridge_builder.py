"""Bridge builder geist - finds notes that could bridge disconnected clusters.

Identifies notes that might serve as conceptual bridges between separate
areas of your knowledge graph.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
    from geistfabrik.models import Note


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest notes that could bridge disconnected areas.

    Returns:
        List of suggestions for potential bridge notes
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []
    # Each unordered pair is reported once, even when both notes are hubs
    reported: set[frozenset[str]] = set()

    def graph_neighbourhood(note: "Note") -> set[str]:
        """Paths of the notes linked to or from ``note``."""
        return {n.path for n in vault.outgoing_links(note)} | {
            n.path for n in vault.backlinks(note)
        }

    # Get hub notes and check their neighbourhoods
    hubs = vault.hubs(count=10)

    for hub in hubs:
        hub_neighbourhood = graph_neighbourhood(hub)

        # Find notes similar to this hub but not linked
        neighbours_with_scores = vault.neighbours(hub, count=10, return_scores=True)

        for neighbour, similarity in neighbours_with_scores:
            if similarity <= SimilarityLevel.HIGH:  # Need strong similarity
                continue

            pair = frozenset((hub.path, neighbour.path))
            if pair in reported or vault.links_between(hub, neighbour):
                continue

            # "Different parts of your vault": not linked directly AND no note
            # links to or from both of them (they are not two hops apart)
            if hub_neighbourhood & graph_neighbourhood(neighbour):
                continue

            reported.add(pair)
            text = (
                f"What if [[{hub.link_text}]] and "
                f"[[{neighbour.link_text}]] were connected? "
                f"They're semantically similar but in different parts of your vault: "
                f"no link joins them, directly or through a shared neighbour. "
                f"A link might bridge important concepts."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[hub.link_text, neighbour.link_text],
                    geist_id="bridge_builder",
                )
            )

    return vault.sample(suggestions, count=3)
