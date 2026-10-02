"""Hidden Hub geist - finds semantically central notes that aren't well-linked.

Identifies notes that are semantically related to many other notes but have few
actual links, suggesting they might be important conceptual hubs that are under-recognised.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Semantic neighbours examined per note.
MAX_NEIGHBOURS = 30


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
        # Count real connections: distinct notes linked to or from this one
        # (raw note.links also counted unresolved and repeated links)
        total_links = len(vault.graph_neighbours(note))

        # Find semantic neighbours with scores
        neighbours_with_scores = vault.neighbours(note, count=MAX_NEIGHBOURS, return_scores=True)

        # Filter to only high-similarity neighbours
        high_similarity_count = sum(
            1 for n, sim in neighbours_with_scores if sim > SimilarityLevel.HIGH
        )

        # High semantic centrality, low graph centrality = hidden hub
        if high_similarity_count > 10 and total_links < 5:
            # Sample some neighbours to mention (extract notes from tuples)
            neighbour_notes = [n for n, sim in neighbours_with_scores[:10]]
            neighbour_sample = vault.sample(neighbour_notes, count=3)
            neighbour_names = ", ".join([f"[[{n.link_text}]]" for n in neighbour_sample])

            # Only the top MAX_NEIGHBOURS are examined, so a full count is a floor
            related = (
                f"at least {high_similarity_count}"
                if high_similarity_count == MAX_NEIGHBOURS
                else str(high_similarity_count)
            )
            if total_links == 0:
                linked = "isn't linked to any notes"
            else:
                linked = f"is linked to only {total_links} note{'s' if total_links > 1 else ''}"

            text = (
                f"[[{note.link_text}]] is semantically related to "
                f"{related} notes (including {neighbour_names}) but {linked}. "
                f"Hidden hub? Maybe it's a concept that connects things implicitly."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text] + [n.link_text for n in neighbour_sample],
                    geist_id="hidden_hub",
                )
            )

    return vault.sample(suggestions, count=3)
