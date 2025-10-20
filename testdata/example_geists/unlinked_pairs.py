"""Example geist: Suggest linking semantically similar but unlinked notes."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find unlinked note pairs that might benefit from connection."""
    pairs = vault.unlinked_pairs(k=3)

    suggestions = []
    for note_a, note_b in pairs:
        text = f"What if you linked [[{note_a.title}]] and [[{note_b.title}]]? They seem related."
        suggestions.append(
            Suggestion(text=text, notes=[note_a.title, note_b.title], geist_id="unlinked_pairs")
        )

    return suggestions
