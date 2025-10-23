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

    suggestions = []

    # Get random pairs of notes
    notes = vault.notes()

    if len(notes) < 2:
        return []

    # Sample multiple pairs
    for _ in range(10):
        pair = vault.sample(notes, k=2)
        if len(pair) != 2:
            continue

        note_a, note_b = pair

        # Check if they're unlinked and dissimilar
        if vault.links_between(note_a, note_b):
            continue

        similarity = vault.similarity(note_a, note_b)

        # Look for moderately dissimilar notes (not too similar, not completely unrelated)
        if 0.2 < similarity < 0.5:
            text = (
                f"What if you combined ideas from [[{note_a.title}]] and [[{note_b.title}]]? "
                f"They're from different domains but might spark something unexpected."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note_a.title, note_b.title],
                    geist_id="creative_collision",
                )
            )

    return vault.sample(suggestions, k=3)
