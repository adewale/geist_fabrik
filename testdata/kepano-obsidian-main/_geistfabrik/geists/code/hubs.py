"""Example geist: Highlight hub notes with many connections."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find notes that are highly connected (hubs)."""
    hubs = vault.hubs(k=2)

    suggestions = []
    for note in hubs:
        # Count backlinks
        backlinks = vault.backlinks(note)
        text = (
            f"[[{note.title}]] is a hub with {len(backlinks)} connections. What makes it central?"
        )
        suggestions.append(Suggestion(text=text, notes=[note.title], geist_id="hubs"))

    return suggestions
