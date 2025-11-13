"""Creative collision geist - suggests unexpected combinations of notes.

Finds notes from different domains/topics and suggests combining them
for creative insights.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest creative collisions between unrelated notes.

    Returns:
        List of suggestions for creative note combinations
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    # Get random pairs of notes
    notes = vault.notes()

    if len(notes) < 2:
        return []

    # Collect candidate pairs
    for _ in range(10):
        pair = vault.sample(notes, k=2)
        if len(pair) != 2:
            continue

        note_a, note_b = pair

        # Check if they're unlinked and dissimilar
        if vault.links_between(note_a, note_b):
            continue

        # Compute similarity using individual call to benefit from cache
        similarity = vault.similarity(note_a, note_b)

        # Look for moderately dissimilar notes (not too similar, not completely unrelated)
        if SimilarityLevel.NOISE < similarity < SimilarityLevel.MODERATE:
            text = (
                f"What if you combined ideas from [[{note_a.obsidian_link}]] and "
                f"[[{note_b.obsidian_link}]]? They're from different domains but "
                f"might spark something unexpected."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note_a.obsidian_link, note_b.obsidian_link],
                    geist_id="creative_collision",
                )
            )

    return vault.sample(suggestions, k=3)
