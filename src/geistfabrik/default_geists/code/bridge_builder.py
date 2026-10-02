"""Bridge builder geist - finds notes that could bridge disconnected clusters.

Identifies notes that might serve as conceptual bridges between separate
areas of your knowledge graph.

For each hub, a semantically similar note qualifies when no link joins the
two, directly or through a shared neighbour. The text names up to two of the
notes linking to the hub (its cluster): the neighbour is linked to none of
them, since every note linked with the hub is in the hub's neighbourhood.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
    from geistfabrik.models import Note


# Notes linking to the hub named as its cluster.
CLUSTER_NAMED = 2


def _cluster_phrase(cluster: list["Note"], total: int) -> str:
    """'[[A]] and [[B]] link to' / '[[A]], [[B]] and 3 other notes link to'."""
    links = [f"[[{n.link_text}]]" for n in cluster]
    others = total - len(cluster)
    if others:
        noun = "other note" if others == 1 else "other notes"
        links.append(f"{others} {noun}")
    if len(links) == 1:
        return f"{links[0]} links to"
    return f"{', '.join(links[:-1])} and {links[-1]} link to"


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
            backlinks = vault.backlinks(hub)
            cluster = vault.sample(backlinks, CLUSTER_NAMED)
            text = (
                f"What if [[{hub.link_text}]] and "
                f"[[{neighbour.link_text}]] were connected? "
                f"They're semantically similar but in different parts of your vault: "
                f"{_cluster_phrase(cluster, len(backlinks))} [[{hub.link_text}]], but no "
                f"link joins [[{neighbour.link_text}]] to it or to any note linked with it. "
                f"A link might bridge important concepts."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[hub.link_text, neighbour.link_text, *(n.link_text for n in cluster)],
                    geist_id="bridge_builder",
                )
            )

    return vault.sample(suggestions, count=3)
