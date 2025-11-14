"""Hidden Hub geist - finds semantically central notes that aren't well-linked.

Identifies notes that are semantically related to many other notes but have few
actual links, suggesting they might be important conceptual hubs that are under-recognised.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes that are semantically important but under-connected.

    Returns:
        List of suggestions highlighting potential hidden hubs
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    notes = vault.notes()

    if len(notes) < 20:
        return []

    for note in vault.sample(notes, min(50, len(notes))):
        # Count actual links (outgoing + incoming)
        outgoing = len(note.links)
        incoming = len(vault.backlinks(note))
        total_links = outgoing + incoming

        # Find semantic neighbours with scores
        neighbors_with_scores = vault.neighbours(note, k=30, return_scores=True)

        # Filter to only high-similarity neighbours
        high_similarity_count = sum(
            1 for n, sim in neighbors_with_scores if sim > SimilarityLevel.HIGH
        )

        # High semantic centrality, low graph centrality = hidden hub
        if high_similarity_count > 10 and total_links < 5:
            # Sample some neighbours to mention (extract notes from tuples)
            neighbor_notes = [n for n, sim in neighbors_with_scores[:10]]
            neighbor_sample = vault.sample(neighbor_notes, k=3)
            neighbor_names = ", ".join([f"[[{n.obsidian_link}]]" for n in neighbor_sample])

            text = (
                f"[[{note.obsidian_link}]] is semantically related to "
                f"{high_similarity_count} notes (including {neighbor_names}) but only "
                f"has {total_links} links. Hidden hub? Maybe it's a concept that "
                f"connects things implicitly."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link] + [n.obsidian_link for n in neighbor_sample],
                    geist_id="hidden_hub",
                )
            )

    return vault.sample(suggestions, k=3)
