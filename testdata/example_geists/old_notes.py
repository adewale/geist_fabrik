"""Example geist: Highlight old notes that haven't been touched in a while."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find notes that haven't been modified recently."""
    old = vault.old_notes(k=2)

    suggestions = []
    for note in old:
        text = f"[[{note.title}]] hasn't been touched in a while. What's changed since then?"
        suggestions.append(Suggestion(text=text, notes=[note.title], geist_id="old_notes"))

    return suggestions
