"""Hidden Hub geist - finds semantically central notes that aren't well-linked.

Identifies notes that are semantically related to many other notes but have few
actual links, suggesting they might be important conceptual hubs that are under-recognized.
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

    suggestions = []

    notes = vault.notes()

    if len(notes) < 20:
        return []

    for note in vault.sample(notes, min(50, len(notes))):
        # Count actual links (outgoing + incoming)
        outgoing = len(note.links)
        incoming = len(vault.backlinks(note))
        total_links = outgoing + incoming

        # Find semantic neighbors with scores (OP-9: avoid recomputing similarities)
        neighbors_with_scores = vault.neighbours(note, k=30, return_scores=True)

        # Filter to only high-similarity neighbors
        high_similarity_count = sum(1 for n, sim in neighbors_with_scores if sim > 0.6)

        # High semantic centrality, low graph centrality = hidden hub
        if high_similarity_count > 10 and total_links < 5:
            # Sample some neighbors to mention (extract notes from tuples)
            neighbor_notes = [n for n, sim in neighbors_with_scores[:10]]
            neighbor_sample = vault.sample(neighbor_notes, k=3)
            neighbor_names = ", ".join([f"[[{n.title}]]" for n in neighbor_sample])

            text = (
                f"[[{note.title}]] is semantically related to {high_similarity_count} notes "
                f"(including {neighbor_names}) but only has {total_links} links. "
                f"Hidden hub? Maybe it's a concept that connects things implicitly."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.title] + [n.title for n in neighbor_sample],
                    geist_id="hidden_hub",
                )
            )

    return vault.sample(suggestions, k=3)
