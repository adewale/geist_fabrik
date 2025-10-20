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

    suggestions = []

    # Get hub notes and check their neighborhoods
    hubs = vault.hubs(k=10)

    for hub in hubs:
        # Find notes similar to this hub but not linked
        neighbors = vault.neighbors(hub, k=10)

        for neighbor in neighbors:
            if vault.links_between(hub, neighbor):
                continue

            # This neighbor is similar to the hub but unlinked
            # Check if linking them would bridge different areas
            similarity = vault.similarity(hub, neighbor)

            if similarity > 0.6:  # Strong similarity but no link
                text = (
                    f"What if [[{hub.title}]] and [[{neighbor.title}]] were connected? "
                    f"They're semantically similar but in different parts of your vault. "
                    f"A link might bridge important concepts."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[hub.title, neighbor.title],
                        geist_id="bridge_builder",
                    )
                )

    return vault.sample(suggestions, k=3)
