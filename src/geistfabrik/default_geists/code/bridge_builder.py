"""Bridge builder geist - finds notes that could bridge disconnected clusters.

Identifies notes that might serve as conceptual bridges between separate
areas of your knowledge graph.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest notes that could bridge disconnected areas.

    Returns:
        List of suggestions for potential bridge notes
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    # Get hub notes and check their neighbourhoods
    hubs = vault.hubs(k=10)

    for hub in hubs:
        # Find notes similar to this hub but not linked
        neighbours_with_scores = vault.neighbours(hub, k=10, return_scores=True)

        for neighbour, similarity in neighbours_with_scores:
            if vault.links_between(hub, neighbour):
                continue

            # This neighbour is similar to the hub but unlinked
            # Check if linking them would bridge different areas

            if similarity > SimilarityLevel.HIGH:  # Strong similarity but no link
                text = (
                    f"What if [[{hub.obsidian_link}]] and "
                    f"[[{neighbour.obsidian_link}]] were connected? "
                    f"They're semantically similar but in different parts of your vault. "
                    f"A link might bridge important concepts."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[hub.obsidian_link, neighbour.obsidian_link],
                        geist_id="bridge_builder",
                    )
                )

    return vault.sample(suggestions, k=3)
