"""Example geist: Suggest linking semantically similar but unlinked notes."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find pairs of notes that are semantically similar but not linked."""
    # Get unlinked pairs
    pairs = vault.unlinked_pairs(k=3)

    suggestions = []
    for note_a, note_b in pairs:
        similarity = vault.similarity(note_a, note_b)
        suggestions.append(
            Suggestion(
                text=f"What if you linked [[{note_a.title}]] and [[{note_b.title}]]? "
                f"They're {similarity:.1%} similar but not connected.",
                notes=[note_a.title, note_b.title],
                geist_id="unlinked_pairs",
            )
        )

    return suggestions
