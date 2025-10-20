"""Example geist: Highlight orphaned notes."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find notes with no links to or from them."""
    orphaned = vault.orphans()

    suggestions = []
    for note in orphaned[:3]:  # Limit to 3
        suggestions.append(
            Suggestion(
                text=f"[[{note.title}]] is an orphan. "
                f"What if you connected it to your knowledge graph?",
                notes=[note.title],
                geist_id="orphans",
            )
        )

    return suggestions
