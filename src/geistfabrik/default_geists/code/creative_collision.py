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

    # OPTIMIZATION #5: Collect pairs first, then batch compute similarities
    pairs_to_check = []
    for _ in range(10):
        pair = vault.sample(notes, k=2)
        if len(pair) != 2:
            continue

        note_a, note_b = pair

        # Check if they're unlinked and dissimilar
        if vault.links_between(note_a, note_b):
            continue

        pairs_to_check.append((note_a, note_b))

    # Batch compute all similarities at once
    if pairs_to_check:
        notes_a = [pair[0] for pair in pairs_to_check]
        notes_b = [pair[1] for pair in pairs_to_check]
        sim_matrix = vault.batch_similarity(notes_a, notes_b)

        for i, (note_a, note_b) in enumerate(pairs_to_check):
            # Extract pairwise similarity from matrix diagonal
            similarity = sim_matrix[i, i]

            # Look for moderately dissimilar notes (not too similar, not completely unrelated)
            if 0.2 < similarity < 0.5:
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
