"""Example geist: Highlight orphaned notes with no connections."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find notes with no links to or from other notes."""
    orphans = vault.orphans()

    # Only suggest if there are orphans
    if not orphans:
        return []

    suggestions = []
    for note in orphans[:2]:  # Limit to 2
        text = f"[[{note.title}]] is an orphan - what could it connect to?"
        suggestions.append(Suggestion(text=text, notes=[note.title], geist_id="orphans"))

    return suggestions
